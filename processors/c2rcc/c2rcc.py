#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess

from packages.auxil import load_properties
from packages.ql_mapping import plot_map

# Key of the params section for this processor
PARAMS_SECTION = "C2RCC"
# The name of the folder to which the output product will be saved
OUT_DIR = "L2C2RCC"
# A pattern for the name of the file to which the output product will be saved (completed with product name)
OUT_FILENAME = "L2C2RCC_{}.nc"
# A pattern for name of the folder to which the quicklooks will be saved (completed with band name)
QL_DIR = "L2C2RCC-{}"
# A pattern for the name of the file to which the quicklooks will be saved (completed with product name and band name)
QL_FILENAME = "L2C2RCC_{}_{}.png"
# The name of the xml file for gpt
GPT_XML_FILENAME = "c2rcc_{}.xml"


def process(env, params, wkt, l1_product_path, source_file, out_path):
    """ This processor applies c2rcc to the source product and stores the result. """

    print("Applying C2RCC...")
    gpt, product_name = env['General']['gpt_path'], os.path.basename(l1_product_path)
    sensor, resolution = params['General']['sensor'], params['General']['resolution']

    output_file = os.path.join(out_path, OUT_DIR, OUT_FILENAME.format(product_name))
    if os.path.isfile(output_file):
        print("Skipping C2RCC, target already exists: {}".format(OUT_FILENAME.format(product_name)))
        return output_file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    gpt_xml_file = os.path.join(out_path, GPT_XML_FILENAME.format(sensor.lower()))
    if not os.path.isfile(gpt_xml_file):
        rewrite_xml(gpt_xml_file, params)

    args = [gpt, gpt_xml_file, "-SsourceFile={}".format(source_file), "-PoutputFile={}".format(output_file)]
    if subprocess.call(args):
        raise RuntimeError("GPT Failed.")

    create_quicklooks(params, output_file, product_name, out_path, wkt)

    return output_file


def rewrite_xml(gpt_xml_file, params):
    sensor = params['General']['sensor']
    with open(os.path.join(os.path.dirname(__file__), GPT_XML_FILENAME.format(sensor.lower())), "r") as f:
        xml = f.read()

    altnn_path = params[PARAMS_SECTION]['altnn']
    if altnn_path:
        altnn_path = os.path.join(os.path.dirname(__file__), "altnn", altnn_path)

    xml = xml.replace("${validPixelExpression}", params[PARAMS_SECTION]['validexpression'])
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
    xml = xml.replace("${alternativeNNPath}", altnn_path)

    vicar_properties_filename = params[PARAMS_SECTION]['vicar_properties_filename']
    if vicar_properties_filename:
        vicar_properties_file = os.path.join(os.path.dirname(__file__), "vicarious", vicar_properties_filename)
        vicar_params = load_properties(vicar_properties_file)
        for key in vicar_params.keys():
            xml = xml.replace("${" + key + "}", vicar_params[key])

    with open(gpt_xml_file, "wb") as f:
        f.write(xml.encode())


def create_quicklooks(params, product_file, product_name, out_path, wkt):
    bands, bandmaxs = params[PARAMS_SECTION]['bands'].split(","), params[PARAMS_SECTION]['bandmaxs'].split(",")
    print("Creating quicklooks for C2RCC for bands: {}".format(bands))
    for band, bandmax in zip(bands, bandmaxs):
        bandmax = False if int(bandmax) == 0 else range(0, int(bandmax))
        ql_file = os.path.join(out_path, QL_DIR.format(band), QL_FILENAME.format(product_name, band))
        os.makedirs(os.path.dirname(ql_file), exist_ok=True)
        plot_map(product_file, ql_file, band, wkt, basemap="srtm_hillshade", param_range=bandmax)
