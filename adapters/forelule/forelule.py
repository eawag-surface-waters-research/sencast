#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""The Forel-Ule adapter is an implementation of `Giardino et al. (2019) <https://www.intechopen.com/books/geospatial-analyses-of-earth-observation-eo-data/the-color-of-water-from-space-a-case-study-for-italian-lakes-from-sentinel-2>`_
in order to estimate the Forel-Ule color from satellite images.
Adapter authors: Daniel Odermatt
"""

import os
import numpy as np
from colour import dominant_wavelength
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
    product_band_names = product.getBandNames()

    print('Product:      {}, {}'.format(name, description))
    print('Raster size: {} x {} pixels'.format(width, height))
    print('Bands:       {}'.format(list(product_band_names)))

    satellite = get_satellite_name_from_name(product_name)

    ################## Derivation of the hue angle ##################
    if satellite in ['S2A', 'S2B']:
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
        valid_pixel_expression = product.getBand('tsm_binding740').getValidPixelExpression()
    elif satellite in ['S3A', 'S3B']:
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
        valid_pixel_expression = product.getBand('tsm_binding754').getValidPixelExpression()
    else:
        exit('Forel-Ule adapter not implemented for satellite ' + satellite)

    spectral_band_names = ['Rw' + str(wvl) for wvl in wvls]
    bands = [product.getBand(bname) for bname in spectral_band_names]

    foreluleProduct = Product('Z0', 'Z0', width, height)
    forelule_names = ['hue_angle', 'dominant_wavelength', 'forel_ule']

    for band_name in product_band_names:
        if band_name in valid_pixel_expression:
            ProductUtils.copyBand(band_name, product, foreluleProduct, True)

    forelule_bands = []
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
        temp_band.setValidPixelExpression(valid_pixel_expression)
        forelule_bands.append(temp_band)

    writer = ProductIO.getProductWriter('NetCDF4-CF')

    ProductUtils.copyGeoCoding(product, foreluleProduct)

    foreluleProduct.setProductWriter(writer)
    foreluleProduct.writeHeader(output_file)

    rs_row = [np.zeros(width, dtype=np.float32) for _ in range(len(spectral_band_names))]

    # Write valid pixel bands
    for band_name in product_band_names:
        if band_name in valid_pixel_expression:
            temp_arr = np.zeros(width * height)
            product.getBand(band_name).readPixels(0, 0, width, height, temp_arr)
            foreluleProduct.getBand(band_name).writePixels(0, 0, width, height, temp_arr)

    print("Calculating Forel-Ule parameters.")

    for n_row in range(height):
        hue_angles_corr = []
        dom_wvls = []
        FUs = []

        # Reading the different bands per pixel into arrays
        rs_row = [b.readPixels(0, n_row, width, 1, r) for (b, r) in zip(bands, rs_row)]

        for rs in zip(*rs_row):

            X = sum([M_x[n_band] * rs[n_band] for n_band in range(len(spectral_band_names))])
            Y = sum([M_y[n_band] * rs[n_band] for n_band in range(len(spectral_band_names))])
            Z = sum([M_z[n_band] * rs[n_band] for n_band in range(len(spectral_band_names))])

            if not np.isnan(X) and not np.isnan(Y) and not np.isnan(Z):
                x = X / (X + Y + Z)
                y = Y / (X + Y + Z)
                z = Z / (X + Y + Z)

            # CALCULATE AND CORRECT HUE ANGLE ACCORDING TO Van der Woerd and Wernand (2018): https://www.mdpi.com/2072-4292/10/2/180
                hue_angle = get_hue_angle(x, y)

                hue_angle_corr = (a5 * (hue_angle/100) ** 5) + (a4 * (hue_angle/100) ** 4) + (a3 * (hue_angle/100) ** 3) +\
                                 (a2 * (hue_angle/100) ** 2) + (a1 * (hue_angle/100)) + a0 + hue_angle

            # CALCULATE DOMINANT WAVELENGTH ASSUMING WHITE AT x,y=1/3
                if np.isnan(x):
                    dom_wvl = np.nan
                else:
                    dom_wvl = dominant_wavelength([x, y], [1/3, 1/3])[0]

            # CALCULATE THE FU CLASS FOR A GIVEN x, y
                FU = get_FU_class(hue_angle_corr)

                hue_angles_corr.append(np.float32(hue_angle_corr))
                dom_wvls.append(np.float32(dom_wvl))
                FUs.append(np.float32(FU))

            else:
                hue_angles_corr.append(np.nan)
                dom_wvls.append(np.nan)
                FUs.append(np.nan)

        output = [np.array(hue_angles_corr)] + [np.array(dom_wvls)] + [np.array(FUs)]

        # Mark infinite values as NAN
        #for bds in output:
        #    bds[bds == np.inf] = np.nan
        #    bds[bds == -np.inf] = np.nan

        # Write the Forel-Ule parameters per band
        for forelule, bds in zip(forelule_bands, output):
            forelule.writePixels(0, n_row, width, 1, bds)

    foreluleProduct.closeIO()
    print('Writing Forel-Ule to file: {}'.format(output_file))

def get_hue_angle(x, y):
    # yields values for FU 1-21:
    # [229.45, 224.79, 217.12, 203.09, 178.91, 147.64, 118.289, 99.75, 88.37, 78.25, 71.08, 65.06, 59.56, 53.64, 47.89, 42.18, 37.23, 32.63, 28.38, 24.3, 20.98]
    # see also Table 6 in Novoa et al. (2013): https://www.jeos.org/index.php/jeos_rp/article/view/13057
    hue_angle = (np.arctan2(x - 1/3, y - 1/3) * 180 / np.pi - 90) * -1

    return hue_angle


def get_FU_class(hue_angle):

    FU = False
    # using the x, y for each FU class given in Novoa et al. (2013): https://www.jeos.org/index.php/jeos_rp/article/view/13057
    fu_hue_angles = [229.4460181266636, 224.78594453445439, 217.11686068327026, # FU 1-3
                   203.09011699782403, 178.906701806006, 147.63906244063008,
                   118.28627616573007, 99.752424941653771, 88.3676604984623,
                   78.253096073802809, 71.081710836489165, 65.061040636646254,
                   59.558194784801302, 53.640209130667706, 47.89451269235753,
                   42.176741925157287, 37.234833981574667, 32.629686435712884,
                   28.38124615489167, 24.349355340488756, 20.98489783588218]    # FU 18-21

    fu_hue_bounds = [(j + i) / 2 for i, j in zip(fu_hue_angles[:-1], fu_hue_angles[1:])]

    for i in range(21):
        if hue_angle > fu_hue_bounds[i]:
            FU = i + 1
            break

    if not FU:
        FU = np.nan

    return FU
