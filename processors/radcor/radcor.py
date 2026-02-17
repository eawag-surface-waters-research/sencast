#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Radcor processor for adjacency effect correction using ACOLITE outputs.

Scientific objective:
- Replace sensor radiance values with adjacency corrected equivalents derived
  from ACOLITE reflectance, supporting downstream atmospheric correction processing.
- Enforce deterministic MSI band mapping.

Inputs and data dependencies:
- Sentinel-3 OLCI or Sentinel-2 MSI Level 1 products on disk.
- ACOLITE installation path and ancillary credentials provided in env.
- NetCDF geometry and instrument files within the Level 1 product.
- Configuration parameters from the Sencast ini file, especially the RADCOR section.

Outputs or side effects:
- Writes a RADCOR product folder under the input product directory.
- Writes temporary processing folders under the output directory and removes them after completion.
- Writes or updates ACOLITE settings files under the reproducibility folder.
- For MSI runs at 20 m, writes adjacency corrected values into native band files
  using nearest resampling for B02, B03, B04, and B08, and average resampling
  for the remaining MSI bands to avoid inventing subpixel structure.

Manual parameters or settings to review:
- RADCOR section values such as radcor_max_vza, radcor_aot_estimate,
  radcor_kernel_radius, and radcor_rhotc_tolerance_nm.
- ACOLITE settings template and LUT selection for the relevant sensor and resolution.

Hardcoded input and output paths:
- Reads geo_coordinates.nc, tie_geometries.nc, and instrument_data.nc within the Level 1 product.
- Writes temporary processing data under <out_path>/tmp and final output under
  <out_path>/L1RADCOR/<platform_date>/<product_id>.
