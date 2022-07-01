#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""The MDN processor calculates Chlorophyll A from Polymer output"""

import os
import numpy as np

from netCDF4 import Dataset
from utils.auxil import log
from utils.product_fun import copy_nc, get_band_names_from_nc, get_name_width_height_from_nc, get_satellite_name_from_product_name, get_valid_pe_from_nc, write_pixels_to_nc

from .MDN import image_estimates, get_tile_data, get_tile_data_polymer

# key of the params section for this adapter
PARAMS_SECTION = "MDN"

# the file name pattern for output file
FILENAME = "L2MDN_{}"
FILEFOLDER = "L2MDN"

#'MSI': [443, 490, 560, 665, 705, 740, 783],
#'MSI-rho': [443, 490, 560, 665, 705, 740, 783, 865],
#'OLCI': [411, 442, 490, 510, 560, 619, 664, 673, 681, 708, 753, 761, 764, 767, 778],
#'OLCI-e': [411, 442, 490, 510, 560, 619, 664, 673, 681, 708, 753, 778],
#'OLCI-poly': [411, 442, 490, 510, 560, 619, 664, 681, 708, 753, 778],
#'OLCI-sat': [411, 442, 490, 510, 560, 619, 664, 673, 681, 708, 753, 761, 764, 767, ],


def process(env, params, l1product_path, l2product_files, out_path):
    """
    MDN processor: uses MDN to output CHL-A

    Parameters
    -------------

    env
        Dictionary of environment parameters, loaded from input file
    params
        Dictionary of parameters, loaded from input file
    l1product_path
        unused
    l2product_files
        Dictionary of Level 2 product files created by processors
    out_path
        unused
    """
    if not params.has_section(PARAMS_SECTION):
        raise RuntimeWarning("MDN was not configured in parameters.")
    log(env["General"]["log"], "Applying MDN...")

    if "processor" not in params[PARAMS_SECTION]:
        raise RuntimeWarning("MDN processor must be defined in the parameter file.")

    if params["General"]["sensor"] != "OLCI":
        raise RuntimeWarning("MDN processor is currently only configured for OLCI.")

    processor = params[PARAMS_SECTION]["processor"]
    if processor != "POLYMER":
        raise RuntimeWarning("MDN adapter only works with Polymer processor output")

    # Check for precursor datasets
    if processor not in l2product_files or not os.path.exists(l2product_files[processor]):
        raise RuntimeWarning("POLYMER precursor file not found ensure POLYMER is run before this adapter.")

    # Create folder for file
    product_path = l2product_files[processor]
    product_name = os.path.basename(product_path)
    product_dir = os.path.join(os.path.dirname(os.path.dirname(product_path)), FILEFOLDER)
    output_file = os.path.join(product_dir, FILENAME.format(product_name))

    if os.path.isfile(output_file):
        if "synchronise" in params["General"].keys() and params['General']['synchronise'] == "false":
            log(env["General"]["log"], "Removing file: ${}".format(output_file))
            os.remove(output_file)
        else:
            log(env["General"]["log"], "Skipping MDN, target already exists: {}".format(FILENAME.format(product_name)))
            return output_file
    os.makedirs(product_dir, exist_ok=True)

    log(env["General"]["log"], "Reading POLYMER output from {}".format(product_path))
    with Dataset(product_path) as src, Dataset(output_file, mode='w') as dst:
        name, width, height = get_name_width_height_from_nc(src, product_path)
        product_band_names = get_band_names_from_nc(src)

        log(env["General"]["log"], "Product:      {}".format(name))
        log(env["General"]["log"], "Raster size: {} x {} pixels".format(width, height))
        log(env["General"]["log"], "Bands:       {}".format(list(product_band_names)))

        valid_pixel_expression = get_valid_pe_from_nc(src)
        inclusions = [band for band in product_band_names if band in valid_pixel_expression]
        inclusions.append('metadata')
        copy_nc(src, dst, inclusions)

        mdn_band_names = ['chla']
        mdn_band_units = ['mg/m3']
        for band_name, band_unit in zip(mdn_band_names, mdn_band_units):
            b = dst.createVariable(band_name, 'f', dimensions=('lat', 'lon'), fill_value=np.NaN)
            b.units = band_unit
            b.valid_pixel_expression = valid_pixel_expression

        sensor = "OLCI-poly"
        for band_name in mdn_band_names:
            if "poly" in sensor:
                bands, rrs = get_tile_data_polymer(product_path, sensor, allow_neg=True)
            else:
                bands, rrs = get_tile_data(product_path, sensor, allow_neg=True)
            estimates = image_estimates(rrs, sensor=sensor)
            band_data = np.asarray(estimates[0])
            write_pixels_to_nc(dst, band_name, 0, 0, width, height, band_data)

        log(env["General"]["log"], "Writing MDN to file: {}".format(output_file))
        l2product_files["MDN"] = output_file
        return output_file
