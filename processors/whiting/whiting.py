#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Calculating whiting using equations from ...
"""

import os
import subprocess
from utils.auxil import log
from utils.product_fun import get_reproject_params_from_wkt

# Key of the params section for this processor
PARAMS_SECTION = "WHITING"
# The name of the folder to which the output product will be saved
OUT_DIR = "L2WHITING"
# A pattern for the name of the file to which the output product will be saved (completed with product name)
OUT_FILENAME = "L2WHITING_{}.nc"
# The name of the xml file for gpt
GPT_XML_FILENAME = "whiting.xml"


def process(env, params, l1product_path, l2product_files, out_path):
    """ This processor applies whiting to the source product and stores the result. """

    if not params.has_section(PARAMS_SECTION):
        raise RuntimeWarning('WHITING was not configured in parameters.')
    log(env["General"]["log"], "Applying Whiting...")

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

    product_path = os.path.basename(source_file)
    output_file = os.path.join(out_path, OUT_DIR, OUT_FILENAME.format(product_name))
    l2product_files["WHITING"] = output_file
    if os.path.isfile(output_file):
        if "synchronise" in params["General"].keys() and params['General']['synchronise'] == "false":
            log(env["General"]["log"], "Removing file: ${}".format(output_file))
            os.remove(output_file)
        else:
            log(env["General"]["log"], "Skipping WHITING, target already exists: {}".format(OUT_FILENAME.format(product_name)))
            return output_file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    gpt_xml_file = os.path.join(out_path, OUT_DIR, "_reproducibility", GPT_XML_FILENAME)
    if not os.path.isfile(gpt_xml_file):
        rewrite_xml(gpt_xml_file, validexpression)

    args = [gpt, gpt_xml_file, "-c", env['General']['gpt_cache_size'], "-e",
            "-SsourceFile={}".format(source_file), "-PoutputFile={}".format(output_file)]
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

    return output_file


def rewrite_xml(gpt_xml_file, validexpression):
    with open(os.path.join(os.path.dirname(__file__), GPT_XML_FILENAME), "r") as f:
        xml = f.read()
    xml = xml.replace("${validPixelExpression}", validexpression)
    os.makedirs(os.path.dirname(gpt_xml_file), exist_ok=True)
    with open(gpt_xml_file, "w") as f:
        f.write(xml)
