#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess

from packages.product_fun import get_reproject_params_from_wkt
from packages.ql_mapping import plot_pic

# Key of the params section for this processor
PARAMS_SECTION = "IDEPIX"
# The name of the folder to which the output product will be saved
OUT_DIR = "L1P"
# A pattern for the name of the file to which the output product will be saved (completed with product name)
OUT_FILENAME = "reproj_idepix_subset_{}.nc"
# A pattern for name of the folder to which the quicklooks will be saved (completed with band name)
QL_DIR = "L1P-{}"
# A pattern for the name of the file to which the quicklooks will be saved (completed with product name and band name)
QL_FILENAME = "reproj_idepix_subset_{}_{}.png"
# The name of the xml file for gpt
GPT_XML_FILENAME = "idepix_{}.xml"


def process(env, params, l1_product_path, source_file, out_path):
    """ This processor applies subset, idepix, merge and reprojection to the source product and
    writes the result to disk. It returns the location of the output product. """

    print("Applying IDEPIX...")
    gpt, product_name = env['General']['gpt_path'], os.path.basename(l1_product_path)
    sensor, resolution, wkt = params['General']['sensor'], params['General']['resolution'], params['General']['wkt']

    output_file = os.path.join(out_path, OUT_DIR, OUT_FILENAME.format(product_name))
    if os.path.isfile(output_file):
        print("Skipping IDEPIX, target already exists: {}".format(os.path.basename(output_file)))
        return output_file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    gpt_xml_file = os.path.join(out_path, OUT_DIR, "_reproducibility", GPT_XML_FILENAME.format(sensor))
    if not os.path.isfile(gpt_xml_file):
        rewrite_xml(gpt_xml_file, sensor, resolution, wkt)

    args = [gpt, gpt_xml_file, "-c", env['General']['gpt_cache_size'], "-e", "-SsourceFile={}".format(source_file),
            "-PoutputFile={}".format(output_file)]
    if subprocess.call(args):
        raise RuntimeError("GPT Failed.")

    rgb_bands = params[PARAMS_SECTION]['rgb_bands'].split(",")
    fc_bands = params[PARAMS_SECTION]['fc_bands'].split(",")
    if params['General']['sensor'] == "OLCI":
        rgb_bands = [bn.replace('radiance', 'reflectance') for bn in rgb_bands]
        fc_bands = [bn.replace('radiance', 'reflectance') for bn in fc_bands]
    create_quicklooks(output_file, product_name, out_path, wkt, rgb_bands, fc_bands)

    return output_file


def rewrite_xml(gpt_xml_file, sensor, resolution, wkt):
    with open(os.path.join(os.path.dirname(__file__), GPT_XML_FILENAME.format(sensor)), "r") as f:
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

    os.makedirs(os.path.dirname(gpt_xml_file), exist_ok=True)
    with open(gpt_xml_file, "w") as f:
        f.write(xml)


def create_quicklooks(product_file, product_name, out_path, wkt, rgb_bands, fc_bands):
    print("Creating quicklooks for IDEPIX")
    ql_file = os.path.join(out_path, QL_DIR.format("rgb"), QL_FILENAME.format(product_name, "rgb"))
    os.makedirs(os.path.dirname(ql_file), exist_ok=True)
    plot_pic(product_file, ql_file, wkt=wkt, rgb_layers=rgb_bands, max_val=0.16)
    ql_file = os.path.join(out_path, QL_DIR.format("fc"), QL_FILENAME.format(product_name, "fc"))
    os.makedirs(os.path.dirname(ql_file), exist_ok=True)
    plot_pic(product_file, ql_file, wkt=wkt, rgb_layers=fc_bands, max_val=0.3)
