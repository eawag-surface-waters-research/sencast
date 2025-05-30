#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""The Normalized Difference Water Index (NDWI) (Gao, 1996) is a satellite-derived index from the
Near-Infrared (NIR) and Short Wave Infrared (SWIR) channels.
"""

import os
from utils.auxil import log, gpt_subprocess

# Key of the params section for this processor
PARAMS_SECTION = "NDWI"
# The name of the folder to which the output product will be saved
OUT_DIR = "L2NDWI"
# A pattern for the name of the file to which the output product will be saved (completed with product name)
OUT_FILENAME = "L2NDWI_{}.nc"
# The name of the xml file for gpt
GPT_XML_FILENAME = "ndwi.xml"
# Default number of attempts for the GPT
DEFAULT_ATTEMPTS = 1
# Default timeout for the GPT (doesn't apply to last attempt) in seconds
DEFAULT_TIMEOUT = False

def process(env, params, l1product_path, l2product_files, out_path):
    """ This processor applies NDWI to the source product and stores the result. """

    if not params.has_section(PARAMS_SECTION):
        raise RuntimeWarning('NDWI was not configured in parameters.')
    log(env["General"]["log"], "Applying NDWI...")

    gpt, product_name = env['General']['gpt_path'], os.path.basename(l1product_path)

    if "processor" not in params[PARAMS_SECTION]:
        raise RuntimeWarning('processor must be defined in the parameter file.')
    processor = params[PARAMS_SECTION]['processor']

    if processor == "l1":
        source_file = l1product_path
    else:
        source_file = l2product_files[processor]

    validexpression = ""
    if "validexpression" in params[PARAMS_SECTION]:
        validexpression = params[PARAMS_SECTION]['validexpression']

    if "green_band" not in params[PARAMS_SECTION]:
        raise RuntimeWarning('green_band must be defined in the parameter file.')
    green = params[PARAMS_SECTION]['green_band']

    if "nir_band" not in params[PARAMS_SECTION]:
        raise RuntimeWarning('nir_band must be defined in the parameter file.')
    nir = params[PARAMS_SECTION]['nir_band']

    product_path = os.path.basename(source_file)
    output_file = os.path.join(out_path, OUT_DIR, OUT_FILENAME.format(product_name))
    l2product_files["NDWI"] = output_file
    if os.path.isfile(output_file):
        if "overwrite" in params["General"].keys() and params['General']['overwrite'] == "true":
            log(env["General"]["log"], "Removing file: ${}".format(output_file))
            os.remove(output_file)
        else:
            log(env["General"]["log"], "Skipping NDWI, target already exists: {}".format(OUT_FILENAME.format(product_name)))
            return output_file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    gpt_xml_file = os.path.join(out_path, OUT_DIR, "_reproducibility", GPT_XML_FILENAME)
    if not os.path.isfile(gpt_xml_file):
        rewrite_xml(gpt_xml_file, validexpression, green, nir)

    args = [gpt, gpt_xml_file, "-c", env['General']['gpt_cache_size'], "-e",
            "-SsourceFile={}".format(source_file), "-PoutputFile={}".format(output_file)]

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


def rewrite_xml(gpt_xml_file, validexpression, green, nir):
    with open(os.path.join(os.path.dirname(__file__), GPT_XML_FILENAME), "r") as f:
        xml = f.read()
    xml = xml.replace("${green}", green)
    xml = xml.replace("${nir}", nir)
    xml = xml.replace("${validPixelExpression}", validexpression)
    os.makedirs(os.path.dirname(gpt_xml_file), exist_ok=True)
    with open(gpt_xml_file, "w") as f:
        f.write(xml)
