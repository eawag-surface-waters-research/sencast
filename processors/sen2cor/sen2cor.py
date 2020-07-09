#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess

from product_fun import get_reproject_params_from_wkt

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


def process(env, params, l1product_path, l2product_files, out_path):
    """ This processor applies sen2cor to the source product and stores the result. """

    print("Applying Sen2Cor...")
    gpt, product_name = env['General']['gpt_path'], os.path.basename(l1product_path)
    sensor, resolution, wkt = params['General']['sensor'], params['General']['resolution'], params['General']['wkt']
    validexpression = params[PARAMS_SECTION]['validexpression']

    if sensor != "MSI":
        return

    output_file = os.path.join(out_path, OUT_DIR, OUT_FILENAME.format(product_name))
    if os.path.isfile(output_file):
        print("Skipping Sen2Cor, target already exists: {}".format(OUT_FILENAME.format(product_name)))
        return output_file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    gpt_xml_file = os.path.join(out_path, OUT_DIR, "_reproducibility", GPT_XML_FILENAME)
    if not os.path.isfile(gpt_xml_file):
        rewrite_xml(gpt_xml_file, validexpression, resolution, wkt)

    args = [gpt, gpt_xml_file, "-c", env['General']['gpt_cache_size'], "-e",
            "-SsourceFile={}".format(l1product_path), "-PoutputFile={}".format(output_file)]

    if subprocess.call(args):
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
