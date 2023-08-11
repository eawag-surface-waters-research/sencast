#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Acolite processor for athmospheric correction"""

import importlib
import os
import shutil
import sys
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
    l2w_mask_wave = params[PARAMS_SECTION]['l2w_mask_wave']
    l2w_mask_threshold = params[PARAMS_SECTION]['l2w_mask_threshold']
    l2w_mask_smooth = params[PARAMS_SECTION]['l2w_mask_smooth']
    l2w_mask_cirrus_threshold = params[PARAMS_SECTION]['l2w_mask_cirrus_threshold']
    l2w_mask_negative_rhow = params[PARAMS_SECTION]['l2w_mask_negative_rhow']
    luts_reduce_dimensions = params[PARAMS_SECTION]['luts_reduce_dimensions']
    dsf_aot_estimate = params[PARAMS_SECTION]['dsf_aot_estimate']
    l2w_parameters = params[PARAMS_SECTION]['l2w_parameters']
    lons, lats = get_lons_lats(wkt)
    limit = "{},{},{},{}".format(min(lats), min(lons), max(lats), max(lons))
    product_name = os.path.basename(l1product_path)
    os.environ['EARTHDATA_u'] = env['EARTHDATA']['username']
    os.environ['EARTHDATA_p'] = env['EARTHDATA']['password']
    out_file = os.path.join(out_path, OUT_FILENAME.format(product_name))

    if os.path.isfile(out_file):
        if "synchronise" in params["General"].keys() and params['General']['synchronise'] == "false":
            log(env["General"]["log"], "Removing file: ${}".format(out_file), indent=1)
            os.remove(out_path)
        else:
            log(env["General"]["log"], "Skipping ACOLITE, target already exists: {}".format(os.path.basename(out_file)), indent=1)
            return out_file

    os.makedirs(out_path, exist_ok=True)
    settings_file = os.path.join(out_path, REPROD_DIR, SETTINGS_FILENAME.format(sensor))
    if not os.path.isfile(settings_file):
        rewrite_settings_file(settings_file, sensor, resolution, limit, l2w_mask_wave, l2w_mask_threshold,
                              l2w_mask_smooth, l2w_mask_cirrus_threshold, l2w_mask_negative_rhow,
                              luts_reduce_dimensions, dsf_aot_estimate, l2w_parameters)

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

    # TODO: merge with idepix masks

    return out_file


def rewrite_settings_file(settings_file, sensor, resolution, limit, l2w_mask_wave, l2w_mask_threshold,
                          l2w_mask_smooth, l2w_mask_cirrus_threshold, l2w_mask_negative_rhow,
                          luts_reduce_dimensions, dsf_aot_estimate, l2w_parameters):

    with open(os.path.join(os.path.dirname(__file__), SETTINGS_FILENAME.format(sensor)), "r") as f:
        text = f.read()

    text = text.replace("${limit}", limit)
    text = text.replace("${resolution}", resolution)
    text = text.replace("${l2w_mask_wave}", l2w_mask_wave)
    text = text.replace("${l2w_mask_threshold}", l2w_mask_threshold)
    text = text.replace("${l2w_mask_smooth}", l2w_mask_smooth)
    text = text.replace("${l2w_mask_cirrus_threshold}", l2w_mask_cirrus_threshold)
    text = text.replace("${l2w_mask_negative_rhow}", l2w_mask_negative_rhow)
    text = text.replace("${luts_reduce_dimensions}", luts_reduce_dimensions)
    text = text.replace("${dsf_aot_estimate}", dsf_aot_estimate)
    text = text.replace("${l2w_parameters}", l2w_parameters)

    os.makedirs(os.path.dirname(settings_file), exist_ok=True)
    with open(settings_file, "w") as f:
        f.write(text)
