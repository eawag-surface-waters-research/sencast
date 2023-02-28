#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Sen2Cor is a processor for Sentinel-2 Level 2A product generation and formatting; it performs the atmospheric-,
terrain and cirrus correction of Top-Of- Atmosphere Level 1C input data. Sen2Cor creates Bottom-Of-Atmosphere,
optionally terrain- and cirrus corrected reflectance images; additional, Aerosol Optical Thickness-, Water Vapor-,
Scene Classification Maps and Quality Indicators for cloud and snow probabilities. Its output product format is
equivalent to the Level 1C User Product: JPEG 2000 images, three different resolutions, 60, 20 and 10 m.

For an overview of the processor: https://step.esa.int/main/third-party-plugins-2/sen2cor/
"""

import os
import subprocess
from utils.auxil import log, gpt_subprocess
from utils.product_fun import get_reproject_params_from_wkt

# Key of the params section for this processor
PARAMS_SECTION = "SEN2COR"
# The name of the folder to which the output product will be saved
OUT_DIR = "L2SEN2COR"
# A pattern for the name of the file to which the output product will be saved (completed with product name)
OUT_FILENAME = "L2SEN2COR_L1P_reproj_{}.nc"
# A pattern for name of the folder to which the quicklooks will be saved (completed with band name)
QL_DIR = "L2SEN2COR-{}"
# A pattern for the name of the file to which the quicklooks will be saved (completed with product name and band name)
QL_FILENAME = "L2SEN2COR_L1P_reproj_{}_{}.png"
# The name of the xml file for gpt
GPT_XML_FILENAME = "sen2cor.xml"
# Default number of attempts for the GPT
DEFAULT_ATTEMPTS = 1
# Default timeout for the GPT (doesn't apply to last attempt) in seconds
DEFAULT_TIMEOUT = False

def process(env, params, l1product_path, l2product_files, out_path):
    """ This processor applies sen2cor to the source product and stores the result. """

    gpt, product_name = env['General']['gpt_path'], os.path.basename(l1product_path)
    sensor, resolution, wkt = params['General']['sensor'], params['General']['resolution'], params['General']['wkt']
    validexpression = params[PARAMS_SECTION]['validexpression']

    if "MSI" not in sensor:
        return

    output_file = os.path.join(out_path, OUT_DIR, OUT_FILENAME.format(product_name))
    if os.path.isfile(output_file):
        if "synchronise" in params["General"].keys() and params['General']['synchronise'] == "false":
            log(env["General"]["log"], "Removing file: ${}".format(output_file))
            os.remove(output_file)
        else:
            log(env["General"]["log"], "Skipping Sen2Cor, target already exists: {}".format(OUT_FILENAME.format(product_name)))
            return output_file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    gpt_xml_file = os.path.join(out_path, OUT_DIR, "_reproducibility", GPT_XML_FILENAME)
    if not os.path.isfile(gpt_xml_file):
        rewrite_xml(gpt_xml_file, validexpression, resolution, wkt)

    args = [gpt, gpt_xml_file, "-c", env['General']['gpt_cache_size'], "-e",
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

    return output_file


def rewrite_xml(gpt_xml_file, validexpression, resolution, wkt):
    with open(os.path.join(os.path.dirname(__file__), GPT_XML_FILENAME), "r") as f:
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
    xml = xml.replace("${validPixelExpression}", validexpression)

    os.makedirs(os.path.dirname(gpt_xml_file), exist_ok=True)
    with open(gpt_xml_file, "w") as f:
        f.write(xml)
