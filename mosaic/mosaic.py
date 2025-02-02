#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Mosaic is SNAP algorithm to combine multiple overlapping satellite images. Documentation with regards to mosaicing is
bundled with the SNAP software.
"""

import os
import re
import subprocess

from utils.product_fun import get_lons_lats, get_sensing_date_from_product_name, get_reproject_params_from_wkt, \
    get_band_names_from_nc

# The name of the xml file for gpt
GPT_XML_FILENAME = "mosaic.xml"


def mosaic(env, params, product_files):
    product_filename = os.path.basename(product_files[0])
    date = get_sensing_date_from_product_name(product_filename)
    name_arr = list(filter(None, re.split('[0-9]{8}', product_filename)[0].split("_")))
    name_arr.append(date)
    if "_NT_" in product_filename:
        name_arr.append("_NT")
    elif "_NR_" in product_filename:
        name_arr.append("_NR")
    output_filename = "Mosaic_{}.nc".format("_".join(name_arr))
    output_file = os.path.join(os.path.dirname(product_files[0]), output_filename)

    # check if output already exists
    if os.path.isfile(output_file):
        if "overwrite" in params["General"].keys() and params['General']['overwrite'] == "true":
            print("Removing file: ${}".format(output_file))
            os.remove(output_file)
        else:
            print("Skipping MOSAIC, target already exists: {}".format(os.path.basename(output_file)))
            return output_file

    # rewrite xml file for gpt
    gpt_xml_file = os.path.join(os.path.dirname(output_file), "_reproducibility", GPT_XML_FILENAME)
    if not os.path.isfile(gpt_xml_file):
        rewrite_xml(gpt_xml_file, product_files, params['General']['sensor'], params['General']['wkt'], params['General']['resolution'])

    # call gpt with args
    args = [env['General']['gpt_path'], gpt_xml_file, "-c", env['General']['gpt_cache_size'], "-e"]
    for i in range(len(product_files)):
        args.append("-SsourceFile{}={}".format(i, product_files[i]))
    args.append("-PoutputFile={}".format(output_file))
    print("Calling [{}]...".format(" ".join(args)))
    if subprocess.call(args):
        raise RuntimeError("GPT Failed.")

    return output_file


def rewrite_xml(gpt_xml_file, product_files, sensor, wkt, resolution):
    with open(os.path.join(os.path.dirname(__file__), GPT_XML_FILENAME), "r") as f:
        xml = f.read()

    sources_str = "\n\t\t\t".join(["<source{}>{}</source{}>".format(i, "${sourceFile" + str(i) + "}", i) for i in range(len(product_files))])

    product_band_names = [get_band_names_from_nc(product_file) for product_file in product_files]
    common_band_names = product_band_names[0]
    for band_names in product_band_names[1:]:
        common_band_names = list(set(common_band_names) & set(band_names))
    variable_template = "<variable>\n\t\t\t\t\t<name>{}</name>\n\t\t\t\t\t<expression>{}</expression>\n\t\t\t\t</variable>"
    for band_name in ["lon", "lat"]:
        try:
            common_band_names.remove(band_name)
        except (Exception, ):
            pass
    variables_str = "\n\t\t\t\t".join([variable_template.format(band_name, band_name) for band_name in sorted(common_band_names)])

    reproject_params = get_reproject_params_from_wkt(wkt, resolution)
    lons, lats = get_lons_lats(wkt)
    xml = xml.replace("${sources}", sources_str)
    xml = xml.replace("${variables}", variables_str)
    xml = xml.replace("${westBound}", str(min(lons)))
    xml = xml.replace("${northBound}", str(max(lats)))
    xml = xml.replace("${eastBound}", str(max(lons)))
    xml = xml.replace("${southBound}", str(min(lats)))
    xml = xml.replace("${pixelSizeX}", reproject_params['pixelSizeX'])
    xml = xml.replace("${pixelSizeY}", reproject_params['pixelSizeY'])

    with open(gpt_xml_file, "w") as f:
        f.write(xml)
