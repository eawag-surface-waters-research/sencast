#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess

from snappy import ProductIO

from auxil import get_sensing_date_from_prodcut_name

# The name of the xml file for gpt
from product_fun import get_lons_lats, get_reproject_params_from_wkt

GPT_XML_FILENAME = "mosaic_{}.xml"


def mosaic(env, params, product_files):
    print("Applying MOSAIC...")

    # determine the output filename
    product_filename = os.path.basename(product_files[0])
    date = get_sensing_date_from_prodcut_name(product_filename)
    output_filename = "{}_{}_mosaic.nc".format(product_filename[0:product_filename.find(date)], date + "T000000")
    output_file = os.path.join(os.path.dirname(product_files[0]), output_filename)

    # check if output already exists
    if os.path.isfile(output_file):
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
        raise RuntimeError("GPT Failed.")

    return output_file


def rewrite_xml(gpt_xml_file, product_files, wkt, resolution):
    with open(os.path.join(os.path.dirname(__file__), GPT_XML_FILENAME.format("")), "r") as f:
        xml = f.read()

    sources_str = "\n\t\t\t".join(["<source{}>{}</source{}>".format(i, "${sourceFile" + str(i) + "}", i)
                                   for i in range(len(product_files))])

    product = ProductIO.readProduct(product_files[0])
    variables_str = "\n\t\t\t\t".join(["<variable>\n\t\t\t\t\t<name>{}</name>\n\t\t\t\t\t<expression>{}</expression>"
                                       "\n\t\t\t\t</variable>".format(band_name, band_name) for band_name in
                                       product.getBandNames()])
    product.closeIO()

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