- Uses settings template processors/radcor/radcor_<sensor>.properties.
"""


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


from utils.product_fun import get_lons_lats

PARAMS_SECTION = "RADCOR"
OUT_DIR = "L1RADCOR"
SETTINGS_FILENAME = "radcor_{}.properties"

# Keep aliases deterministic across S2A, S2B, and S2C to avoid ambiguity when
# ACOLITE exposes slightly different wavelengths for the same MSI band.
MSI_BAND_TO_WAVELENGTHS = {
    "B01": ("443", "442", "444"),
    "B02": ("492", "493", "489"),
    "B03": ("560", "559", "561"),
    "B04": ("665", "667"),
    "B05": ("705", "704", "707"),
    "B06": ("740", "739", "741"),
    "B07": ("783", "780", "781", "784", "785"),
    "B08": ("842", "833", "835", "844"),
    "B8A": ("865", "864", "866"),
    "B09": ("943", "944", "945", "946", "947", "948", "940"),
    "B10": ("1375", "1374", "1373", "1372", "1377", "1378"),
    "B11": ("1610", "1611", "1612", "1614"),
    "B12": ("2190", "2186", "2184", "2191", "2193", "2198", "2202"),
}
MSI_BAND_ORDER = tuple(MSI_BAND_TO_WAVELENGTHS.keys())
MSI_AC_TOKEN_TO_BAND = {
    "1": "B01", "01": "B01", "B1": "B01", "B01": "B01",
    "2": "B02", "02": "B02", "B2": "B02", "B02": "B02",
    "3": "B03", "03": "B03", "B3": "B03", "B03": "B03",
    "4": "B04", "04": "B04", "B4": "B04", "B04": "B04",
    "5": "B05", "05": "B05", "B5": "B05", "B05": "B05",
    "6": "B06", "06": "B06", "B6": "B06", "B06": "B06",
    "7": "B07", "07": "B07", "B7": "B07", "B07": "B07",
    "8": "B08", "08": "B08", "B8": "B08", "B08": "B08",
    "8A": "B8A", "B8A": "B8A",
    "9": "B09", "09": "B09", "B9": "B09", "B09": "B09",
    "10": "B10", "B10": "B10",
    "11": "B11", "B11": "B11",
    "12": "B12", "B12": "B12",
}
MSI_BANDS_10M = {"B02", "B03", "B04", "B08"}

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

def _parse_wavelength(value):
    match = re.search(r"\d+(?:\.\d+)?", str(value))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _parse_ac_bands(value):
    """Parse ACOLITE ac_bands attribute into a list of OLCI band names.

    Expected format example: "Oa01,Oa02,Oa03".
    Returns None if the value is missing or cannot be parsed.
    """

    if value is None:
        return None

    text = str(value)
    parts = []
    for item in text.split(","):
        item = item.strip()
        if re.match(r"^Oa\d{2}$", item):
            parts.append(item)

    if not parts:
        return None

    return parts


def _parse_msi_ac_bands(value):
    """Parse ACOLITE MSI ac_bands tokens into canonical MSI band ids."""

    if value is None:
        return None

    if isinstance(value, (list, tuple, np.ndarray)):
        tokens = [str(item).strip().strip("'\"") for item in value]
    else:
        text = str(value).strip()
        text = text.strip("[]")
        tokens = [item.strip().strip("'\"") for item in text.split(",")]

    selected = set()
    unknown = []
    for token in tokens:
        if not token:
            continue
        key = token.upper()
        if key not in MSI_AC_TOKEN_TO_BAND:
            unknown.append(token)
            continue
        selected.add(MSI_AC_TOKEN_TO_BAND[key])

    if unknown:
        raise ValueError("RADCOR MSI fail-fast: unrecognised ACOLITE ac_bands tokens: {}".format(unknown))

    if not selected:
        return None

    return [band for band in MSI_BAND_ORDER if band in selected]


def _read_float_param(parameters, key, default, log_path=None):
    if key not in parameters:
        return default
    try:
        return float(parameters[key])
    except (TypeError, ValueError):
        if log_path:
            log(log_path, "Invalid value for {}. Using default {}.".format(key, default), indent=1)
        return default

def _select_rhotc_variable(rad_nc, toa_prefix, rad_band, log_path=None, tolerance_nm=2.0):
    target_name = "{}{}".format(toa_prefix, rad_band)
    if target_name in rad_nc.variables:
        return target_name

    target_wl = _parse_wavelength(rad_band)
    if target_wl is None:
        raise KeyError("Missing {} and the band value could not be parsed.".format(target_name))

    candidates = []
    for var in rad_nc.variables:
        if not var.startswith(toa_prefix):
            continue
        wl = _parse_wavelength(var[len(toa_prefix):])
        if wl is None:
            continue
        candidates.append((abs(wl - target_wl), wl, var))

    if not candidates:
        raise KeyError("Missing {} and no numeric {} variables were found.".format(target_name, toa_prefix))

    candidates.sort(key=lambda item: item[0])
    diff, nearest_wl, nearest_name = candidates[0]
    if diff > tolerance_nm:
        raise KeyError(
            "Missing {} and nearest band {} differs by {:.2f} nm.".format(target_name, nearest_name, diff)
        )
    if log_path:
        log(
            log_path,
            "Using {} for missing {} with nearest wavelength {:.2f} nm.".format(nearest_name, target_name, diff),
            indent=1,
        )
    return nearest_name


def _list_rhotc_variables(ds, toa_prefix):
    return sorted(var for var in ds.variables if var.startswith(toa_prefix))


def _build_msi_src_geotransform(ds):
    lat, lon = ds["lat"].values, ds["lon"].values
    if lat.ndim != 2 or lon.ndim != 2:
        raise ValueError("Expected 2D lat/lon arrays in NetCDF")
    xres = lon[0, 1] - lon[0, 0]
    yres = lat[1, 0] - lat[0, 0]
    if yres >= 0:
        raise ValueError("Latitude resolution is non-negative.")
    return [lon[0, 0], xres, 0, lat[0, 0], 0, yres]


def _resolve_msi_band_to_variable(ds, toa_prefix, bands_expected, log_path):
    band_to_var = {}
    missing_bands = {}

    for band in bands_expected:
        wl_tokens = MSI_BAND_TO_WAVELENGTHS[band]
        matches = [f"{toa_prefix}{wl}" for wl in wl_tokens if f"{toa_prefix}{wl}" in ds.variables]
        if not matches:
            missing_bands[band] = wl_tokens
            continue
        band_to_var[band] = matches[0]
        if len(matches) > 1:
            log(
                log_path,
                "RADCOR: multiple {} matches for {}: {}. Using {}.".format(
                    toa_prefix, band, matches, matches[0]
                ),
                indent=2,
            )

    if missing_bands:
        details = []
        for band in bands_expected:
            if band in missing_bands:
                details.append("{} expects one of {}".format(band, list(missing_bands[band])))
        raise ValueError(
            "RADCOR MSI fail-fast: missing required {} variables. {}".format(
                toa_prefix, "; ".join(details)
            )
        )

    return band_to_var


def _derive_expected_msi_bands(ds, toa_prefix, log_path):
    ac_bands_raw = ds.attrs.get("ac_bands")
    ac_bands = _parse_msi_ac_bands(ac_bands_raw)
    if ac_bands:
        log(
            log_path,
            "RADCOR: using ACOLITE ac_bands for MSI fail-fast requirement: {}".format(ac_bands),
            indent=1,
        )
        return ac_bands

    inferred = []
    for band in MSI_BAND_ORDER:
        aliases = MSI_BAND_TO_WAVELENGTHS[band]
        if any("{}{}".format(toa_prefix, wl) in ds.variables for wl in aliases):
            inferred.append(band)

    if not inferred:
        raise ValueError(
            "RADCOR MSI fail-fast: ACOLITE ac_bands is missing and no {} variables could be mapped to MSI bands.".format(
                toa_prefix
            )
        )

    log(
        log_path,
        "RADCOR: ACOLITE ac_bands missing, inferred MSI fail-fast requirement from available {} variables: {}".format(
            toa_prefix, inferred
        ),
        indent=1,
    )
    return inferred


def _apply_msi_band_update(ds, tmp_dir, band, rhotc_var, src_gt, log_path):
    jp2 = find_s2_jp2(tmp_dir, band)
    resamp = gdal.GRA_NearestNeighbour if band in MSI_BANDS_10M else gdal.GRA_Average
    resamp_name = "nearest" if band in MSI_BANDS_10M else "average"
    log(log_path, "RADCOR: {} uses {} (resampling: {})".format(band, rhotc_var, resamp_name), indent=2)
    rho_acolite = ds[rhotc_var].values
    rho_reprojected = reproject_to_band(rho_acolite, src_gt, jp2, resamp, log_path=log_path)
    dn_sub, mask = float_to_uint16(rho_reprojected)
    if not mask.any():
        raise ValueError(
            "RADCOR MSI fail-fast: no valid pixels available to update {} using {}.".format(
                band, rhotc_var
            )
        )
    update_band(jp2, dn_sub, mask)
    return band


def _process_msi_fail_fast(env, tmp_dir, acolite_file, toa_prefix):
    ds = xr.open_dataset(acolite_file)
    try:
        src_gt = _build_msi_src_geotransform(ds)

        rhotc_variables = _list_rhotc_variables(ds, toa_prefix)
        if not rhotc_variables:
            raise ValueError("RADCOR MSI fail-fast: no {} variables found in ACOLITE L2R output.".format(toa_prefix))
        log(
            env["General"]["log"],
            "RADCOR: detected {} {} variables in ACOLITE L2R: {}".format(
                len(rhotc_variables), toa_prefix, rhotc_variables
            ),
            indent=1,
        )

        bands_expected = _derive_expected_msi_bands(ds, toa_prefix, env["General"]["log"])
        band_to_var = _resolve_msi_band_to_variable(ds, toa_prefix, bands_expected, env["General"]["log"])
        log(
            env["General"]["log"],
            "RADCOR: MSI resampling policy is nearest for B02, B03, B04, B08 and average for other bands.",
            indent=1,
        )
        log(
            env["General"]["log"],
            "RADCOR: attempting adjacency correction for {} radiance band files using {} variables".format(
                len(bands_expected), toa_prefix
            ),
            indent=1,
        )

        processed_bands = []
        for band in bands_expected:
            processed_bands.append(
                _apply_msi_band_update(ds, tmp_dir, band, band_to_var[band], src_gt, env["General"]["log"])
            )

        if set(processed_bands) != set(bands_expected):
            missing_after = sorted(set(bands_expected) - set(processed_bands))
            raise ValueError(
                "RADCOR MSI fail-fast: bands were not adjacency-corrected: {}".format(missing_after)
            )

        log(env["General"]["log"], "RADCOR: adjacency-corrected bands: {}".format(processed_bands), indent=1)
    finally:
        ds.close()

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

    wf = _select_acolite_output(out_path, product_id, "_L2W.nc")
    acolite_l2w_file = None
    if wf:
        acolite_l2w_file = os.path.join(out_path, wf)

    log(env["General"]["log"], "RADCOR: using ACOLITE adjacency-corrected reflectances (prefix rhotc_)", indent=1)
    log(env["General"]["log"], "Selected ACOLITE L2R output (rhotc_): {}".format(rf), indent=1)
    if acolite_l2w_file:
        log(env["General"]["log"], "RADCOR: L2W found for metadata fallback: {}".format(wf), indent=1)
    else:
        log(env["General"]["log"], "RADCOR: no unique L2W found for metadata fallback", indent=1)

    tmp_dir = os.path.join(out_path, "tmp", os.path.basename(l1product_path))

    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir)

    shutil.copytree(l1product_path, tmp_dir)

    if sensor == "OLCI":
        rad_nc = netCDF4.Dataset(acolite_file)

        rhotc_wavelengths = []
        for var_name in rad_nc.variables:
            if not var_name.startswith(toa_prefix):
                continue
            wl = _parse_wavelength(var_name[len(toa_prefix):])
            if wl is None:
                continue
            rhotc_wavelengths.append(wl)
        rhotc_wavelengths = sorted(set(rhotc_wavelengths))
        log(
            env["General"]["log"],
            "RADCOR: detected {} rhotc_ bands in ACOLITE L2R: {}".format(
                len(rhotc_wavelengths), rhotc_wavelengths
            ),
            indent=1,
        )

        ac_bands = _parse_ac_bands(getattr(rad_nc, "ac_bands", None))
        ac_bands_source = "L2R"
        if ac_bands is None:
            ac_bands_source = "L2W"
            if acolite_l2w_file:
                with netCDF4.Dataset(acolite_l2w_file) as nc_w:
                    ac_bands = _parse_ac_bands(getattr(nc_w, "ac_bands", None))

        keep_bands = set()
        if ac_bands:
            keep_bands = set(ac_bands)
            log(
                env["General"]["log"],
                "RADCOR: selecting radiance bands from ACOLITE ac_bands ({}) : {}".format(
                    ac_bands_source, sorted(keep_bands)
                ),
                indent=1,
            )
        else:
            log(
                env["General"]["log"],
                "RADCOR: ac_bands not found in L2R or L2W. No radiance bands will be adjacency-corrected.",
                indent=1,
            )

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

        rhotc_tolerance_nm = _read_float_param(
            params[PARAMS_SECTION],
            "radcor_rhotc_tolerance_nm",
            2.0,
            log_path=env["General"]["log"],
        )

        files = [f for f in os.listdir(tmp_dir) if f.endswith("_radiance.nc")]
        files.sort()
        files = [f for f in files if f.split("_", 1)[0] in keep_bands]

        corrected_bands = []
        skipped_bands = {}

        log(
            env["General"]["log"],
            "RADCOR: attempting adjacency correction for {} radiance band files using {} variables".format(
                len(files), toa_prefix
            ),
            indent=1,
        )

        for file in files:
            band = file.split("_", 1)[0]
            band_index = int(band[2:]) - 1

            rad_band = getattr(rad_nc, "{}_name".format(band), None)
            if rad_band is None:
                skipped_bands[band] = "missing {}_name attribute in ACOLITE file".format(band)
                continue

            try:
                rhotc_var = _select_rhotc_variable(
                    rad_nc,
                    toa_prefix,
                    rad_band,
                    log_path=None,
                    tolerance_nm=rhotc_tolerance_nm,
                )
            except KeyError as e:
                skipped_bands[band] = str(e)
                continue

            log(
                env["General"]["log"],
                "RADCOR: {} uses {}".format(band, rhotc_var),
                indent=2,
            )

            p_t = np.array(rad_nc.variables[rhotc_var][:])[rad_indices[:, 0], rad_indices[:, 1]]
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

            corrected_bands.append(band)

        log(
            env["General"]["log"],
            "RADCOR: adjacency-corrected bands: {}".format(sorted(corrected_bands)),
            indent=1,
        )

        if skipped_bands:
            log(
                env["General"]["log"],
                "RADCOR: bands kept as ORIGINAL radiance (not adjacency-corrected):",
                indent=1,
            )
            for band in sorted(skipped_bands.keys()):
                log(
                    env["General"]["log"],
                    "{} skipped: {}".format(band, skipped_bands[band]),
                    indent=2,
                )

        rad_nc.close()
    elif sensor == "MSI":
        if int(resolution) != int(20):
            raise ValueError("RADCOR for MSI only implemented for 20m")
        _process_msi_fail_fast(env, tmp_dir, acolite_file, toa_prefix)
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

    for line in lines:
        match = key_value_pattern.match(line)
        if match:
            key = match.group(1).strip()
            value = match.group(2).strip()
            comment = match.group(4) if match.group(4) else ''

            if key in parameters:
                if value != str(parameters[key]):
                    updated_lines.append(f"{key}={parameters[key]} {comment}\n")
                    updated = True
                else:
                    updated_lines.append(line)
                keys_in_file.add(key)
            else:
                updated_lines.append(line)
        else:
            updated_lines.append(line)

    if updated_lines and not updated_lines[-1].endswith("\n"):
        updated_lines[-1] = updated_lines[-1] + "\n"

    for key, value in parameters.items():
        if key not in keys_in_file:
            updated_lines.append(f"{key}={value}\n")
            updated = True

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

def reproject_to_band(rho, src_gt, tpl_jp2, resampling, log_path=None):
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
    if status != 0 and log_path:
        log(log_path, "gdal.ReprojectImage may have failed with status {}".format(status), indent=2)

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
