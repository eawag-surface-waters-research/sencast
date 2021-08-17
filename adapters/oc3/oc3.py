#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""The OC3 adapter calculates Chlorophyll A from Polymer output"""

import os
import numpy as np
from snappy import ProductIO, ProductData, Product, ProductUtils

# key of the params section for this adapter
PARAMS_SECTION = "OC3"

# the file name pattern for output file
FILENAME = "L2OC3_{}"
FILEFOLDER = "L2OC3"

# Optimised OC3 parameters
p0_oc3_lin = [0.73, -1.2, 0, 0, 0]
popt_oc3_rev = [0.44580314, -2.29314384, 13.17079188, -11.08418745, -408.86537168]


def apply(env, params, l2product_files, date):
    """Apply OC3 adapter.
        1. Uses OC3 to output CHL-A

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
        raise RuntimeWarning("OC3 was not configured in parameters.")
    print("Applying OC3...")

    if "processor" not in params[PARAMS_SECTION]:
        raise RuntimeWarning("OC3 processor must be defined in the parameter file.")

    processor = params[PARAMS_SECTION]["processor"]
    if processor != "POLYMER":
        raise RuntimeWarning("OC3 adapter only works with Polymer processor output")

    # Check for precursor datasets
    if processor not in l2product_files or not os.path.exists(l2product_files[processor]):
        raise RuntimeWarning("POLYMER precursor file not found ensure POLYMER is run before this adapter.")

    # Create folder for file
    product_path = l2product_files[processor]
    product_name = os.path.basename(product_path)
    product_dir = os.path.join(os.path.dirname(os.path.dirname(product_path)), FILEFOLDER)
    output_file = os.path.join(product_dir, FILENAME.format(product_name))
    l2product_files["OC3"] = output_file
    if os.path.isfile(output_file):
        if "synchronise" in params["General"].keys() and params['General']['synchronise'] == "false":
            print("Removing file: ${}".format(output_file))
            os.remove(output_file)
        else:
            print("Skipping OC3, target already exists: {}".format(FILENAME.format(product_name)))
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

    oc3_product = Product('Z0', 'Z0', width, height)

    valid_pixel_expression = product.getBand('tsm_binding754').getValidPixelExpression()
    for band_name in band_names:
        if band_name in valid_pixel_expression:
            ProductUtils.copyBand(band_name, product, oc3_product, True)

    chla_band = create_band(oc3_product, "chla", "mg/m3", valid_pixel_expression)

    writer = ProductIO.getProductWriter('NetCDF4-BEAM')
    ProductUtils.copyGeoCoding(product, oc3_product)
    oc3_product.setProductWriter(writer)
    oc3_product.writeHeader(output_file)

    # Write valid pixel bands
    for band_name in band_names:
        if band_name in valid_pixel_expression:
            temp_arr = np.zeros(width * height)
            product.getBand(band_name).readPixels(0, 0, width, height, temp_arr)
            oc3_product.getBand(band_name).writePixels(0, 0, width, height, temp_arr)

    Rrs = read_rrs_polymer(product, width, height)
    xx_oc3 = np.log10(np.maximum(Rrs[2], Rrs[3]) / Rrs[5])

    chla = np.zeros(width * height)
    chla[:] = np.nan
    chla[xx_oc3 < -0.16] = ocx(xx_oc3[xx_oc3 < -0.16], *p0_oc3_lin)
    chla[xx_oc3 >= -0.16] = ocx(xx_oc3[xx_oc3 >= -0.16], *popt_oc3_rev)

    chla_band.writePixels(0, 0, width, height, chla)
    oc3_product.closeIO()
    print("Writing OC3 to file: {}".format(output_file))


def create_band(product, name, unit, valid_pixel_expression):
    band = product.addBand(name, ProductData.TYPE_FLOAT32)
    band.setUnit(unit)
    band.setNoDataValueUsed(True)
    band.setNoDataValue(np.NaN)
    band.setValidPixelExpression(valid_pixel_expression)
    return band


def read_rrs_polymer(product, width, height):
    polymer_bands = ["Rw400", "Rw412", "Rw443", "Rw490", "Rw510", "Rw560", "Rw620", "Rw665",
                     "Rw681", "Rw709", "Rw754", "Rw779", "Rw865", "Rw1020"]
    Rrs = []
    for band in polymer_bands:
        temp_arr = np.zeros(width * height)
        Rrs.append(product.getBand(band).readPixels(0, 0, width, height, temp_arr))
    return Rrs


def ocx(rsbg, a0, a1, a2, a3, a4):
    return 10**(a0 + a1 * rsbg + a2 * (rsbg ** 2) + a3 * (rsbg ** 3) + a4 * (rsbg ** 4))
