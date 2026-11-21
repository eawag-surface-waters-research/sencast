#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Acolite processor for atmospheric correction"""


import os
import re
import sys
import shutil
import importlib
import numpy as np
from utils.auxil import log
from constants import REPROD_DIR


# Key of the params section for this processor
from utils.product_fun import get_lons_lats

PARAMS_SECTION = "ACOLITE"
# The name of the folder to which the output product will be saved
OUT_DIR = "L2ACOLITE"
# A pattern for the name of the file to which the output product will be saved (completed with product name)
OUT_FILENAME = "L2ACOLITE_{}.nc"
# The name of the settings file for acolite
SETTINGS_FILENAME = "acolite_{}.properties"


def process(env, params, l1product_path, _, out_path):
    """This processor calls acolite for the source product and writes the result to disk. It returns the location of the output product."""

    sys.path.append(env[PARAMS_SECTION]['root_path'])
    ac = importlib.import_module("acolite.acolite")

    out_path = os.path.join(out_path, OUT_DIR)

    sensor, resolution, wkt = params['General']['sensor'], params['General']['resolution'], params['General']['wkt']
    product_name = os.path.basename(l1product_path)
    settings_sensor = normalize_settings_sensor(sensor, product_name)
    lons, lats = get_lons_lats(wkt)
    limit = "{},{},{},{}".format(min(lats), min(lons), max(lats), max(lons))
    product_id = os.path.splitext(product_name)[0]
    os.environ['EARTHDATA_u'] = env['EARTHDATA']['username']
    os.environ['EARTHDATA_p'] = env['EARTHDATA']['password']
    out_file = os.path.join(out_path, OUT_FILENAME.format(product_name).replace(".nc.nc", ".nc"))

    if os.path.isfile(out_file):
        if "overwrite" in params["General"].keys() and params['General']['overwrite'] == "true":
            log(env["General"]["log"], "Removing file: ${}".format(out_file), indent=1)
            os.remove(out_file)
        else:
            log(env["General"]["log"], "Skipping ACOLITE, target already exists: {}".format(os.path.basename(out_file)), indent=1)
            return out_file

    os.makedirs(out_path, exist_ok=True)
    settings_file = os.path.join(out_path, REPROD_DIR, SETTINGS_FILENAME.format(settings_sensor))
    if not os.path.isfile(settings_file):
        rewrite_settings_file(settings_file, settings_sensor, resolution, limit, params[PARAMS_SECTION])

    tmp_path = os.path.join(out_path, "tmp", product_id)
    if os.path.isdir(tmp_path):
        shutil.rmtree(tmp_path)
    ac.acolite_run(settings_file, l1product_path, tmp_path)

    if not os.path.isdir(tmp_path):
        raise RuntimeError("ACOLITE did not create the expected temporary output folder: {}".format(tmp_path))

    l2w_outputs = []
    projected_l2w_outputs = []
    for aco_file in os.listdir(tmp_path):
        if aco_file == REPROD_DIR:
            continue
        elif aco_file.endswith("_L2W_projected.nc"):
            projected_l2w_outputs.append(aco_file)
        elif aco_file.endswith("_L2W.nc"):
            l2w_outputs.append(aco_file)

    l2w_outputs = projected_l2w_outputs or l2w_outputs
    matching_l2w_outputs = [aco_file for aco_file in l2w_outputs if product_id in aco_file]
    if len(matching_l2w_outputs) == 1:
        selected_l2w = matching_l2w_outputs[0]
    elif len(l2w_outputs) == 1:
        selected_l2w = l2w_outputs[0]
    elif len(l2w_outputs) == 0:
        selected_l2w = None
    else:
        raise RuntimeError("ACOLITE produced multiple L2W files for {}: {}".format(product_name, l2w_outputs))

    if selected_l2w:
        log(env["General"]["log"], "Renaming Acolite L2W output file.", indent=2)
        os.rename(os.path.join(tmp_path, selected_l2w), out_file)

    if not os.path.exists(out_file):
        raise RuntimeError("The expected output file is not present: {}".format(out_file))

    stack_file = export_l2w_stack_geotiff(out_file, env)
    remove_single_band_l2w_geotiffs(out_path, stack_file, env)

    shutil.rmtree(tmp_path)

    return out_file


