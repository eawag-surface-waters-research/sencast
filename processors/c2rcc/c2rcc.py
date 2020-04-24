#! /usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import os
import re
import subprocess

# from polymer.ancillary_era import Ancillary_ERA
from polymer.ancillary_era5 import Ancillary_ERA5

from auxil import load_properties
from product_fun import get_lons_lats

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
GPT_XML_FILENAME = "c2rcc_{}_{}.xml"


def process(env, params, l1_product_path, source_file, out_path):
    """ This processor applies c2rcc to the source product and stores the result. """

    print("Applying C2RCC...")
    gpt, product_name = env['General']['gpt_path'], os.path.basename(l1_product_path)
    sensor, resolution, wkt = params['General']['sensor'], params['General']['resolution'], params['General']['wkt']
    altnn, validexpression = params[PARAMS_SECTION]['altnn'], params[PARAMS_SECTION]['validexpression']
    vicar_properties_filename = params[PARAMS_SECTION]['vicar_properties_filename']
    date_str = re.findall(r"\d{8}T\d{6}", product_name)[0]

    output_file = os.path.join(out_path, OUT_DIR, OUT_FILENAME.format(product_name))
    if os.path.isfile(output_file):
        print("Skipping C2RCC, target already exists: {}".format(OUT_FILENAME.format(product_name)))
        return output_file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    gpt_xml_file = os.path.join(out_path, OUT_DIR, "_reproducibility", GPT_XML_FILENAME.format(sensor, date_str))
    if not os.path.isfile(gpt_xml_file):
        rewrite_xml(gpt_xml_file, date_str, sensor, altnn, validexpression, vicar_properties_filename, wkt)

    args = [gpt, gpt_xml_file, "-c", env['General']['gpt_cache_size'], "-e", "-SsourceFile={}".format(source_file),
            "-PoutputFile={}".format(output_file)]
    if subprocess.call(args):
        raise RuntimeError("GPT Failed.")

    return output_file


def rewrite_xml(gpt_xml_file, date_str, sensor, altnn, validexpression, vicar_properties_filename, wkt):
    with open(os.path.join(os.path.dirname(__file__), GPT_XML_FILENAME.format(sensor, "")), "r") as f:
        xml = f.read()

    altnn_path = os.path.join(os.path.dirname(__file__), "altnn", altnn) if altnn else ""

    # ancillary = Ancillary_ERA()
    ancillary = Ancillary_ERA5()
    date = datetime.datetime.strptime(date_str, "%Y%m%dT%H%M%S")
    lons, lats = get_lons_lats(wkt)
    coords = (max(lats) + min(lats)) / 2, (max(lons) + min(lons)) / 2
    ozone = round(ancillary.get("ozone", date)[coords])
    surf_press = round(ancillary.get("surf_press", date)[coords])

    xml = xml.replace("${validPixelExpression}", validexpression)
    xml = xml.replace("${salinity}", str(0.05))
    xml = xml.replace("${temperature}", str(15.0))
    xml = xml.replace("${ozone}", str(ozone))
    xml = xml.replace("${press}", str(surf_press))
    xml = xml.replace("${TSMfakBpart}", str(1.72))
    xml = xml.replace("${TSMfakBwit}", str(3.1))
    xml = xml.replace("${CHLexp}", str(1.04))
    xml = xml.replace("${CHLfak}", str(21.0))
    xml = xml.replace("${thresholdRtosaOOS}", str(0.05))
    xml = xml.replace("${thresholdAcReflecOos}", str(0.1))
    xml = xml.replace("${thresholdCloudTDown865}", str(0.955))
    xml = xml.replace("${alternativeNNPath}", altnn_path)

    if vicar_properties_filename:
        vicar_properties_file = os.path.join(os.path.dirname(__file__), "vicarious", vicar_properties_filename)
        vicar_params = load_properties(vicar_properties_file)
        for key in vicar_params.keys():
            xml = xml.replace("${" + key + "}", vicar_params[key])

    os.makedirs(os.path.dirname(gpt_xml_file), exist_ok=True)
    with open(gpt_xml_file, "w") as f:
        f.write(xml)
