#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Polymer is an algorithm aimed at recovering the radiance scattered and absorbed by the oceanic waters (also called
Ocean Colour) from the signal measured by satellite sensors in the visible spectrum.

For an overview of the processor:
https://www.hygeos.com/polymer

or for more details:
https://forum.hygeos.com/viewforum.php?f=3
"""

import os
import subprocess
from math import ceil, floor
from datetime import datetime
import numpy as np
from snappy import ProductIO, GeoPos

from polymer.ancillary_era5 import Ancillary_ERA5
from polymer.gsw import GSW
from polymer.level1_msi import Level1_MSI
from polymer.level1_olci import Level1_OLCI
from polymer.level2 import default_datasets
from polymer.main import run_atm_corr, Level2

from utils.product_fun import get_lons_lats, get_sensing_datetime_from_product_name, get_reproject_params_from_wkt
import processors.polymer.vicarious.polymer_vicarious as polymer_vicarious

# Key of the params section for this processor
PARAMS_SECTION = "POLYMER"
# The name of the folder to which the output product will be saved
OUT_DIR = "L2POLY"
# A pattern for the name of the file to which the output product will be saved (completed with product name)
OUT_FILENAME = "L2POLY_L1P_reproj_{}_{}.nc"
# A pattern for name of the folder to which the quicklooks will be saved (completed with band name)
QL_DIR = "L2POLY-{}"
# A pattern for the name of the file to which the quicklooks will be saved (completed with product name and band name)
QL_FILENAME = "L2POLY_L1P_reproj_{}_{}.png"
# The name of the xml file for gpt
GPT_XML_FILENAME = "polymer_{}.xml"


def process(env, params, l1product_path, _, out_path):
    """ This processor applies polymer to the source product and stores the result. """

    print("Applying POLYMER...")
    gpt, product_name = env['General']['gpt_path'], os.path.basename(l1product_path)
    date_str = get_sensing_datetime_from_product_name(product_name)
    sensor, resolution, wkt = params['General']['sensor'], params['General']['resolution'], params['General']['wkt']
    water_model, validexpression = params['POLYMER']['water_model'], params['POLYMER']['validexpression']
    vicar_version = params['POLYMER']['vicar_version']
    gsw_path, ancillary_path = env['GSW']['root_path'], env['CDS']['era5_path']
    os.makedirs(gsw_path, exist_ok=True)
    os.makedirs(ancillary_path, exist_ok=True)

    try:
        date = datetime.strptime(date_str, "%Y%m%dT%H%M%S")
        lons, lats = get_lons_lats(wkt)
        coords = (max(lats) + min(lats)) / 2, (max(lons) + min(lons)) / 2
        ancillary = Ancillary_ERA5(directory=ancillary_path)
        ozone = round(ancillary.get("ozone", date)[coords])  # Test can retrieve parameters
        anc_name = "ERA5"
        print("Polymer collected ERA5 ancillary data.")
    except Exception:
        ancillary = None
        anc_name = "NA"
        print("Polymer failed to collect ERA5 ancillary data.")

    output_file = os.path.join(out_path, OUT_DIR, OUT_FILENAME.format(anc_name, product_name))
    if os.path.isfile(output_file):
        if "synchronise" in params["General"].keys() and params['General']['synchronise'] == "false":
            print("Removing file: ${}".format(output_file))
            os.remove(output_file)
        else:
            print("Skipping POLYMER, target already exists: {}".format(OUT_FILENAME.format(anc_name, product_name)))
            product = ProductIO.readProduct(output_file)
            band = product.getBand("Rw443")
            w = band.getRasterWidth()
            h = band.getRasterHeight()
            band_data = np.zeros(w * h, np.float32)
            band.readPixels(0, 0, w, h, band_data)
            if np.isnan(np.nanmean(band_data)):
                print("No pixels present in the file.")
                return False
            return output_file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    if sensor == "MSI":
        calib_gains = polymer_vicarious.msi_vicarious(vicar_version)
        granule_path = os.path.join(l1product_path, "GRANULE")
        msi_product_path = os.path.join(granule_path, os.listdir(granule_path)[0])
        UL, UR, LR, LL = get_corner_pixels_roi(msi_product_path, wkt)
        sline, scol, eline, ecol = min(UL[0], UR[0]), min(UL[1], UR[1]), max(LL[0], LR[0]), max(LL[1], LR[1])
        # Normalize to correct resolution
        target_divisor = 60 / int(resolution)
        sline, scol, eline, ecol = [(i * 10 / int(resolution)) for i in [sline, scol, eline, ecol]]
        sline, scol = [int(floor(i / target_divisor) * target_divisor) for i in [sline, scol]]
        eline, ecol = [int(ceil(i / target_divisor) * target_divisor) for i in [eline, ecol]]
        gsw = GSW(directory=gsw_path)
        l1 = Level1_MSI(msi_product_path, sline=sline, eline=eline, scol=scol, ecol=ecol, landmask=gsw,
                        ancillary=ancillary, resolution=resolution)
        additional_ds = ['sza']
    else:
        calib_gains = polymer_vicarious.olci_vicarious(vicar_version)
        UL, UR, LR, LL = get_corner_pixels_roi(l1product_path, wkt)
        sline, scol, eline, ecol = min(UL[0], UR[0]), min(UL[1], UR[1]), max(LL[0], LR[0]), max(LL[1], LR[1])
        gsw = GSW(directory=gsw_path, agg=8)
        l1 = Level1_OLCI(l1product_path, sline=sline, eline=eline, scol=scol, ecol=ecol, landmask=gsw,
                         ancillary=ancillary)
        additional_ds = ['vaa', 'vza', 'saa', 'sza']
    poly_tmp_file = os.path.join(out_path, OUT_DIR, "_reproducibility", OUT_FILENAME.format(anc_name, product_name) + ".tmp")
    l2 = Level2(filename=poly_tmp_file, fmt='netcdf4', overwrite=True, datasets=default_datasets + additional_ds)
    os.makedirs(os.path.dirname(poly_tmp_file), exist_ok=True)

    run_atm_corr(l1, l2, water_model=water_model, calib=calib_gains)

    gpt_xml_file = os.path.join(out_path, OUT_DIR, "_reproducibility", GPT_XML_FILENAME.format(sensor))
    if not os.path.isfile(gpt_xml_file):
        rewrite_xml(gpt_xml_file, sensor, validexpression, resolution, wkt)

    args = [gpt, gpt_xml_file, "-c", env['General']['gpt_cache_size'], "-e", "-SsourceFile={}".format(poly_tmp_file),
            "-PoutputFile={}".format(output_file)]
    if subprocess.call(args):
        if os.path.exists(output_file):
            os.remove(output_file)
        else:
            print("No file was created.")
        raise RuntimeError("GPT Failed.")

    product = ProductIO.readProduct(output_file)
    band = product.getBand("Rw443")
    w = band.getRasterWidth()
    h = band.getRasterHeight()
    band_data = np.zeros(w * h, np.float32)
    band.readPixels(0, 0, w, h, band_data)
    if np.isnan(np.nanmean(band_data)):
        print("No pixels present in the file.")
        return False

    return output_file


def rewrite_xml(gpt_xml_file, sensor, validexpression, resolution, wkt):
    with open(os.path.join(os.path.dirname(__file__), GPT_XML_FILENAME.format(sensor)), "r") as f:
        xml = f.read()

    reproject_params = get_reproject_params_from_wkt(wkt, resolution)
    xml = xml.replace("${wkt}", wkt)
    xml = xml.replace("${validPixelExpression}", validexpression)
    xml = xml.replace("${easting}", reproject_params['easting'])
    xml = xml.replace("${northing}", reproject_params['northing'])
    xml = xml.replace("${pixelSizeX}", reproject_params['pixelSizeX'])
    xml = xml.replace("${pixelSizeY}", reproject_params['pixelSizeY'])
    xml = xml.replace("${width}", reproject_params['width'])
    xml = xml.replace("${height}", reproject_params['height'])

    os.makedirs(os.path.dirname(gpt_xml_file), exist_ok=True)
    with open(gpt_xml_file, "w") as f:
        f.write(xml)


def get_corner_pixels_roi(product_path, wkt):
    """ Get the uper left, upper right, lower right, and lower left pixel position of the wkt containing rectangle """
    product = ProductIO.readProduct(product_path)

    h, w = product.getSceneRasterHeight(), product.getSceneRasterWidth()

    lons, lats = get_lons_lats(wkt)
    ul_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(max(lats), min(lons)), None)
    ur_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(max(lats), max(lons)), None)
    ll_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(min(lats), min(lons)), None)
    lr_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(min(lats), max(lons)), None)

    UL = [int(ul_pos.y) if (0 <= ul_pos.y < h) else 0, int(ul_pos.x) if (0 <= ul_pos.x < w) else 0]
    UR = [int(ur_pos.y) if (0 <= ur_pos.y < h) else 0, int(ur_pos.x) if (0 <= ur_pos.x < w) else w]
    LL = [int(ll_pos.y) if (0 <= ll_pos.y < h) else h, int(ll_pos.x) if (0 <= ll_pos.x < w) else 0]
    LR = [int(lr_pos.y) if (0 <= lr_pos.y < h) else h, int(lr_pos.x) if (0 <= lr_pos.x < w) else w]

    product.closeIO()
    return UL, UR, LR, LL
