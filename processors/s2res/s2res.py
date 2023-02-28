#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""This processor resamples S2 to a fixed resolution to facilitate use with further processors.
"""

import os
import subprocess
from utils.auxil import log, gpt_subprocess

PARAMS_SECTION = "L2S2RES"
# The name of the folder to which the output product will be saved
OUT_DIR = "L2S2RES"
# A pattern for the name of the file to which the output product will be saved (completed with product name)
OUT_FILENAME = "L2S2RES_{}.nc"
# The name of the xml file for gpt
GPT_XML_FILENAME = "s2res.xml"
# Default number of attempts for the GPT
DEFAULT_ATTEMPTS = 1
# Default timeout for the GPT (doesn't apply to last attempt) in seconds
DEFAULT_TIMEOUT = False


def process(env, params, l1product_path, l2product_files, out_path):
    """ This processor applies S2 resampling to the source product and stores the result. """

    gpt, product_name = env['General']['gpt_path'], os.path.basename(l1product_path)

    if "resolution" not in params["General"]:
        raise RuntimeWarning('Resolution must be defined in the parameter file.')
    resolution = params["General"]['resolution']

    source_file = l1product_path

    product_path = os.path.basename(source_file)
    output_file = os.path.join(out_path, OUT_DIR, OUT_FILENAME.format(product_name))
    l2product_files["S2RES"] = output_file
    if os.path.isfile(output_file):
        if "synchronise" in params["General"].keys() and params['General']['synchronise'] == "false":
            log(env["General"]["log"], "Removing file: ${}".format(output_file))
            os.remove(output_file)
        else:
            log(env["General"]["log"], "Skipping S2 res, target already exists: {}".format(OUT_FILENAME.format(product_name)))
            return output_file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    gpt_xml_file = os.path.join(out_path, OUT_DIR, "_reproducibility", GPT_XML_FILENAME)
    if not os.path.isfile(gpt_xml_file):
        rewrite_xml(gpt_xml_file, resolution)

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


def rewrite_xml(gpt_xml_file, resolution):
    with open(os.path.join(os.path.dirname(__file__), GPT_XML_FILENAME), "r") as f:
        xml = f.read()
    xml = xml.replace("${resolution}", resolution)
    os.makedirs(os.path.dirname(gpt_xml_file), exist_ok=True)
    with open(gpt_xml_file, "w") as f:
        f.write(xml)
