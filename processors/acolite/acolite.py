#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Acolite processor for atmospheric correction"""


import os
import re
import sys
import shutil
import importlib
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
    lons, lats = get_lons_lats(wkt)
    limit = "{},{},{},{}".format(min(lats), min(lons), max(lats), max(lons))
    product_name = os.path.basename(l1product_path)
    os.environ['EARTHDATA_u'] = env['EARTHDATA']['username']
    os.environ['EARTHDATA_p'] = env['EARTHDATA']['password']
    out_file = os.path.join(out_path, OUT_FILENAME.format(product_name))

    if os.path.isfile(out_file):
        if "overwrite" in params["General"].keys() and params['General']['overwrite'] == "true":
            log(env["General"]["log"], "Removing file: ${}".format(out_file), indent=1)
            os.remove(out_path)
        else:
            log(env["General"]["log"], "Skipping ACOLITE, target already exists: {}".format(os.path.basename(out_file)), indent=1)
            return out_file

    os.makedirs(out_path, exist_ok=True)
    settings_file = os.path.join(out_path, REPROD_DIR, SETTINGS_FILENAME.format(sensor))
    if not os.path.isfile(settings_file):
        rewrite_settings_file(settings_file, sensor, resolution, limit, params[PARAMS_SECTION])

    tmp_path = os.path.join(out_path, "tmp")
    ac.acolite_run(settings_file, l1product_path, tmp_path)

    for aco_file in os.listdir(tmp_path):
        if aco_file == REPROD_DIR:
            continue
        elif aco_file.endswith("_L2W.nc"):
            log(env["General"]["log"], "Renaming Acolite L2W output file.", indent=2)
            os.rename(os.path.join(tmp_path, aco_file), out_file)

    if not os.path.exists(out_file):
        raise RuntimeError("The expected output file is not present: {}".format(out_file))

    shutil.rmtree(tmp_path)

    return out_file


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
