#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
The Identification of Pixel Properties (IdePix) algorithm classifies pixels from Sentinel-2, Sentinel-3, MERIS,
Landsat-8, MODIS, VIIRS, Proba-V, SPOT VGT amongst others in order to define surface types.

For an overview of the processor: https://www.brockmann-consult.de/portfolio/idepix/
"""

import os
from utils.auxil import log, gpt_subprocess
from utils.product_fun import get_reproject_params_from_wkt, get_main_file_from_product_path

# Key of the params section for this processor
PARAMS_SECTION = "IDEPIX"
# The name of the folder to which the output product will be saved
OUT_DIR = "L1P"
# A pattern for the name of the file to which the output product will be saved (completed with product name)
OUT_FILENAME = "reproj_idepix_subset_{}.nc"
# A pattern for name of the folder to which the quicklooks will be saved (completed with band name)
QL_DIR = "L1P-{}"
# A pattern for the name of the file to which the quicklooks will be saved (completed with product name and band name)
QL_FILENAME = "reproj_idepix_subset_{}_{}.png"
# The name of the xml file for gpt
GPT_XML_FILENAME = "idepix_{}.xml"
# Default number of attempts for the GPT
DEFAULT_ATTEMPTS = 1
# Default timeout for the GPT (doesn't apply to last attempt) in seconds
DEFAULT_TIMEOUT = False


def process(env, params, l1product_path, _, out_path):
    """This processor applies subset, idepix, merge and reprojection to the source product and
    writes the result to disk. It returns the location of the output product."""

    gpt, product_name = env['General']['gpt_path'], os.path.basename(l1product_path)
    sensor, resolution, wkt = params['General']['sensor'], params['General']['resolution'], params['General']['wkt']

    output_file = os.path.join(out_path, OUT_DIR, OUT_FILENAME.format(product_name))
    if os.path.isfile(output_file):
        if "synchronise" in params["General"].keys() and params['General']['synchronise'] == "false":
            log(env["General"]["log"], "Removing file: ${}".format(output_file), indent=1)
            os.remove(output_file)
        else:
            log(env["General"]["log"], "Skipping IDEPIX, target already exists: {}".format(os.path.basename(output_file)), indent=1)
            return output_file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    gpt_xml_file = os.path.join(out_path, OUT_DIR, "_reproducibility", GPT_XML_FILENAME.format(sensor))
    if not os.path.isfile(gpt_xml_file):
        rewrite_xml(gpt_xml_file, sensor, resolution, wkt)

    if sensor == "OLI_TIRS":
        l1product_path = get_main_file_from_product_path(l1product_path)

    if "gpt_use_default" in env['General'] and env['General']['gpt_use_default'] == "True":
        args = [gpt, "-Dsnap.gpf.disableTileCache=true", gpt_xml_file, "-SsourceFile={}".format(l1product_path), "-PoutputFile={}".format(output_file)]
    else:
        args = [gpt, "-Dsnap.gpf.disableTileCache=true", gpt_xml_file, "-c", env['General']['gpt_cache_size'], "-e",
                "-SsourceFile={}".format(l1product_path), "-PoutputFile={}".format(output_file)]

    if PARAMS_SECTION in params and "attempts" in params[PARAMS_SECTION]:
        attempts = int(params[PARAMS_SECTION]["attempts"])
    else:
        attempts = DEFAULT_ATTEMPTS

    if PARAMS_SECTION in params and "timeout" in params[PARAMS_SECTION]:
        timeout = int(params[PARAMS_SECTION]["timeout"])
    else:
        timeout = DEFAULT_TIMEOUT

    if gpt_subprocess(args, env["General"]["log"], attempts=attempts, timeout=timeout):
        return output_file
    else:
        if os.path.exists(output_file):
            os.remove(output_file)
            log(env["General"]["log"], "Removed corrupted output file.", indent=2)
        raise RuntimeError("GPT Failed.")


def rewrite_xml(gpt_xml_file, sensor, resolution, wkt):
    with open(os.path.join(os.path.dirname(__file__), GPT_XML_FILENAME.format(sensor)), "r") as f:
        xml = f.read()

    reproject_params = get_reproject_params_from_wkt(wkt, resolution)
    xml = xml.replace("${wkt}", wkt)
    xml = xml.replace("${resolution}", resolution)
    xml = xml.replace("${easting}", reproject_params['easting'])
    xml = xml.replace("${northing}", reproject_params['northing'])
    xml = xml.replace("${pixelSizeX}", reproject_params['pixelSizeX'])
    xml = xml.replace("${pixelSizeY}", reproject_params['pixelSizeY'])
    xml = xml.replace("${width}", reproject_params['width'])
    xml = xml.replace("${height}", reproject_params['height'])

    os.makedirs(os.path.dirname(gpt_xml_file), exist_ok=True)
    with open(gpt_xml_file, "w") as f:
        f.write(xml)
