#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess

from haversine import haversine
from snappy import ProductIO

from packages.product_fun import get_lons_lats
from packages.ql_mapping import plot_pic

# The name of the folder to which the output product will be saved
OUT_DIR = "L1P"
# A pattern for the name of the file to which the output product will be saved (completed with product name)
FILENAME = "merge_reproj_L1P_subset_{}.nc"
# A pattern for name of the folder to which the quicklooks will be saved (completed with band name)
QL_OUT_DIR = "L1P-{}"
# A pattern for the name of the file to which the quicklooks will be saved (completed with product name and band name)
QL_FILENAME = "reproj_L1P_subset_{}_{}.png"
# The name of the xml file for gpt
GPT_XML_FILENAME = "idepix_{}.xml"


def process(gpt, gpt_xml_path, wkt, source, product_name, out_path, sensor, resolution, params):
    """ This processor applies subset, idepix, merge and reprojection to the source product and stores the result.
    It returns the location of the output product. """

    print("Applying IDEPIX...")

    output = os.path.join(out_path, OUT_DIR, FILENAME.format(product_name))
    if os.path.isfile(output):
        print("Skipping IDEPIX, targets already exist: {}".format(os.path.basename(output)))
        return output
    os.makedirs(os.path.dirname(output), exist_ok=True)

    gpt_xml_file = rewrite_xml(gpt_xml_path, out_path, wkt, sensor, resolution)

    args = [gpt, gpt_xml_file,
            "-Ssource={}".format(source),
            "-Poutput={}".format(output)]
    subprocess.call(args)

    rgb_bands = params['rgb_bands'].split(",")
    fc_bands = params['fc_bands'].split(",")
    create_quicklooks(out_path, product_name, wkt, sensor, rgb_bands, fc_bands)

    return output


def rewrite_xml(gpt_xml_path, out_path, wkt, sensor, resolution):
    with open(os.path.join(gpt_xml_path, GPT_XML_FILENAME.format(sensor.lower())), "r") as f:
        xml = f.read()

    reproject_params = create_reproject_parameters_from_wkt(wkt, resolution)
    xml = xml.replace("${wkt}", wkt)
    xml = xml.replace("${easting}", reproject_params['easting'])
    xml = xml.replace("${northing}", reproject_params['northing'])
    xml = xml.replace("${pixelSizeX}", reproject_params['pixelSizeX'])
    xml = xml.replace("${pixelSizeY}", reproject_params['pixelSizeY'])
    xml = xml.replace("${width}", reproject_params['width'])
    xml = xml.replace("${height}", reproject_params['height'])

    gpt_xml_file = os.path.join(out_path, GPT_XML_FILENAME.format(sensor.lower()))
    with open(gpt_xml_file, "wb") as f:
        f.truncate()
        f.write(xml.encode())

    return gpt_xml_file


def create_reproject_parameters_from_wkt(wkt, resolution):
    lons, lats = get_lons_lats(wkt)
    x_dist = haversine((min(lats), min(lons)), (min(lats), max(lons)))
    y_dist = haversine((min(lats), min(lons)), (max(lats), min(lons)))
    x_pix = int(round(x_dist / (int(resolution) / 1000)))
    y_pix = int(round(y_dist / (int(resolution) / 1000)))
    x_pixsize = (max(lons) - min(lons)) / x_pix
    y_pixsize = (max(lats) - min(lats)) / y_pix

    return {'easting': str(min(lons)), 'northing': str(max(lats)), 'pixelSizeX': str(x_pixsize),
            'pixelSizeY': str(y_pixsize), 'width': str(x_pix), 'height': str(y_pix)}


def create_quicklooks(out_path, product_name, wkt, sensor, rgb_bands, fc_bands):
    print("Creating quicklooks for IDEPIX")
    if sensor == "OLCI":
        rgb_bands = [bn.replace('radiance', 'reflectance') for bn in rgb_bands]
        fc_bands = [bn.replace('radiance', 'reflectance') for bn in fc_bands]

    product = ProductIO.readProduct(os.path.join(out_path, OUT_DIR, FILENAME.format(product_name)))
    ql_file = os.path.join(out_path, QL_OUT_DIR.format("rgb"), QL_FILENAME.format(product_name, "rgb"))
    os.makedirs(os.path.dirname(ql_file), exist_ok=True)
    plot_pic(product, ql_file, rgb_layers=rgb_bands, grid=True, max_val=0.16, wkt=wkt)
    ql_file = os.path.join(out_path, QL_OUT_DIR.format("fc"), QL_FILENAME.format(product_name, "fc"))
    os.makedirs(os.path.dirname(ql_file), exist_ok=True)
    plot_pic(product, ql_file, rgb_layers=fc_bands, grid=True, max_val=0.3, wkt=wkt)
    product.closeIO()
