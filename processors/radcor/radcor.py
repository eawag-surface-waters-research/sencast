#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Radcor processor for adjacency effect (part of Acolite)"""


import os
import re
import sys
import netCDF4
import shutil
import importlib
import numpy as np
import xarray as xr
import contextlib
from osgeo import gdal, osr
from datetime import datetime
from scipy.spatial import cKDTree
from scipy.interpolate import RegularGridInterpolator
from utils.auxil import log
from constants import REPROD_DIR


# Key of the params section for this processor
from utils.product_fun import get_lons_lats

PARAMS_SECTION = "RADCOR"
# The name of the folder to which the output product will be saved
OUT_DIR = "L1RADCOR"
# The name of the settings file for acolite
SETTINGS_FILENAME = "radcor_{}.properties"

def _tile_id_from_product(product_id):
    match = re.search(r"_T\d{2}[A-Z]{3}_", product_id)
    if match:
        return match.group(0).strip("_")
    return None

def _select_acolite_output(out_dir, product_id, suffix):
    candidates = [f for f in os.listdir(out_dir) if f.endswith(suffix)]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    exact = [f for f in candidates if product_id in f]
    if len(exact) == 1:
        return exact[0]
    tile_id = _tile_id_from_product(product_id)
    if tile_id:
        tile_matches = [f for f in candidates if tile_id in f]
        if len(tile_matches) == 1:
            return tile_matches[0]
    return None

