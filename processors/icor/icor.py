#! /usr/bin/env python
# -*- coding: utf-8 -*-

""" iCOR preprocessor for athmospheric correction """

import os
import subprocess

from constants import REPROD_DIR


# Key of the params section for this processor
PARAMS_SECTION = "ICOR"
# The name of the folder to which the output product will be saved
OUT_DIR = "ICOR"
# A pattern for the name of the file to which the output product will be saved (completed with product name)
OUT_FILENAME = "icor_{}.nc"
# The name of the xml file for gpt
GPT_XML_FILENAME = "icor_{}.xml"


def process(env, params, l1product_path, _, out_path):
    """ This processor applies iCor to the source product and
        writes the result to disk. It returns the location of the output product. """

    print("Applying iCor...")

    gpt, product_name = env['General']['gpt_path'], os.path.basename(l1product_path)
    sensor, resolution, wkt = params['General']['sensor'], params['General']['resolution'], params['General']['wkt']
    use_product_water_mask = params[PARAMS_SECTION]['useProductWaterMask'] if 'useProductWaterMask' in params[PARAMS_SECTION] else "false"
    use_inland_water_mask = params[PARAMS_SECTION]['useInlandWaterMask'] if 'useInlandWaterMask' in params[PARAMS_SECTION] else "false"
    apply_simec_correction = params[PARAMS_SECTION]['applySimecCorrection'] if 'applySimecCorrection' in params[PARAMS_SECTION] else "false"
    glint = params[PARAMS_SECTION]['glintCorrectionPostProcessing'] if 'glintCorrectionPostProcessing' in params[PARAMS_SECTION] else "false"

    output_file = os.path.join(out_path, OUT_DIR, OUT_FILENAME.format(product_name))
    if os.path.isfile(output_file):
        if "synchronise" in params["General"].keys() and params['General']['synchronise'] == "false":
            print("Removing file: ${}".format(output_file))
            os.remove(output_file)
        else:
            print("Skipping ICOR, target already exists: {}".format(os.path.basename(output_file)))
            return output_file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    gpt_xml_file = os.path.join(out_path, OUT_DIR, REPROD_DIR, GPT_XML_FILENAME.format(sensor))
    if not os.path.isfile(gpt_xml_file):
        rewrite_xml(gpt_xml_file, sensor, os.path.dirname(output_file), use_product_water_mask, use_inland_water_mask, apply_simec_correction, glint)

    args = [gpt, gpt_xml_file, "-c", env['General']['gpt_cache_size'], "-e", "-SsourceFile={}".format(l1product_path),
            "-PoutputFile={}".format(output_file)]
    print("Calling '{}'".format(args))
    if subprocess.call(args):
        if os.path.exists(output_file):
            os.remove(output_file)
        else:
            print("No file was created.")
        raise RuntimeError("GPT Failed.")

    return output_file


def rewrite_xml(gpt_xml_file, sensor, working_folder, use_product_water_mask, use_inland_water_mask, apply_simec_correction, glint):
    with open(os.path.join(os.path.dirname(__file__), GPT_XML_FILENAME.format(sensor)), "r") as f:
        xml = f.read()

    xml = xml.replace("${workingFolder}", working_folder)
    xml = xml.replace("${useProductWaterMask}", use_product_water_mask)
    xml = xml.replace("${useInlandWaterMask}", use_inland_water_mask)
    xml = xml.replace("${applySimecCorrection}", apply_simec_correction)
    xml = xml.replace("${glintCorrectionPostProcessing}", glint)

    os.makedirs(os.path.dirname(gpt_xml_file), exist_ok=True)
    with open(gpt_xml_file, "w") as f:
        f.write(xml)
