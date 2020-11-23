#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""The MDN adapter calculates Chlorophyll A from Polymer output"""

import os
import numpy as np
from snappy import ProductIO, ProductData, Product, ProductUtils
from .MDN import image_estimates, get_tile_data, get_sensor_bands, get_tile_data_polymer

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

def apply(env, params, l2product_files, date):
    """Apply MDN adapter.
        1. Uses MDN to output CHL-A

        Parameters
        -------------

        params
            Dictionary of parameters, loaded from input file
        env
            Dictionary of environment parameters, loaded from input file
        l2product_files
            Dictionary of Level 2 product files created by processors
        date
            Run date
        """
    if not params.has_section(PARAMS_SECTION):
        raise RuntimeWarning("MDN was not configured in parameters.")
    print("Applying MDN...")

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
    l2product_files["MDN"] = output_file
    if os.path.isfile(output_file):
        if "synchronise" in params["General"].keys() and params['General']['synchronise'] == "false":
            print("Removing file: ${}".format(output_file))
            os.remove(output_file)
        else:
            print("Skipping MDN, target already exists: {}".format(FILENAME.format(product_name)))
            return output_file
    os.makedirs(product_dir, exist_ok=True)

    print("Reading POLYMER output from {}".format(product_path))
    product = ProductIO.readProduct(product_path)
    width = product.getSceneRasterWidth()
    height = product.getSceneRasterHeight()
    name = product.getName()
    description = product.getDescription()
    band_names = product.getBandNames()

    print("Product:      {}, {}".format(name, description))
    print("Raster size: {} x {} pixels".format(width, height))
    print("Bands:       {}".format(list(band_names)))

    mdn_product = Product('Z0', 'Z0', width, height)

    valid_pixel_expression = product.getBand('tsm_binding754').getValidPixelExpression()
    for band_name in band_names:
        if band_name in valid_pixel_expression:
            ProductUtils.copyBand(band_name, product, mdn_product, True)

    mdn_band_names = [{"name": 'chla', "unit": "mg/m3"}]
    mdn_bands = []
    for mdn_band in mdn_band_names:
        temp_band = mdn_product.addBand(mdn_band["name"], ProductData.TYPE_FLOAT32)
        temp_band.setUnit(mdn_band["unit"])
        temp_band.setNoDataValueUsed(True)
        temp_band.setNoDataValue(np.NaN)
        temp_band.setValidPixelExpression(valid_pixel_expression)
        mdn_bands.append(temp_band)

    writer = ProductIO.getProductWriter('NetCDF4-BEAM')

    ProductUtils.copyGeoCoding(product, mdn_product)

    mdn_product.setProductWriter(writer)
    mdn_product.writeHeader(output_file)

    # Write valid pixel bands
    for band_name in band_names:
        if band_name in valid_pixel_expression:
            temp_arr = np.zeros(width * height)
            product.getBand(band_name).readPixels(0, 0, width, height, temp_arr)
            mdn_product.getBand(band_name).writePixels(0, 0, width, height, temp_arr)

    sensor = "OLCI-poly"
    for mdn_b in mdn_bands:
        if "poly" in sensor:
            bands, Rrs = get_tile_data_polymer(product_path, sensor, allow_neg=True)
        else:
            bands, Rrs = get_tile_data(product_path, sensor, allow_neg=True)
        estimates = image_estimates(Rrs, sensor=sensor)
        band_data = np.asarray(estimates[0])
        mdn_b.writePixels(0, 0, width, height, band_data)
    mdn_product.closeIO()
    print("Writing MDN to file: {}".format(output_file))