def process(env, params, l1product_path, _, out_path):
    """This processor calls acolite for the source product and writes the result to disk. It returns the location of the output product."""

    sys.path.append(env["ACOLITE"]['root_path'])
    ac = importlib.import_module("acolite.acolite")

    product = os.path.basename(l1product_path)
    start_date = dates_from_name(product)[0]
    product_id = os.path.splitext(product)[0]

    sensor, resolution, wkt = params['General']['sensor'], params['General']['resolution'], params['General']['wkt']
    lons, lats = get_lons_lats(wkt)
    limit = "{},{},{},{}".format(min(lats), min(lons), max(lats), max(lons))

    out_path = os.path.join(out_path, OUT_DIR, "{}_{}".format(product[:3], start_date), product_id)
    os.makedirs(out_path, exist_ok=True)

    os.environ['EARTHDATA_u'] = env['EARTHDATA']['username']
    os.environ['EARTHDATA_p'] = env['EARTHDATA']['password']

    radcor_folder = os.path.join(os.path.dirname(l1product_path), "RADCOR")
    os.makedirs(radcor_folder, exist_ok=True)
    radcor_file = os.path.join(radcor_folder, os.path.basename(l1product_path))

    if os.path.exists(radcor_file):
        if "synchronise" in params["General"].keys() and params['General']['synchronise'] == "false":
            log(env["General"]["log"], "Removing file: ${}".format(radcor_file))
            shutil.rmtree(radcor_file)
        else:
            log(env["General"]["log"], 'Skipping RADCOR, target already exists: {}'.format(radcor_file), indent=1)
            return [radcor_file]

    settings_file = os.path.join(out_path, REPROD_DIR, SETTINGS_FILENAME.format(sensor))
    if not os.path.isfile(settings_file):
        rewrite_settings_file(settings_file, sensor, resolution, limit, params[PARAMS_SECTION])

    ac.acolite_run(settings_file, l1product_path, out_path)

    toa_prefix = None
    acolite_file = None
    rf = _select_acolite_output(out_path, product_id, "_L2R.nc")
    if not rf:
        raise ValueError(
            "ACOLITE L2R output is required for RADCOR because rhotc bands are needed. "
            "No unique L2R file found for product {}.".format(product_id)
        )
    acolite_file = os.path.join(out_path, rf)
    toa_prefix = "rhotc_"
    log(env["General"]["log"], "Selected ACOLITE L2R output (rhotc_): {}".format(rf), indent=1)

    tmp_dir = os.path.join(out_path, "tmp", os.path.basename(l1product_path))

    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir)

    shutil.copytree(l1product_path, tmp_dir)

    if sensor == "OLCI":
        rad_nc = netCDF4.Dataset(acolite_file)
        rad_lat = np.array(rad_nc.variables["lat"][:])
        rad_lng = np.array(rad_nc.variables["lon"][:])
        rad_coords = np.column_stack([rad_lat.flatten(), rad_lng.flatten()])
        rad_idx = np.indices(rad_lat.shape)
        rad_indices = np.column_stack([rad_idx[0].ravel(), rad_idx[1].ravel()])

        with netCDF4.Dataset(os.path.join(tmp_dir, "geo_coordinates.nc")) as nc:
            l1_shape = nc.variables["latitude"].shape
            l1_lat = np.array(nc.variables["latitude"][:])
            l1_lng = np.array(nc.variables["longitude"][:])
            l1_coords = np.column_stack([l1_lat.ravel(), l1_lng.ravel()])
            tree = cKDTree(l1_coords)
            distances, indices = tree.query(rad_coords, k=1)
            threshold = 0.001
            valid_mask = distances < threshold
            i, j = np.unravel_index(indices[valid_mask], l1_lat.shape)
            l1_indices = np.array(list(zip(i, j)))

        if l1_indices.shape[0] != rad_indices.shape[0]:
            raise ValueError("Cannot match all Acolite pixels to OLCI pixels.")

        d = distance_sun_earth(doy_ocli(os.path.basename(l1product_path)))
        sza = solar_zenith_angle(os.path.join(tmp_dir, "tie_geometries.nc"), l1_shape)[
            l1_indices[:, 0], l1_indices[:, 1]]

        files = [f for f in os.listdir(tmp_dir) if "_radiance.nc" in f]
        files.sort()

        for file in files:
            band = file.split("_")[0]
            band_index = int(band[2:]) - 1
            rad_band = getattr(rad_nc, "{}_name".format(band))
            p_t = np.array(rad_nc.variables[f"{toa_prefix}{rad_band}"][:])[rad_indices[:,0], rad_indices[:,1]]
            gain = gain_value(os.path.basename(l1product_path)[:3], band_index)
            F0 = solar_flux(band_index, os.path.join(tmp_dir, "instrument_data.nc"), l1_shape)[
                l1_indices[:, 0], l1_indices[:, 1]]
            radiance = reflectance_radiance(p_t, F0, sza, d, gain)
            with netCDF4.Dataset(os.path.join(tmp_dir, file), mode="a") as nc:
                combined_radiance = np.array(nc.variables["{}_radiance".format(band)][:])
                if combined_radiance.shape != l1_shape:
                    raise ValueError("Inconsistent OLCI grids.")
                combined_radiance[l1_indices[:, 0], l1_indices[:, 1]] = radiance
                nc.variables["{}_radiance".format(band)][:] = combined_radiance

        rad_nc.close()
    elif sensor == "MSI":
        if int(resolution) != int(20):
            raise ValueError("RADCOR for MSI only implemented for 20m")
        WAVE_TO_BAND = {
            "442": "B01", "443": "B01", "492": "B02", "559": "B03", "560": "B03", "665": "B04",
            "704": "B05", "739": "B06", "740": "B06", "780": "B07", "783": "B07", "833": "B08",
            "842": "B08", "864": "B8A", "865": "B8A", "940": "B09", "943": "B09", "1375": "B10",
            "1377": "B10", "1610": "B11", "2186": "B12", "2190": "B12",
        }
        BANDS_10M = {"B02", "B03", "B04", "B08"}
        ds = xr.open_dataset(acolite_file)
        lat, lon = ds["lat"].values, ds["lon"].values
        if lat.ndim != 2 or lon.ndim != 2:
            raise ValueError("Expected 2D lat/lon arrays in NetCDF")
        xres = lon[0, 1] - lon[0, 0]
        yres = lat[1, 0] - lat[0, 0]
        if yres >= 0: print("Latitude resolution is non-negative.")
        src_gt = [lon[0, 0], xres, 0, lat[0, 0], 0, yres]
        processed_bands = set()
        for var in sorted(ds.variables):
            if var.startswith(toa_prefix):
                wl = var.split("_", 1)[1]
                band = WAVE_TO_BAND.get(wl)
                if band and band not in processed_bands:
                    jp2 = find_s2_jp2(tmp_dir, band)
                    resamp = (gdal.GRA_NearestNeighbour
                              if band in BANDS_10M
                              else gdal.GRA_Average)
                    rho_acolite = ds[var].values
                    rho_reprojected = reproject_to_band(rho_acolite, src_gt, jp2, resamp)
                    dn_sub, mask = float_to_uint16(rho_reprojected)
                    if mask.any():
                        update_band(jp2, dn_sub, mask)
                        processed_bands.add(band)
        ds.close()
    else:
        raise ValueError("RADCOR not implemented for {}".format(sensor))

    shutil.copytree(tmp_dir, radcor_file)
    shutil.rmtree(tmp_dir)

    return [radcor_file]


