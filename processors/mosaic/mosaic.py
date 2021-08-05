#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Mosaic is SNAP algorithm to combine multiple overlapping satellite images. Documentation with regards to mosaicing is
bundled with the SNAP software.
"""

import os
import re
import subprocess

from auxil import get_sensing_date_from_product_name
from product_fun import get_lons_lats, get_reproject_params_from_wkt


# The name of the xml file for gpt
GPT_XML_FILENAME = "mosaic_{}.xml"


def mosaic(env, params, product_files):
    print("Applying MOSAIC...")
    product_filename = os.path.basename(product_files[0])
    date = get_sensing_date_from_product_name(product_filename)
    name_arr = list(filter(None, re.split('[0-9]{8}', product_filename)[0].split("_")))
    name_arr.append(date + "T")
    if "_NT_" in product_filename:
        name_arr.append("NT")
    elif "_NR_" in product_filename:
        name_arr.append("NR")
    output_filename = "Mosaic_{}.nc".format("_".join(name_arr))
    output_file = os.path.join(os.path.dirname(product_files[0]), output_filename)

    # check if output already exists
    if os.path.isfile(output_file):
        if "synchronise" in params["General"].keys() and params['General']['synchronise'] == "false":
            print("Removing file: ${}".format(output_file))
            os.remove(output_file)
        else:
            print("Skipping MOSAIC, target already exists: {}".format(os.path.basename(output_file)))
            return output_file

    # rewrite xml file for gpt
    gpt_xml_file = os.path.join(os.path.dirname(output_file), "_reproducibility", GPT_XML_FILENAME.format(date))
    if not os.path.isfile(gpt_xml_file):
        rewrite_xml(gpt_xml_file, product_files, params['General']['wkt'], params['General']['resolution'])

    # call gpt with args
    args = [env['General']['gpt_path'], gpt_xml_file, "-c", env['General']['gpt_cache_size'], "-e"]
    for i in range(len(product_files)):
        args.append("-SsourceFile{}={}".format(i, product_files[i]))
    args.append("-PoutputFile={}".format(output_file))
    if subprocess.call(args):
        if os.path.exists(output_file):
            os.remove(output_file)
        else:
            print("No file was created.")
        raise RuntimeError("GPT Failed.")

    return output_file


def rewrite_xml(gpt_xml_file, product_files, wkt, resolution):
    with open(os.path.join(os.path.dirname(__file__), GPT_XML_FILENAME.format("")), "r") as f:
        xml = f.read()

    sources_str = "\n\t\t\t".join(["<source{}>{}</source{}>".format(i, "${sourceFile" + str(i) + "}", i) for i in range(len(product_files))])

    reproject_params = get_reproject_params_from_wkt(wkt, resolution)
    lons, lats = get_lons_lats(wkt)
    xml = xml.replace("${sources}", sources_str)
    xml = xml.replace("${westBound}", str(min(lons)))
    xml = xml.replace("${northBound}", str(max(lats)))
    xml = xml.replace("${eastBound}", str(max(lons)))
    xml = xml.replace("${southBound}", str(min(lats)))
    xml = xml.replace("${pixelSizeX}", reproject_params['pixelSizeX'])
    xml = xml.replace("${pixelSizeY}", reproject_params['pixelSizeY'])

    with open(gpt_xml_file, "w") as f:
        f.write(xml)
