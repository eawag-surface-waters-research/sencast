#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess
from utils.auxil import log, gpt_subprocess

# Key of the params section for this processor
PARAMS_SECTION = "L_FLUO"
# The name of the folder to which the output product will be saved
OUT_DIR = "L2FLUO"
# A pattern for the name of the file to which the output product will be saved (completed with product name)
OUT_FILENAME = "L_FLUO_{}.nc"
# A pattern for name of the folder to which the quicklooks will be saved (completed with band name)
QL_DIR = "L2FLUO-{}"
# A pattern for the name of the file to which the quicklooks will be saved (completed with product name and band name)
QL_FILENAME = "L_FLUO_{}_{}.png"
# The name of the xml file for gpt
GPT_XML_FILENAME = "l_fluo.xml"
# Default number of attempts for the GPT
DEFAULT_ATTEMPTS = 1
# Default timeout for the GPT (doesn't apply to last attempt) in seconds
DEFAULT_TIMEOUT = False


def process(env, params, l1product_path, l2product_files, out_path):
    """This processor applies the fluorescence processor to a radiance source product and stores the result."""

    gpt, product_name = env['General']['gpt_path'], os.path.basename(l1product_path)
    validexpression = params[PARAMS_SECTION]['validexpression']

    output_file = os.path.join(out_path, OUT_DIR, OUT_FILENAME.format(product_name))
    if os.path.isfile(output_file):
        if "synchronise" in params["General"].keys() and params['General']['synchronise'] == "false":
            log(env["General"]["log"], "Removing file: ${}".format(output_file))
            os.remove(output_file)
        else:
            log(env["General"]["log"], "Skipping L-FLUO, target already exists: {}".format(OUT_FILENAME.format(product_name)))
            return output_file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    gpt_xml_file = os.path.join(out_path, OUT_DIR, "_reproducibility", GPT_XML_FILENAME)
    if not os.path.isfile(gpt_xml_file):
        rewrite_xml(gpt_xml_file, validexpression)

    args = [gpt, gpt_xml_file, "-c", env['General']['gpt_cache_size'], "-e",
            "-SsourceFile={}".format(l2product_files['IDEPIX']), "-PoutputFile={}".format(output_file)]

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


def rewrite_xml(gpt_xml_file, validexpression):
    with open(os.path.join(os.path.dirname(__file__), GPT_XML_FILENAME), "r") as f:
        xml = f.read()

    xml = xml.replace("${validPixelExpression}", validexpression)

    os.makedirs(os.path.dirname(gpt_xml_file), exist_ok=True)
    with open(gpt_xml_file, "w") as f:
        f.write(xml)
