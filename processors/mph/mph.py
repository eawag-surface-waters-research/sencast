#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess

from snappy import ProductIO

from packages.ql_mapping import plot_map

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


def process(gpt, wkt, source, product_name, out_path, sensor, params):
    """ This processor applies mph to the source product and stores the result. """
    print("Applying MPH...")

    if sensor != "OLCI":
        return

    output = os.path.join(out_path, OUT_DIR, OUT_FILENAME.format(product_name))
    if os.path.isfile(output):
        print("Skipping MPH, target already exists: {}".format(OUT_FILENAME.format(product_name)))
        return output
    os.makedirs(os.path.dirname(output), exist_ok=True)

    gpt_xml_file = os.path.join(out_path, GPT_XML_FILENAME)
    if not os.path.isfile(gpt_xml_file):
        rewrite_xml(gpt_xml_file, params['validexpression'])

    args = [gpt, gpt_xml_file,
            "-Ssource={}".format(source),
            "-Poutput={}".format(output)]

    if subprocess.call(args):
        raise RuntimeError("GPT Failed.")

    create_quicklooks(out_path, product_name, wkt, params['bands'].split(","), params['bandmaxs'].split(","))

    return output


def rewrite_xml(gpt_xml_file, validexpression):
    with open(os.path.join(os.path.dirname(__file__), GPT_XML_FILENAME), "r") as f:
        xml = f.read()

    xml = xml.replace("${validPixelExpression}", validexpression)
    xml = xml.replace("${cyanoMaxValue}", str(1000.0))
    xml = xml.replace("${chlThreshForFloatFlag}", str(500.0))
    xml = xml.replace("${exportMph}", "true")
    xml = xml.replace("${applyLowPassFilter}", "false")

    with open(gpt_xml_file, "wb") as f:
        f.write(xml.encode())


def create_quicklooks(out_path, product_name, wkt, bands, bandmaxs):
    print("Creating quicklooks for MPH for bands: {}".format(bands))
    product = ProductIO.readProduct(os.path.join(out_path, OUT_DIR, OUT_FILENAME.format(product_name)))
    for band, bandmax in zip(bands, bandmaxs):
        if int(bandmax) == 0:
            bandmax = False
        else:
            bandmax = range(0, int(bandmax))
        ql_file = os.path.join(out_path, QL_DIR.format(band), QL_FILENAME.format(product_name, band))
        os.makedirs(os.path.dirname(ql_file), exist_ok=True)
        plot_map(product, ql_file, band, basemap="srtm_hillshade", grid=True, wkt=wkt, param_range=bandmax)
        print("Plot for band {} finished.".format(band))
    product.closeIO()
