#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
from utils.auxil import load_environment, log
import subprocess

# The name of the xml file for gpt
GPT_XML_FILENAME = "pixelextraction.xml"

# key of the params section for this adapter
PARAMS_SECTION = "PIXELEXTRACTION"
OUT_DIR = "PixelExtraction"


def apply(env, params, l2product_files, date):
    """Apply Pixel Extraction.

    Parameters
    -------------

    env
        Dictionary of environment parameters, loaded from input file
    params
        Dictionary of parameters, loaded from input file
    l2product_files
        Dictionary of Level 2 product files created by processors
    date
        Run date
    """

    gpt = env['General']['gpt_path']

    if PARAMS_SECTION not in params:
        raise ValueError("PIXEL section must be defined in the parameters file.")

    window_size = 1
    if "window_size" in params[PARAMS_SECTION]:
        window_size = params[PARAMS_SECTION]["window_size"]

    if "coordinates" not in params[PARAMS_SECTION]:
        raise ValueError("Coordinates must be defined in the PIXEL section.")
    coords = params[PARAMS_SECTION]["coordinates"].replace(" ", "").split("],[")
    coords = [coord.replace("[", "").replace("]", "").split(",") for coord in coords]

    if "products" not in params[PARAMS_SECTION]:
        raise ValueError("Products must be defined in the PIXEL section.")

    files = []
    for product in params[PARAMS_SECTION]["products"].replace(" ", "").split(","):
        if product.upper() in l2product_files.keys():
            files.append(l2product_files[product.upper()])

    if len(files) == 0:
        return

    out_path = os.path.dirname(os.path.dirname(files[0]))
    gpt_xml_file = os.path.join(out_path, OUT_DIR, "_reproducibility", GPT_XML_FILENAME)

    if not os.path.isfile(gpt_xml_file):
        rewrite_xml(gpt_xml_file, files, os.path.join(out_path, OUT_DIR), coords, window_size)

    args = [gpt, gpt_xml_file, "-c", env['General']['gpt_cache_size']]
    log(env["General"]["log"], "Calling '{}'".format(args), indent=1)

    process = subprocess.Popen(args, stdout=subprocess.PIPE, universal_newlines=True)
    while True:
        output = process.stdout.readline()
        log(env["General"]["log"], output.strip(), indent=2)
        return_code = process.poll()
        if return_code is not None:
            if return_code != 0:
                raise RuntimeError("GPT Failed.")
            break


def rewrite_xml(gpt_xml_file, files, folder, coords, window_size):
    with open(os.path.join(os.path.dirname(__file__), GPT_XML_FILENAME), "r") as f:
        xml = f.read()

    coords_arr = []
    for i in range(len(coords)):
        coords_arr.append(
            "<coordinate><name>{}</name><latitude>{}</latitude><longitude>{"
            "}</longitude><originalValues/><id>0</id></coordinate>".format(
                i, coords[i][0], coords[i][1]))

    xml = xml.replace("${sourceproductpaths}", ",".join(files))
    xml = xml.replace("${coordinates}", "".join(coords_arr))
    xml = xml.replace("${outputdir}", folder)
    xml = xml.replace("${windowsize)", str(window_size))

    os.makedirs(os.path.dirname(gpt_xml_file), exist_ok=True)
    with open(gpt_xml_file, "w") as f:
        f.write(xml)

