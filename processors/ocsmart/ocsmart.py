#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""OC SMART processor for atmospheric correction http://www.rtatmocn.com/oc-smart/"""

import os
import shutil
import subprocess
from utils.auxil import log

# Key of the params section for this processor
PARAMS_SECTION = "OCSMART"
# The name of the folder to which the output product will be saved
OUT_DIR = "L2OCSMART"
# A pattern for the name of the file to which the output product will be saved (completed with product name)
OUT_FILENAME = "L2OCSMART_{}.hf"
# The name of the input file for ocsmart
SETTINGS_FILENAME = "OCSMART_Input.txt"


def process(env, params, l1product_path, _, out_path):
    """This processor calls OC SMART for the source product and writes the result to disk. It returns the location of the output product."""

    out_path = os.path.join(out_path, OUT_DIR)
    l1_path, product_name = os.path.dirname(l1product_path), os.path.basename(l1product_path)
    out_file = os.path.join(out_path, OUT_FILENAME.format(product_name))
    ocsmart_file = os.path.splitext(product_name)[0] + '_L2_OCSMART.h5'

    if os.path.isfile(out_file):
        if "overwrite" in params["General"].keys() and params['General']['overwrite'] == "true":
            log(env["General"]["log"], "Removing file: ${}".format(out_file), indent=1)
            os.remove(out_path)
        else:
            log(env["General"]["log"], "Skipping OCSMART, target already exists: {}".format(os.path.basename(out_file)), indent=1)
            return out_file

    rewrite_settings_file(os.path.join(env[PARAMS_SECTION]['root_path'], SETTINGS_FILENAME), l1_path, product_name,
                          out_path)

    cwd = os.getcwd()
    os.chdir(env[PARAMS_SECTION]['root_path'])
    subprocess.run(["python", "OCSMART.py"])
    os.chdir(cwd)

    if not os.path.exists(os.path.join(out_path, ocsmart_file)):
        raise RuntimeError("The expected output file is not present: {}".format(os.path.join(out_path, ocsmart_file)))
    else:
        os.rename(os.path.join(out_path, ocsmart_file), out_file)

    return out_file


def rewrite_settings_file(settings_file, l1_path, l1_file, l2_path):
    with open(settings_file, "w") as f:
        f.write("l1b_path = {}/\n".format(l1_path))
        f.write("file = {}\n".format(l1_file))
        f.write("geo_path = ./GEO/\n")
        f.write("l2_path = {}/\n".format(l2_path))
        f.write("solz_limit = 70.0\n")
        f.write("senz_limit = 70.0\n")
        # TODO: Add subset functionality here
    # TODO: Implement reproducibility