def export_l2w_stack_geotiff(nc_file, env):
    from netCDF4 import Dataset
    import rasterio
    from rasterio.crs import CRS
    from rasterio.transform import Affine

    tif_file = os.path.splitext(nc_file)[0] + "_L2W_stack.tif"

    with Dataset(nc_file) as ds:
        if "x" not in ds.variables or "y" not in ds.variables:
            log(env["General"]["log"], "Skipping stacked GeoTIFF export; NetCDF has no projected x/y coordinates.", indent=2)
            return None

        x = np.asarray(ds.variables["x"][:], dtype=np.float64)
        y = np.asarray(ds.variables["y"][:], dtype=np.float64)
        if x.size < 2 or y.size < 2:
            log(env["General"]["log"], "Skipping stacked GeoTIFF export; projected x/y coordinates are incomplete.", indent=2)
            return None

        band_names = l2w_stack_band_names(ds)
        if not band_names:
            log(env["General"]["log"], "Skipping stacked GeoTIFF export; no 2-D L2W bands found.", indent=2)
            return None

        crs = l2w_stack_crs(ds, band_names)
        if crs is None:
            log(env["General"]["log"], "Skipping stacked GeoTIFF export; projected CRS was not found.", indent=2)
            return None

        xres = abs(float(x[1] - x[0]))
        yres = abs(float(y[1] - y[0]))
        transform = Affine(xres, 0.0, float(x[0]) - xres / 2.0, 0.0, -yres, float(y[0]) + yres / 2.0)

        profile = {
            "driver": "GTiff",
            "height": len(y),
            "width": len(x),
            "count": len(band_names),
            "dtype": "float32",
            "crs": crs,
            "transform": transform,
            "nodata": np.nan,
            "compress": "deflate",
            "predictor": 3,
            "tiled": True,
        }

        with rasterio.open(tif_file, "w", **profile) as dst:
            for band_index, name in enumerate(band_names, start=1):
                var = ds.variables[name]
                data = np.ma.filled(var[:], np.nan).astype(np.float32)
                dst.write(data, band_index)
                dst.set_band_description(band_index, l2w_stack_band_description(name))
                dst.update_tags(
                    band_index,
                    variable=name,
                    units=getattr(var, "units", ""),
                    wavelength=str(getattr(var, "wave_nm", getattr(var, "wavelength", ""))),
                    long_name=getattr(var, "long_name", ""),
                )

    log(env["General"]["log"], "Wrote stacked ACOLITE L2W GeoTIFF: {}".format(os.path.basename(tif_file)), indent=2)
    return tif_file


def remove_single_band_l2w_geotiffs(out_path, stack_file, env):
    removed = 0
    stack_file = os.path.abspath(stack_file) if stack_file else None
    for filename in os.listdir(out_path):
        path = os.path.abspath(os.path.join(out_path, filename))
        if path == stack_file:
            continue
        if filename.lower().endswith((".tif", ".tiff")) and "_L2W_" in filename:
            os.remove(path)
            removed += 1

    if removed:
        log(env["General"]["log"], "Removed {} single-band ACOLITE L2W GeoTIFF file(s).".format(removed), indent=2)


def l2w_stack_band_names(ds):
    preferred_prefixes = ("rhot_", "rhos_", "rhow_", "Rrs_", "aot_", "chl_")
    names = []
    for name, var in ds.variables.items():
        if getattr(var, "dimensions", ()) != ("y", "x"):
            continue
        if name in ("lon", "lat"):
            continue
        if not np.issubdtype(np.dtype(var.dtype), np.number):
            continue
        if name.startswith(preferred_prefixes):
            names.append(name)
    return sorted(names, key=l2w_stack_sort_key)


def l2w_stack_sort_key(name):
    groups = ["rhot", "rhos", "rhow", "Rrs", "aot", "chl"]
    prefix, _, suffix = name.partition("_")
    try:
        group_index = groups.index(prefix)
    except ValueError:
        group_index = len(groups)
    try:
        wave = float(suffix)
    except ValueError:
        wave = float("inf")
    return group_index, wave, name


def l2w_stack_band_description(name):
    prefix, _, suffix = name.partition("_")
    if suffix and suffix.replace(".", "", 1).isdigit():
        return "{}({})".format(prefix, suffix)
    return name


def l2w_stack_crs(ds, band_names):
    from rasterio.crs import CRS

    grid_mapping = None
    for name in band_names:
        grid_mapping = getattr(ds.variables[name], "grid_mapping", None)
        if grid_mapping:
            break

    candidates = [grid_mapping, getattr(ds, "projection_key", None), "transverse_mercator"]
    for candidate in candidates:
        if candidate and candidate in ds.variables:
            crs_wkt = getattr(ds.variables[candidate], "crs_wkt", None)
            if crs_wkt:
                return CRS.from_wkt(crs_wkt)

    proj4_string = getattr(ds, "proj4_string", None)
    if proj4_string:
        return CRS.from_string(proj4_string)

    return None


def normalize_settings_sensor(sensor, product_name):
    """Map equivalent SenCast sensor selectors to the ACOLITE settings template key."""
    requested = [token.strip() for token in sensor.split(",")]
    if product_name.startswith(("LC08", "LC09")) or any(token in ["LC08", "LC09", "OLI_TIRS"] for token in requested):
        return "OLI_TIRS"
    return sensor


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