def rewrite_settings_file(settings_file, sensor, resolution, limit, parameters):
    with open(os.path.join(os.path.dirname(__file__), SETTINGS_FILENAME.format(sensor)), "r") as f:
        text = f.read()
    text = text.replace("${limit}", limit)
    text = text.replace("${resolution}", resolution)
    os.makedirs(os.path.dirname(settings_file), exist_ok=True)
    with open(settings_file, "w") as f:
        f.write(text)
    update_settings_file(settings_file, parameters)


def update_settings_file(file_path, parameters):
    key_value_pattern = re.compile(r"^(\s*[\w_]+)\s*=\s*(.*?)(\s*(#.*)?)?$")

    with open(file_path, 'r') as file:
        lines = file.readlines()

    updated_lines = []
    keys_in_file = set()
    updated = False

    # Iterate through the file to update existing parameters
    for line in lines:
        match = key_value_pattern.match(line)
        if match:
            key = match.group(1).strip()  # Key
            value = match.group(2).strip()  # Value before any comments
            comment = match.group(4) if match.group(4) else ''  # Inline comment if any

            # Check if the key exists in the parameters dict
            if key in parameters:
                # Only update if the value has actually changed
                if value != str(parameters[key]):
                    updated_lines.append(f"{key}={parameters[key]} {comment}\n")
                    updated = True  # Mark that we made an update
                else:
                    # Keep the original line if the value has not changed
                    updated_lines.append(line)
                keys_in_file.add(key)
            else:
                # Keep the original line if key is not in the dict
                updated_lines.append(line)
        else:
            # Keep non key-value lines (comments or blank lines)
            updated_lines.append(line)

    if updated_lines and not updated_lines[-1].endswith("\n"):
        updated_lines[-1] = updated_lines[-1] + "\n"

    # Add missing key-value pairs at the end of the file
    for key, value in parameters.items():
        if key not in keys_in_file:
            updated_lines.append(f"{key}={value}\n")
            updated = True

    # Write the updated content back to the file only if changes were made
    if updated:
        with open(file_path, 'w') as file:
            file.writelines(updated_lines)


def find_closest_point(lat_array, lon_array, lat_target, lon_target):
    distances_sq = (lat_array - lat_target) ** 2 + (lon_array - lon_target) ** 2
    min_index = np.unravel_index(np.argmin(distances_sq), lat_array.shape)
    min_distance = np.sqrt(distances_sq[min_index])
    return min_index, min_distance


def reflectance_radiance(p_t, F0, sza, d, gain):
    """
    Calculate OLCI radiance from ACOLITE ρ_t

    Parameters
    ----------

    ρ_t
        ACOLITE ρ_t
    F0
        Solar flux at TOA from the solar_flux_band_1 variable
    sza
        Solar zenith angle
    d
        Earth-Sun distance in astronomical units (AU)
    gain
        EUMETSAT SVC gain applied to the radiance
    """
    return (p_t * F0 * np.cos(np.deg2rad(sza))) / (np.pi * d ** 2 * gain)

def solar_flux(band_index, instrument_file, l1_shape):
    with netCDF4.Dataset(instrument_file) as nc:
        solar_flux_raw = np.array(nc.variables["solar_flux"][band_index, :])
    old_rows = np.linspace(0, l1_shape[0] - 1, solar_flux_raw.shape[0])
    new_rows = np.arange(l1_shape[0])
    flux_rows = np.interp(new_rows, old_rows, solar_flux_raw)
    return np.tile(flux_rows[:, None], (1, l1_shape[1]))

def doy_ocli(filename):
    matches = dates_from_name(filename)
    dt_start = datetime.strptime(matches[0], "%Y%m%dT%H%M%S")
    dt_end = datetime.strptime(matches[1], "%Y%m%dT%H%M%S")
    dt = dt_start + (dt_end - dt_start) / 2
    return float(dt.timetuple().tm_yday)

def dates_from_name(filename):
    return re.findall(r"\d{8}T\d{6}", filename)

def distance_sun_earth(doy):
    return 1.00014-0.01671*np.cos(np.pi*(0.9856002831*doy-3.4532868)/180.)-0.00014*np.cos(2*np.pi*(0.9856002831*doy-3.4532868)/180.)

def solar_zenith_angle(tie_geometries_file, l1_shape):
    with netCDF4.Dataset(tie_geometries_file) as nc:
        sza_tie = nc.variables['SZA'][:]
    rows_tie = np.arange(sza_tie.shape[0])
    cols_tie = np.linspace(0, l1_shape[1] - 1, sza_tie.shape[1])
    rr, cc = np.meshgrid(np.arange(l1_shape[0]), np.arange(l1_shape[1]), indexing='ij')
    sza_interpolator = RegularGridInterpolator(
        (rows_tie, cols_tie),
        sza_tie,
        method='nearest',
        bounds_error=False,
        fill_value=np.nan
    )
    return sza_interpolator((rr, cc))

