#! /usr/bin/env python
# -*- coding: utf-8 -*-

""" Acolite preprocessor for athmospheric correction """

import importlib
import os
import sys

from constants import REPROD_DIR


# Key of the params section for this processor
from utils.product_fun import get_lons_lats

PARAMS_SECTION = "ACOLITE"
# The name of the folder to which the output product will be saved
OUT_DIR = "ACOLITE"
# The name of the settings file for acolite
SETTINGS_FILENAME = "acolite_{}.properties"


def process(env, params, l1product_path, _, out_path):
    """ This processor calls acolite for the source product and
        writes the result to disk. It returns the location of the output product. """

    sys.path.append(env[PARAMS_SECTION]['root_path'])
    ac = importlib.import_module("acolite.acolite")

    sensor, resolution, wkt = params['General']['sensor'], params['General']['resolution'], params['General']['wkt']
    l2w_mask_wave, l2w_mask_threshold = params[PARAMS_SECTION]['l2w_mask_wave'], params[PARAMS_SECTION]['l2w_mask_threshold']
    l2w_mask_smooth = params[PARAMS_SECTION]['l2w_mask_smooth']
    lons, lats = get_lons_lats(wkt)
    limit = "{},{},{},{}".format(min(lats), min(lons), max(lats), max(lons))

    if os.path.isdir(os.path.join(out_path, OUT_DIR)):
        if "synchronise" in params["General"].keys() and params['General']['synchronise'] == "false":
            print("Removing file: ${}".format(os.path.join(out_path, OUT_DIR)))
            os.remove(os.path.join(out_path, OUT_DIR))
    os.makedirs(os.path.dirname(os.path.join(out_path, OUT_DIR)), exist_ok=True)

    settings_file = os.path.join(out_path, OUT_DIR, REPROD_DIR, SETTINGS_FILENAME.format(sensor))
    if not os.path.isfile(settings_file):
        rewrite_settings_file(settings_file, sensor, resolution, limit, l2w_mask_wave, l2w_mask_threshold, l2w_mask_smooth)

    ac.acolite_run(settings_file, l1product_path, os.path.join(out_path, OUT_DIR))

    return os.path.join(out_path, OUT_DIR)


def rewrite_settings_file(settings_file, sensor, resolution, limit, l2w_mask_wave, l2w_mask_threshold, l2w_mask_smooth):
    with open(os.path.join(os.path.dirname(__file__), SETTINGS_FILENAME.format(sensor)), "r") as f:
        text = f.read()

    text = text.replace("${limit}", limit)
    text = text.replace("${resolution}", resolution)
    text = text.replace("${l2w_mask_wave}", l2w_mask_wave)
    text = text.replace("${l2w_mask_threshold}", l2w_mask_threshold)
    text = text.replace("${l2w_mask_smooth}", l2w_mask_smooth)

    os.makedirs(os.path.dirname(settings_file), exist_ok=True)
    with open(settings_file, "w") as f:
        f.write(text)
