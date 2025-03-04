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


def process(env, params, l1product_path, _, out_path):
    """This processor calls acolite for the source product and writes the result to disk. It returns the location of the output product."""

    sys.path.append(env["ACOLITE"]['root_path'])
    ac = importlib.import_module("acolite.acolite")

    product = os.path.basename(l1product_path)
    start_date = dates_from_name(product)[0]

    sensor, resolution, wkt = params['General']['sensor'], params['General']['resolution'], params['General']['wkt']
    lons, lats = get_lons_lats(wkt)
    limit = "{},{},{},{}".format(min(lats), min(lons), max(lats), max(lons))

    out_path = os.path.join(out_path, OUT_DIR, "{}_{}".format(product[:3], start_date))
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

    rf = [f for f in os.listdir(out_path) if f.endswith("_L1R.nc")]
    if len(rf) != 1:
        raise ValueError("Cannot find correct Acolite output file.")

    tmp_dir = os.path.join(out_path, "tmp", os.path.basename(l1product_path))

    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir)

    shutil.copytree(l1product_path, tmp_dir)

    if sensor == "OLCI":
        rad_nc = netCDF4.Dataset(os.path.join(out_path, rf[0]))
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
            p_t = np.array(rad_nc.variables["rhot_{}".format(rad_band)][:])[rad_indices[:, 0], rad_indices[:, 1]]
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