def gain_value(satellite, band_index):
    gain_data = {
        "S3A": [0.975458,0.974061,0.974919,0.968897,0.971844,0.975705,0.980013,0.978339,0.978597,0.979083,0.980135,0.985516,1,1,1,0.987718,0.986,0.986569,1,1,0.913161],
        "S3B": [0.994584,0.9901,0.992215,0.986199,0.988985,0.99114,0.997689,0.996837,0.997165,0.998016,0.997824,1.001631,1,1,1,1.002586,1,1.000891,1,1,0.940641]
    }
    return gain_data[satellite][band_index]

def find_s2_jp2(safe_path, band):
    pat = re.compile(fr'_{band}\.jp2$', re.I)
    granule = os.path.join(safe_path, "GRANULE")
    for tile in os.listdir(granule):
        img = os.path.join(granule, tile, "IMG_DATA")
        if not os.path.isdir(img): continue
        for root,_,files in os.walk(img):
            for f in files:
                if pat.search(f):
                    return os.path.join(root, f)
    raise FileNotFoundError(f"{band} not found under any IMG_DATA")

def build_mem(arr, gt, wkt, gtype):
    ds = gdal.GetDriverByName("MEM") \
             .Create("", arr.shape[1], arr.shape[0], 1, gtype)
    if not ds: raise MemoryError("Failed to create GDAL MEM dataset")
    ds.SetGeoTransform(gt); ds.SetProjection(wkt)
    ds.GetRasterBand(1).WriteArray(arr)
    return ds

def reproject_to_band(rho, src_gt, tpl_jp2, resampling):
    tpl = gdal.Open(tpl_jp2)
    if not tpl: raise IOError(f"Failed to open template JP2: {tpl_jp2}")
    w, h        = tpl.RasterXSize, tpl.RasterYSize
    gt, tgt_wkt = tpl.GetGeoTransform(), tpl.GetProjection()
    tpl = None

    dst = build_mem(np.full((h,w), np.nan, np.float32),
                    gt, tgt_wkt, gdal.GDT_Float32)
    dst.GetRasterBand(1).SetNoDataValue(np.nan)

    srs = osr.SpatialReference(); srs.ImportFromEPSG(4326)
    src_wkt_epsg4326 = srs.ExportToWkt()
    src = build_mem(rho.astype(np.float32), src_gt,
                    src_wkt_epsg4326, gdal.GDT_Float32)
    src.GetRasterBand(1).SetNoDataValue(np.nan)

    status = gdal.ReprojectImage(src, dst, src_wkt_epsg4326, tgt_wkt, resampling)
    if status != 0:
        print(f"gdal.ReprojectImage may have failed with status {status}")

    reprojected_rho = dst.ReadAsArray()
    src = None
    dst = None
    return reprojected_rho

def float_to_uint16(rho):
    SCALE, OFFSET_DN, NODATA_U16 = 10000, 1000, 0
    OFFSET_RHO = -OFFSET_DN / SCALE
    with np.errstate(invalid='ignore'):
        vals = np.rint(rho * SCALE + OFFSET_DN)
        dn = np.where(np.isnan(rho),
                      NODATA_U16,
                      np.clip(vals, 0, 65535)).astype(np.uint16)
    mask = ~np.isnan(rho)
    return dn, mask

def update_band(jp2, dn_sub, mask):
    src_ds = gdal.Open(jp2, gdal.GA_ReadOnly)
    if src_ds is None:
        raise Exception(f"Could not open {jp2}")
    band = src_ds.GetRasterBand(1)
    data = band.ReadAsArray()
    modified_data = data.copy()
    modified_data[mask] = dn_sub[mask]
    gdal_dtype = band.DataType
    temp_ds = gdal.GetDriverByName('MEM').Create(
        '',
        src_ds.RasterXSize,
        src_ds.RasterYSize,
        1,
        gdal_dtype
    )
    temp_ds.SetGeoTransform(src_ds.GetGeoTransform())
    crs_wkt = src_ds.GetProjection()
    temp_ds.SetProjection(crs_wkt)
    temp_band = temp_ds.GetRasterBand(1)
    temp_band.WriteArray(modified_data)
    temp_path = jp2 + '.tmp.jp2'
    gdal.Translate(temp_path, temp_ds, format='JP2OpenJPEG', creationOptions=['QUALITY=100'])
    temp_ds = None
    src_ds = None
    backup_path = jp2 + '.backup.jp2'
    shutil.move(jp2, backup_path)
    shutil.move(temp_path, jp2)
    os.remove(backup_path)
