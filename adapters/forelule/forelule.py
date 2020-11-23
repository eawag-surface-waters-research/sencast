#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""The Forel-Ule adapter is an implementation of `Giardino et al. (2019) <https://www.intechopen.com/books/geospatial-analyses-of-earth-observation-eo-data/the-color-of-water-from-space-a-case-study-for-italian-lakes-from-sentinel-2>`_
in order to estimate the Forel-Ule color from satellite images.
Adapter authors: Daniel Odermatt
"""

import os
import re
import numpy as np
from snappy import ProductIO, ProductData, Product, ProductUtils


# key of the params section for this adapter
PARAMS_SECTION = 'FORELULE'

# the file name pattern for output file
FILENAME = 'L2FU_{}'
FILEFOLDER = 'L2FU'


def apply(env, params, l2product_files, date):
    """Apply the Forel-Ule adapter.
                1. Calculates a hue product from Polymer output

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
    if not env.has_section(PARAMS_SECTION):
        raise RuntimeWarning('Forel-Ule was not configured in this environment.')
    if not params.has_section(PARAMS_SECTION):
        raise RuntimeWarning('Forel-Ule was not configured in parameters.')
    print("Applying Forel-Ule...")

    if "processor" not in params[PARAMS_SECTION]:
        raise RuntimeWarning('processor must be defined in the parameter file.')

    processor = params[PARAMS_SECTION]['processor']
    if processor != 'POLYMER':
        raise RuntimeWarning('Forel-Ule adapter only works with Polymer processor output')

    # Check for precursor datasets
    if processor not in l2product_files or not os.path.exists(l2product_files[processor]):
        raise RuntimeWarning('POLYMER precursor file not found ensure POLYMER is run before this adapter.')

    # Create folder for file
    product_path = l2product_files[processor]
    product_name = os.path.basename(product_path)
    product_dir = os.path.join(os.path.dirname(os.path.dirname(product_path)), FILEFOLDER)
    output_file = os.path.join(product_dir, FILENAME.format(product_name))
    l2product_files["FORELULE"] = output_file
    if os.path.isfile(output_file):
        if "synchronise" in params["General"].keys() and params['General']['synchronise'] == "false":
            print('Removing file: ${}'.format(output_file))
            os.remove(output_file)
        else:
            print('Skipping Forel-Ule, target already exists: {}'.format(FILENAME.format(product_name)))
            return output_file
    os.makedirs(product_dir, exist_ok=True)

    print('Reading POLYMER output from {}'.format(product_path))
    product = ProductIO.readProduct(product_path)
    width = product.getSceneRasterWidth()
    height = product.getSceneRasterHeight()
    name = product.getName()
    description = product.getDescription()
    band_names = product.getBandNames()

    print('Product:      {}, {}'.format(name, description))
    print('Raster size: {} x {} pixels'.format(width, height))
    print('Bands:       {}'.format(list(band_names)))

    band_names2 = ['Rw443', 'Rw490', 'Rw560', 'Rw665', 'Rw705']
    bands = [product.getBand(bname) for bname in band_names2]

    foreluleProduct = Product('Z0', 'Z0', width, height)
    forelule_names = ['hue_angle']
    forelules = []
    for forelule_name in forelule_names:
        temp_band = foreluleProduct.addBand(forelule_name, ProductData.TYPE_FLOAT32)
        if 'angle' in forelule_name:
            temp_band.setUnit('deg')
        elif 'whatever' in forelule_name:
            temp_band.setUnit('m^-1')
        temp_band.setNoDataValueUsed(True)
        temp_band.setNoDataValue(np.NaN)
        wavelength = re.findall('\d+', forelule_name)[0]
        forelules.append(temp_band)

    writer = ProductIO.getProductWriter('NetCDF4-CF')
    ProductUtils.copyGeoCoding(product, foreluleProduct)
    foreluleProduct.setProductWriter(writer)
    foreluleProduct.writeHeader(output_file)

    rs = [np.zeros(width, dtype=np.float32) for _ in range(len(band_names2))]

    print('Calculating Forel-Ule parameters.')

    for y in range(height):
        # Reading the different bands per pixel into arrays
        rs = [b.readPixels(0, y, width, 1, r) for (b, r) in zip(bands, rs)]

        ################## Derivation of the hue angle ##################

        x = 8.356 * rs[1] + 12.040 * rs[2] + 53.696 * rs[3] + 32.087 * rs[4] + 0.487 * rs[5]
        y = 0.993 * rs[1] + 12.040 * rs[2] + 53.696 * rs[3] + 32.087 * rs[4] + 0.177 * rs[5]
        z = 43.487 * rs[1] + 61.055 * rs[2] + 1.778 * rs[3] + 0.015 * rs[4]

        # test equation
        # print((np.arctan2([1/3 - 1/3], [0.5 - 1/3]) % 2) * 180 / np.pi)
        hue_angle = np.arctan2([y - 1/3], [x - 1/3]) % 2

        output = hue_angle # + etc. bands

        # Mark infinite values as NAN
        for bds in output:
            bds[bds == np.inf] = np.nan
            bds[bds == -np.inf] = np.nan

        # Write the Forel-Ule parameters per band
        for forelule, bds in zip(forelules, output):
            forelule.writePixels(0, y, width, 1, bds)

    foreluleProduct.closeIO()
    print('Writing Forel-Ule to file: {}'.format(output_file))
