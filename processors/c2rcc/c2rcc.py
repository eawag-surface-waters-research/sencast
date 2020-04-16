#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess

from snappy import ProductIO

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


def process(gpt, wkt, source_file, product_name, out_path, sensor, params):
    """ This processor applies c2rcc to the source product and stores the result. """
    print("Applying C2RCC...")

    output_file = os.path.join(out_path, OUT_DIR, OUT_FILENAME.format(product_name))
    if os.path.isfile(output_file):
        print("Skipping C2RCC, target already exists: {}".format(OUT_FILENAME.format(product_name)))
        return output_file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    gpt_xml_file = os.path.join(out_path, GPT_XML_FILENAME.format(sensor.lower()))
    if not os.path.isfile(gpt_xml_file):
        rewrite_xml(gpt_xml_file, sensor, params[PARAMS_SECTION]['validexpression'], params[PARAMS_SECTION]['altnn'],
                    params)

    args = [gpt, gpt_xml_file,
            "-SsourceFile={}".format(source_file),
            "-PoutputFile={}".format(output_file)]

    if subprocess.call(args):
        raise RuntimeError("GPT Failed.")

    create_quicklooks(out_path, product_name, wkt, params[PARAMS_SECTION]['bands'].split(","),
                      params[PARAMS_SECTION]['bandmaxs'].split(","))

    return output_file


def rewrite_xml(gpt_xml_file, sensor, validexpression, altnn, params):
    with open(os.path.join(os.path.dirname(__file__), GPT_XML_FILENAME.format(sensor.lower())), "r") as f:
        xml = f.read()

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

    if params.has_option(PARAMS_SECTION, 'vicar_properties_filename'):
        vicar_properties_filename = params[PARAMS_SECTION]['vicar_properties_filename']
        if vicar_properties_filename:
            vicar_properties_file = os.path.join(os.path.dirname(__file__), "vicarious", vicar_properties_filename)
            vicar_params = load_properties(vicar_properties_file)
            for key in vicar_params.keys():
                xml = xml.replace("${" + key + "}", vicar_params[key])

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


def load_properties(properties_file, separator_char='=', comment_char='#'):
    """ Read a properties file into a dict. """
    properties_dict = {}
    with open(properties_file, "rt") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith(comment_char):
                key_value = line.split(separator_char)
                key = key_value[0].strip()
                value = separator_char.join(key_value[1:]).strip().strip('"')
                properties_dict[key] = value
    return properties_dict
