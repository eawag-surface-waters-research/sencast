#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""The MPH Processor calculates chl-a concentrations by means of the Maximum Peak Height and specific arithmetic expressions for different water types. Flags for floating material, eucaryote/cyanobacteria dominance and an adjacency effect indicator are provided for each pixel.  The processor was originally developed for the processing of MERIS products in the BEAM toolbox. This processor has been migrated to SNAP and was extended to support OLCI products, using the same underlying algorithm which has been adapted by just replacing the MERIS bands by the corresponding OLCI bands at the same wavelength.  The algorithm requires as input data either L1b radiances or bottom-of-Rayleigh (BRR) corrected reflectances derived from the OLCI or MERIS spectral bands. A BRR product can be processed using the Rayleigh correction processor available from SNAP Desktop -> Optical --> Preprocessing, or the corresponding GPT processor. If the input is an OLCI or MERIS L1b product, the Rayleigh correction is automatically performed as a preprocessing step within the MPH processor.
Using the option to export intermediate MPH calculations allows the user to customize arithmetic expressions for calculating chl-a. Documentation with regards to MPH is
bundled with the SNAP software.
"""

import os
import subprocess
from utils.auxil import log

# Key of the params section for this processor
PARAMS_SECTION = "MPH"
# The name of the folder to which the output product will be saved
OUT_DIR = "L2MPH"
# A pattern for the name of the file to which the output product will be saved (completed with product name)
OUT_FILENAME = "L2MPH_L1P_reproj_{}.nc"
# A pattern for name of the folder to which the quicklooks will be saved (completed with band name)
QL_DIR = "L2MPH-{}"
# A pattern for the name of the file to which the quicklooks will be saved (completed with product name and band name)
QL_FILENAME = "L2MPH_L1P_reproj_{}_{}.png"
# The name of the xml file for gpt
GPT_XML_FILENAME = "mph.xml"


def process(env, params, l1product_path, l2product_files, out_path):
    """ This processor applies mph to the source product and stores the result. """

    gpt, product_name = env['General']['gpt_path'], os.path.basename(l1product_path)
    sensor, resolution, wkt = params['General']['sensor'], params['General']['resolution'], params['General']['wkt']
    validexpression = params[PARAMS_SECTION]['validexpression']

    if sensor != "OLCI":
        return

    output_file = os.path.join(out_path, OUT_DIR, OUT_FILENAME.format(product_name))
    if os.path.isfile(output_file):
        if "synchronise" in params["General"].keys() and params['General']['synchronise'] == "false":
            log(env["General"]["log"], "Removing file: ${}".format(output_file))
            os.remove(output_file)
        else:
            log(env["General"]["log"], "Skipping MPH, target already exists: {}".format(OUT_FILENAME.format(product_name)))
            return output_file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    gpt_xml_file = os.path.join(out_path, OUT_DIR, "_reproducibility", GPT_XML_FILENAME)
    if not os.path.isfile(gpt_xml_file):
        rewrite_xml(gpt_xml_file, validexpression)

    args = [gpt, gpt_xml_file, "-c", env['General']['gpt_cache_size'], "-e",
            "-SsourceFile={}".format(l2product_files['IDEPIX']), "-PoutputFile={}".format(output_file)]
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
    xml = xml.replace("${cyanoMaxValue}", str(1000.0))
    xml = xml.replace("${chlThreshForFloatFlag}", str(500.0))
    xml = xml.replace("${exportMph}", "true")
    xml = xml.replace("${applyLowPassFilter}", "false")

    os.makedirs(os.path.dirname(gpt_xml_file), exist_ok=True)
    with open(gpt_xml_file, "w") as f:
        f.write(xml)
