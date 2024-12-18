#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
The Merge adapter combines multiple L2 products into a single file with multiple bands.
The merge is only valid for files with identical geospatial information, it is not for merging geospatially distinct regions.
"""

import os
import subprocess
from utils.auxil import log, gpt_subprocess


# key of the params section for this adapter
PARAMS_SECTION = "MERGE"
# The name of the folder to which the output product will be saved
OUT_DIR = "L2MERGE"
# A pattern for the name of the file to which the output product will be saved (completed with product name)
OUT_FILENAME = "L2MERGE_{}"
# The name of the xml file for gpt
GPT_XML_FILENAME = "merge.xml"
# Default number of attempts for the GPT
DEFAULT_ATTEMPTS = 1
# Default timeout for the GPT (doesn't apply to last attempt) in seconds
DEFAULT_TIMEOUT = False


def apply(env, params, l2product_files, date):
    """Apply merge processor.
    1. Uses gpt to merge multiple L2 files

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
    if not params.has_section(PARAMS_SECTION):
        raise RuntimeWarning("Merge was not configured in parameters.")
    log(env["General"]["log"], "Applying Merge...")

    if "merge_nc" not in params[PARAMS_SECTION]:
        raise RuntimeWarning("Merge files must be defined in the parameter file under the merge_nc key.")

    merge_processors = list(filter(None, params[PARAMS_SECTION]["processors"].split(",")))

    product_path = l2product_files[merge_processors[0]]
    out_path = os.path.join(os.path.dirname(os.path.dirname(product_path)))
    gpt, product_name = os.path.basename(product_path), env['General']['gpt_path']
    slave_product_paths = ', '.join([l2product_files[merge_processor] for merge_processor in merge_processors[1:]])

    output_file = os.path.join(out_path, OUT_DIR, OUT_FILENAME.format(product_name))
    if os.path.isfile(output_file):
        if "overwrite" in params["General"].keys() and params['General']['overwrite'] == "true":
            log(env["General"]["log"], "Removing file: ${}".format(output_file))
            os.remove(output_file)
        else:
            log(env["General"]["log"], "Skipping Merge, target already exists: {}".format(output_file))
            return output_file
    os.makedirs(out_path, exist_ok=True)

    gpt_xml_file = os.path.join(out_path, OUT_DIR, "_reproducibility", GPT_XML_FILENAME)
    if not os.path.isfile(gpt_xml_file):
        rewrite_xml(gpt_xml_file, slave_product_paths)

    args = [gpt, gpt_xml_file, "-c", env['General']['gpt_cache_size'], "-e", "-SmasterProduct={}".format(product_path)]
    log(env["General"]["log"], "Calling '{}'".format(args), indent=1)

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


def rewrite_xml(gpt_xml_file, slave_product_paths):
    with open(os.path.join(os.path.dirname(__file__), GPT_XML_FILENAME), "r") as f:
        xml = f.read()

    xml = xml.replace("${sourceProducts}", slave_product_paths)

    os.makedirs(os.path.dirname(gpt_xml_file), exist_ok=True)
    with open(gpt_xml_file, "w") as f:
        f.write(xml)
