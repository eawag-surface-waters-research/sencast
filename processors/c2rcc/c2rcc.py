#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess

from snappy import ProductIO

from packages.ql_mapping import plot_map

# The name of the folder to which the output product will be saved
OUT_DIR = "L2C2RCC"
# A pattern for the name of the file to which the output product will be saved (completed with product name)
OUT_FILENAME = "L2C2RCC_L1P_reproj_{}.nc"
# A pattern for name of the folder to which the quicklooks will be saved (completed with band name)
QL_DIR = "L2C2RCC-{}"
# A pattern for the name of the file to which the quicklooks will be saved (completed with product name and band name)
QL_FILENAME = "L2C2RCC_L1P_reproj_{}_{}.png"
# The name of the xml file for gpt
GPT_XML_FILENAME = "c2rcc.xml"


def process(gpt, wkt, source, product_name, out_path, sensor, params):
    """ This processor applies c2rcc to the source product and stores the result. """
    print("Applying C2RCC...")

    output = os.path.join(out_path, OUT_DIR, OUT_FILENAME.format(product_name))
    if os.path.isfile(output):
        print("Skipping C2RCC, target already exists: {}".format(OUT_FILENAME.format(product_name)))
        return output
    os.makedirs(os.path.dirname(output), exist_ok=True)

    gpt_xml_file = os.path.join(out_path, GPT_XML_FILENAME)
    if not os.path.isfile(gpt_xml_file):
        rewrite_xml(gpt_xml_file, sensor, params['validexpression'], params['altnn'])

    args = [gpt, gpt_xml_file,
            "-Ssource={}".format(source),
            "-Poutput={}".format(output)]

    if subprocess.call(args):
        raise RuntimeError("GPT Failed.")

    create_quicklooks(out_path, product_name, wkt, params['bands'].split(","), params['bandmaxs'].split(","))

    return output


def rewrite_xml(gpt_xml_file, sensor, validexpression, altnn):
    with open(os.path.join(os.path.dirname(__file__), GPT_XML_FILENAME), "r") as f:
        xml = f.read()

    xml = xml.replace("${c2rccOperator}", "c2rcc.olci" if sensor == "OLCI" else "c2rcc.msi")
    xml = xml.replace("${validPixelExpression}", validexpression)
    xml = xml.replace("${salinity}", str(0.05))
    xml = xml.replace("${temperature}", str(15.0))
    xml = xml.replace("${ozone}", str(330.0))  # str(product_parameters.get('ozone'))
    xml = xml.replace("${press}", str(1000.0))  # str(product_parameters.get('press'))
    xml = xml.replace("${TSMfakBpart}", str(1.72))
    xml = xml.replace("${TSMfakBwit}", str(3.1))
    xml = xml.replace("${CHLexp}", str(1.04))
    xml = xml.replace("${CHLfak}", str(21.0))
    xml = xml.replace("${thresholdRtosaOOS}", str(0.05))
    xml = xml.replace("${thresholdAcReflecOos}", str(0.1))
    xml = xml.replace("${thresholdCloudTDown865}", str(0.955))
    xml = xml.replace("${alternativeNNPath}", altnn)

    with open(gpt_xml_file, "wb") as f:
        f.write(xml.encode())


def create_quicklooks(out_path, product_name, wkt, bands, bandmaxs):
    print("Creating quicklooks for C2RCC for bands: {}".format(bands))
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
