#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess

from polymer.ancillary_era5 import Ancillary_ERA5
from polymer.gsw import GSW
from polymer.level2 import default_datasets
from polymer.main import run_atm_corr, Level1, Level2
from snappy import ProductIO

from packages.product_fun import get_corner_pixels_roi, get_reproject_params_from_wkt
from packages.ql_mapping import plot_map

# Key of the params section for this processor
PARAMS_SECTION = "POLYMER"
# The name of the folder to which the output product will be saved
OUT_DIR = "L2POLY"
# A pattern for the name of the file to which the output product will be saved (completed with product name)
OUT_FILENAME = "L2POLY_L1P_reproj_{}.nc"
# A pattern for name of the folder to which the quicklooks will be saved (completed with band name)
QL_DIR = "L2POLY-{}"
# A pattern for the name of the file to which the quicklooks will be saved (completed with product name and band name)
QL_FILENAME = "L2POLY_L1P_reproj_{}_{}.png"
# The name of the xml file for gpt
GPT_XML_FILENAME = "polymer.xml"


def process(env, params, l1_product_path, source_file, out_path):
    """ This processor applies polymer to the source product and stores the result. """

    print("Applying POLYMER...")
    gpt, product_name = env['General']['gpt_path'], os.path.basename(l1_product_path)
    sensor, resolution, wkt = params['General']['sensor'], params['General']['resolution'], params['General']['wkt']
    gsw_path, ancillary_path = env['GSW']['root_path'], env['CDS']['root_path']
    os.makedirs(gsw_path, exist_ok=True)
    os.makedirs(ancillary_path, exist_ok=True)

    output_file = os.path.join(out_path, OUT_DIR, OUT_FILENAME.format(product_name))
    if os.path.isfile(output_file):
        print("Skipping POLYMER, target already exists: {}".format(OUT_FILENAME.format(product_name)))
        return output_file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    ancillary = Ancillary_ERA5(directory=ancillary_path)
    if sensor == "MSI":
        granule_path = os.path.join(l1_product_path, "GRANULE")
        msi_product_path = os.path.join(granule_path, os.listdir(granule_path)[0])
        gsw = GSW(directory=gsw_path)
        l1 = Level1(msi_product_path, landmask=gsw, ancillary=ancillary)
        additional_ds = ['sza']
    else:
        UL, UR, LR, LL = get_corner_pixels_roi(ProductIO.readProduct(l1_product_path), wkt)
        sline, scol, eline, ecol = min(UL[0], UR[0]), min(UL[1], UR[1]), max(LL[0], LR[0]), max(LL[1], LR[1])
        gsw = GSW(directory=gsw_path, agg=8)
        l1 = Level1(l1_product_path, sline=sline, scol=scol, eline=eline, ecol=ecol, landmask=gsw, ancillary=ancillary)
        additional_ds = ['vaa', 'vza', 'saa', 'sza']
    poly_tmp_file = "{}.tmp".format(output_file)
    l2 = Level2(filename=poly_tmp_file, fmt='netcdf4', overwrite=True, datasets=default_datasets + additional_ds)
    run_atm_corr(l1, l2)

    gpt_xml_file = os.path.join(out_path, GPT_XML_FILENAME)
    if not os.path.isfile(gpt_xml_file):
        rewrite_xml(gpt_xml_file, resolution, wkt)

    args = [gpt, gpt_xml_file,
            "-SsourceFile1={}".format(source_file),
            "-SsourceFile2={}".format(poly_tmp_file),
            "-PoutputFile={}".format(output_file)]

    if subprocess.call(args):
        raise RuntimeError("GPT Failed.")

    os.remove(poly_tmp_file)

    create_quicklooks(params, output_file, product_name, out_path, wkt)

    return output_file


def rewrite_xml(gpt_xml_file, resolution, wkt):
    with open(os.path.join(os.path.dirname(__file__), GPT_XML_FILENAME), "r") as f:
        xml = f.read()

    reproject_params = get_reproject_params_from_wkt(wkt, resolution)
    xml = xml.replace("${wkt}", wkt)
    xml = xml.replace("${easting}", reproject_params['easting'])
    xml = xml.replace("${northing}", reproject_params['northing'])
    xml = xml.replace("${pixelSizeX}", reproject_params['pixelSizeX'])
    xml = xml.replace("${pixelSizeY}", reproject_params['pixelSizeY'])
    xml = xml.replace("${width}", reproject_params['width'])
    xml = xml.replace("${height}", reproject_params['height'])

    with open(gpt_xml_file, "wb") as f:
        f.write(xml.encode())


def create_quicklooks(params, product_file, product_name, out_path, wkt):
    bands, bandmaxs = params[PARAMS_SECTION]['bands'].split(","), params[PARAMS_SECTION]['bandmaxs'].split(",")
    print("Creating quicklooks for POLYMER for bands: {}".format(bands))
    for band, bandmax in zip(bands, bandmaxs):
        bandmax = False if int(bandmax) == 0 else range(0, int(bandmax))
        ql_file = os.path.join(out_path, QL_DIR.format(band), QL_FILENAME.format(product_name, band))
        os.makedirs(os.path.dirname(ql_file), exist_ok=True)
        plot_map(product_file, ql_file, band, wkt, basemap="srtm_hillshade", param_range=bandmax)
