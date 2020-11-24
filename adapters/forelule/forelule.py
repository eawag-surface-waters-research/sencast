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
from auxil import get_satellite_name_from_name


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


    satellite = get_satellite_name_from_name(product_name)
    ################## Derivation of the hue angle ##################
    if satellite == 'Sentinel-2':
        # see table 1 in Van der Woerd & Wernand (2018): https://www.mdpi.com/2072-4292/10/2/180
        # let's assume his R440 in S2 MSI-60 m is a typo and should be R400 as for the other sensors
        wvls = [443, 490, 560, 665, 705]
        M_x = [11.756, 6.423, 53.696, 32.028, 0.529]
        M_y = [1.744, 22.289, 65.702, 16.808, 0.192]
        M_z = [62.696, 31.101, 1.778, 0.0015, 0]
        # see table 2 in the same paper
        a5 = -65.74
        a4 = 477.16
        a3 = -1279.99
        a2 = 1524.96
        a1 = -751.59
        a0 = 116.56
    elif satellite == 'Sentinel-3':
        # see table 3 in Van der Woerd & Wernand (2015): https://www.mdpi.com/1424-8220/15/10/25663/htm
        # NOTE: BAND 673 IS NOT AVAILABLE FROM POLYMER, THEREFORE I DISTRIBUTED ITS WEIGHT 50:50 TO ADJACENT BANDS
        wvls = [412, 443, 490, 510, 560, 620, 665, 681, 709, 754]
        M_x = [2.957, 10.861, 3.744, 3.750, 34.687, 41.853, 7.6185, 0.8445, 0.189, 0.006]
        M_y = [0.112, 1.711, 5.672, 23.263, 48.791, 23.949, 2.944, 0.307, 0.068, 0.002]
        M_z = [14.354, 58.356, 28.227, 4.022, 0.318, 0.026, 0, 0, 0, 0]
        # see table 4 in the same paper
        a5 = -12.5076
        a4 = 91.6345
        a3 = -249.8480
        a2 = 308.6561
        a1 = -165.4818
        a0 = 28.5608
    else:
        exit('Forel-Ule adapter not implemented for satellite ' + satellite)

    band_names2 = ['Rw' + str(wvl) for wvl in wvls]
    bands = [product.getBand(bname) for bname in band_names2]

    foreluleProduct = Product('Z0', 'Z0', width, height)
    forelule_names = ['hue_angle', 'central_wavelength', 'Forel-Ule']
    forelules = []
    for forelule_name in forelule_names:
        temp_band = foreluleProduct.addBand(forelule_name, ProductData.TYPE_FLOAT32)
        if 'angle' in forelule_name:
            temp_band.setUnit('rad')
        elif 'wavelength' in forelule_name:
            temp_band.setUnit('nm')
        else:
            temp_band.setUnit('dl')
        temp_band.setNoDataValueUsed(True)
        temp_band.setNoDataValue(np.NaN)
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

        Xs = [sum([M_x * r[band_number] for band_number, band_wvl in enumerate(wvls)]) for r in rs]
        Ys = [sum([M_y * r[band_number] for band_number, band_wvl in enumerate(wvls)]) for r in rs]
        Zs = [sum([M_z * r[band_number] for band_number, band_wvl in enumerate(wvls)]) for r in rs]

        xs = [Xs[idx] / (Xs[idx] + Ys[idx] + Zs[idx]) for idx, item in enumerate(Xs)]
        ys = [Ys[idx] / (Xs[idx] + Ys[idx] + Zs[idx]) for idx, item in enumerate(Xs)]

        # test equation
        # print((np.arctan2([1/3 - 1/3], [0.5 - 1/3]) % 2) * 180 / np.pi)
        hue_angles = [np.arctan2([ys[idx] - 1/3], [xs[idx] - 1/3]) % 2 for idx, item in enumerate(xs)]
        hue_angles_corr = [(a5 * hue_angle/100 ** 5) + (a4 * hue_angle/100 ** 4) + (a3 * hue_angle/100 ** 3) +
                           (a2 * hue_angle/100 ** 2) + (a1 * hue_angle/100) + a0 for hue_angle in hue_angles]






        #output = hue_angles_corr + central_wavelengths + ForelUle





        # Mark infinite values as NAN
        for bds in output:
            bds[bds == np.inf] = np.nan
            bds[bds == -np.inf] = np.nan

        # Write the Forel-Ule parameters per band
        for forelule, bds in zip(forelules, output):
            forelule.writePixels(0, y, width, 1, bds)

    foreluleProduct.closeIO()
    print('Writing Forel-Ule to file: {}'.format(output_file))
