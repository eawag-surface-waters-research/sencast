#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
The Merge adapter combines multiple L2 products into a single file with multiple bands.
The merge is only valid for files with identical geospatial information, it is not for merging geospatially distinct regions.
"""

import os
import subprocess
from utils.auxil import log


# key of the params section for this adapter
PARAMS_SECTION = "MERGE"
# The name of the folder to which the output product will be saved
OUT_DIR = "L2MERGE"
# A pattern for the name of the file to which the output product will be saved (completed with product name)
OUT_FILENAME = "L2MERGE_{}"
# The name of the xml file for gpt
GPT_XML_FILENAME = "merge.xml"


# TODO: this should be to util and be called from the processors!
def apply(env, params, l2product_files, date):
    """Apply merge adapter.
    1. Uses snappy to merge multiple L2 files

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

    merge_processors = list(filter(None, params[PARAMS_SECTION]["merge_nc"].split(",")))

    product_path = l2product_files[merge_processors[0]]
    out_path = os.path.join(os.path.dirname(os.path.dirname(product_path)))
    gpt, product_name = os.path.basename(product_path), env['General']['gpt_path']
    slave_product_paths = [l2product_files[merge_processor] for merge_processor in merge_processors[1:]]

    output_file = os.path.join(out_path, OUT_DIR, OUT_FILENAME.format(product_name))
    l2product_files["MERGE"] = output_file
    if os.path.isfile(output_file):
        if "synchronise" in params["General"].keys() and params['General']['synchronise'] == "false":
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


def rewrite_xml(gpt_xml_file, slave_product_paths):
    with open(os.path.join(os.path.dirname(__file__), GPT_XML_FILENAME), "r") as f:
        xml = f.read()

    xml = xml.replace("${sourceProducts}", slave_product_paths)

    os.makedirs(os.path.dirname(gpt_xml_file), exist_ok=True)
    with open(gpt_xml_file, "w") as f:
        f.write(xml)
