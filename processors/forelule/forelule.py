#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""The Forel-Ule processor is an implementation of `Giardino et al. (2019) <https://www.intechopen.com/books/geospatial-analyses-of-earth-observation-eo-data/the-color-of-water-from-space-a-case-study-for-italian-lakes-from-sentinel-2>`_
in order to estimate the Forel-Ule color from satellite images.
Adapter authors: Daniel Odermatt
"""

import os
import numpy as np
from colour import dominant_wavelength
from snappy import ProductIO, ProductData, Product, ProductUtils
from utils.product_fun import get_satellite_name_from_product_name
from utils.auxil import log

# key of the params section for this adapter
PARAMS_SECTION = 'FORELULE'

# the file name pattern for output file
FILENAME = 'L2FU_{}'
FILEFOLDER = 'L2FU'


def process(env, params, l1product_path, l2product_files, out_path):
    """Forel-Ule processor.
        1. Calculates a hue product from Polymer output

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
        raise RuntimeWarning('Forel-Ule was not configured in parameters.')

    if "processor" not in params[PARAMS_SECTION]:
        raise RuntimeWarning('processor must be defined in the parameter file.')

    processor = params[PARAMS_SECTION]['processor']
    if processor not in ['POLYMER', 'C2RCC']:
        raise RuntimeWarning('Forel-Ule adapter only works with Polymer and C2RCC processor output')

    # Check for precursor datasets
    if processor not in l2product_files or not os.path.exists(l2product_files[processor]):
        raise RuntimeWarning('Precursor file not found ensure a processor is run before this adapter.')

    # Create folder for file
    product_path = l2product_files[processor]
    product_name = os.path.basename(product_path)
    product_dir = os.path.join(os.path.dirname(os.path.dirname(product_path)), FILEFOLDER)
    output_file = os.path.join(product_dir, FILENAME.format(product_name))
    l2product_files["FORELULE"] = output_file
    if os.path.isfile(output_file):
        if "synchronise" in params["General"].keys() and params['General']['synchronise'] == "false":
            log(env["General"]["log"], 'Removing file: ${}'.format(output_file))
            os.remove(output_file)
        else:
            log(env["General"]["log"], 'Skipping Forel-Ule, target already exists: {}'.format(FILENAME.format(product_name)))
            return output_file
    os.makedirs(product_dir, exist_ok=True)

    log(env["General"]["log"], 'Reading processor output from {}'.format(product_path), indent=1)
    product = ProductIO.readProduct(product_path)
    width = product.getSceneRasterWidth()
    height = product.getSceneRasterHeight()
    name = product.getName()
    description = product.getDescription()
    product_band_names = product.getBandNames()

    log(env["General"]["log"], 'Product:      {}, {}'.format(name, description), indent=1)
    log(env["General"]["log"], 'Raster size: {} x {} pixels'.format(width, height), indent=1)
    log(env["General"]["log"], 'Bands:       {}'.format(list(product_band_names)), indent=1)

    satellite = get_satellite_name_from_product_name(product_name)

    log(env["General"]["log"], "Defining chromaticity and hue angle coefficients.", indent=1)
    if "sensor" in params[PARAMS_SECTION] and "spectral_band_names" in params[PARAMS_SECTION] and "sample_band" in params[PARAMS_SECTION]:
        chromaticity = chromaticity_values(params[PARAMS_SECTION]["sensor"])
        hue_angle_coeff = hue_angle_coefficients(params[PARAMS_SECTION]["sensor"])
        spectral_band_names = params[PARAMS_SECTION]["spectral_band_names"]
        sample_band = params[PARAMS_SECTION]["sample_band"]
    elif satellite in ['S2A', 'S2B']:
        resolution = str(params["General"]['resolution'])
        if resolution not in ["10", "20", "60"]:
            raise RuntimeWarning('Forel-Ule only configured for 10, 20 & 60m Sentinel-2 resolutions')
        if resolution == "10":
            chromaticity = chromaticity_values("S2 MSI-10 m")
            hue_angle_coeff = hue_angle_coefficients("S2 MSI-10 m")
        elif resolution == "20":
            chromaticity = chromaticity_values("S2 MSI-20 m")
            hue_angle_coeff = hue_angle_coefficients("S2 MSI-20 m")
        elif resolution == "60":
            chromaticity = chromaticity_values("S2 MSI-60 m")
            hue_angle_coeff = hue_angle_coefficients("S2 MSI-60 m")
        if processor == 'POLYMER':
            raise RuntimeWarning('Forel-Ule not yet configured for S2 POLYMER inputs.')
            spectral_band_names = ["Rw443", "Rw490", "Rw560", "Rw665", "Rw705"]
            sample_band = 'tsm_binding740'
        elif processor == 'C2RCC':
            spectral_band_names = ["rhow_B1", "rhow_B2", "rhow_B3", "rhow_B4", "rhow_B5", "rhow_B6"]
            sample_band = 'conc_tsm'
    elif satellite in ['S3A', 'S3B']:
        chromaticity = chromaticity_values("OLCI")
        hue_angle_coeff = hue_angle_coefficients("OLCI")
        if processor == 'POLYMER':
            spectral_band_names = ["Rw400", "Rw412", "Rw443", "Rw490", "Rw510", "Rw560", "Rw620", "Rw665", "Rw681", "Rw681", "Rw709", "Rw709"]
            sample_band = 'tsm_binding754'
        elif processor == 'C2RCC':
            spectral_band_names = ["rhow_1", "rhow_2", "rhow_3", "rhow_4", "rhow_5", "rhow_6", "rhow_7", "rhow_8", "rhow_9", "rhow_10", "rhow_11", "rhow_12"]
            sample_band = 'conc_tsm'
    else:
        exit('Forel-Ule adapter not implemented for satellite ' + satellite)

    log(env["General"]["log"], "Reading input bands and creating output file.", indent=1)
    bands = [product.getBand(bname) for bname in spectral_band_names]
    foreluleProduct = Product('Z0', 'Z0', width, height)
    forelule_names = ['hue_angle', 'dominant_wavelength', 'forel_ule']
    valid_pixel_expression = product.getBand(sample_band).getValidPixelExpression()
    nodata_value = bands[0].getNoDataValue()

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

    writer = ProductIO.getProductWriter('NetCDF4-BEAM')

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

    log(env["General"]["log"], "Reading reflectance values.", indent=1)
    input_band_values = len(bands) * [np.zeros(width * height)]
    input_band_lambdas = []
    for i in range(len(bands)):
        input_band_values[i][:] = np.nan
        bands[i].readPixels(0, 0, width, height, input_band_values[i])
        input_band_lambdas.append(bands[i].getSpectralWavelength())
    input_band_lambdas = np.array(input_band_lambdas)

    log(env["General"]["log"], 'Interpolating reflectance spectra to: {}'.format(list(chromaticity["lambda"])), indent=1)
    band_values = []
    for i in range(len(chromaticity["lambda"])):
        lbda = chromaticity["lambda"][i]
        if lbda in input_band_lambdas:
            log(env["General"]["log"], 'Reflectance {}nm matched exactly.'.format(lbda), indent=2)
            index = np.where(input_band_lambdas == lbda)[0][0]
            band_values.append(input_band_values[index])
        elif lbda > np.amax(input_band_lambdas):
            log(env["General"]["log"], 'Reflectance {}nm larger than max, selecting max: {}nm.'.format(lbda, np.amax(input_band_lambdas)), indent=2)
            index = np.where(input_band_lambdas == np.amax(input_band_lambdas))[0][0]
            band_values.append(input_band_values[index])
        elif lbda < np.amin(input_band_lambdas):
            log(env["General"]["log"], 'Reflectance {}nm smaller than min, selecting min: {}nm.'.format(lbda, np.amin(input_band_lambdas)), indent=2)
            index = np.where(input_band_lambdas == np.amin(input_band_lambdas))[0][0]
            band_values.append(input_band_values[index])
        else:
            u_lbda = input_band_lambdas[input_band_lambdas > lbda].min()
            l_lbda = input_band_lambdas[input_band_lambdas < lbda].max()
            u_index = np.where(input_band_lambdas == u_lbda)[0][0]
            l_index = np.where(input_band_lambdas == l_lbda)[0][0]
            log(env["General"]["log"], 'Interpolating reflectance {}nm between {}nm and {}nm'.format(lbda, l_lbda, u_lbda), indent=2)
            f = (lbda - l_lbda)/(u_lbda - l_lbda)
            band_values.append(band_values[l_index] + (band_values[u_index]-band_values[l_index])*f)

    log(env["General"]["log"], "Calculating Tristimulus values", indent=1)
    X = np.sum(np.array([chromaticity["x"][i] * band_values[i] for i in range(len(chromaticity["lambda"]))]), axis=0)
    Y = np.sum(np.array([chromaticity["y"][i] * band_values[i] for i in range(len(chromaticity["lambda"]))]), axis=0)
    Z = np.sum(np.array([chromaticity["z"][i] * band_values[i] for i in range(len(chromaticity["lambda"]))]), axis=0)
    x = X / (X + Y + Z)
    y = Y / (X + Y + Z)
    z = Z / (X + Y + Z)

    log(env["General"]["log"], "Calculating hue angle", indent=1)
    hue_angle = get_hue_angle(x, y)
    hue_angle_corr = (hue_angle_coeff["a5"] * (hue_angle / 100) ** 5) + (hue_angle_coeff["a4"] * (hue_angle / 100) ** 4) + (hue_angle_coeff["a3"] * (hue_angle / 100) ** 3) + \
                     (hue_angle_coeff["a2"] * (hue_angle / 100) ** 2) + (hue_angle_coeff["a1"] * (hue_angle / 100)) + hue_angle_coeff["a"] + hue_angle

    hue_angle_c = (hue_angle_coeff["a5"] * (hue_angle / 100) ** 5) + (hue_angle_coeff["a4"] * (hue_angle / 100) ** 4) +\
                  (hue_angle_coeff["a3"] * (hue_angle / 100) ** 3) + (hue_angle_coeff["a2"] * (hue_angle / 100) ** 2) + \
                  (hue_angle_coeff["a1"] * (hue_angle / 100)) + hue_angle_coeff["a"] + hue_angle

    exit()

    log(env["General"]["log"], "Calculating Forel-Ule parameters.")

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

            # Most products have no data value NaN, but mosaics come with no data zero
            if (not np.isnan(X) and not np.isnan(Y) and not np.isnan(Z)) and \
                    (X != nodata_value and Y != nodata_value and Z != nodata_value) and \
                    (X != 0 and Y != 0 and Z != 0):
                x = X / (X + Y + Z)
                y = Y / (X + Y + Z)
                z = Z / (X + Y + Z)

            # CALCULATE AND CORRECT HUE ANGLE ACCORDING TO Van der Woerd and Wernand (2018): https://www.mdpi.com/2072-4292/10/2/180
                hue_angle = get_hue_angle(x, y)

                hue_angle_corr = (hue_angle["a5"] * (hue_angle/100) ** 5) + (hue_angle["a4"] * (hue_angle/100) ** 4) + (hue_angle["a3"] * (hue_angle/100) ** 3) +\
                                 (hue_angle["a2"] * (hue_angle/100) ** 2) + (hue_angle["a1"] * (hue_angle/100)) + hue_angle["a"] + hue_angle

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
    log(env["General"]["log"], 'Writing Forel-Ule to file: {}'.format(output_file))
    return output_file


def get_hue_angle(x, y):
    """ Yields values for FU 1-21: [229.45, 224.79, 217.12, 203.09, 178.91, 147.64, 118.289, 99.75, 88.37, 78.25, 71.08, 65.06, 59.56, 53.64, 47.89, 42.18, 37.23, 32.63, 28.38, 24.3, 20.98]
        See also Table 6 in Novoa et al. (2013): https://www.jeos.org/index.php/jeos_rp/article/view/13057"""
    return (np.arctan2(x - 1/3, y - 1/3) * 180 / np.pi - 90) * -1


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


def chromaticity_values(sensor):
    data = {
        "MERIS FR and RR": {
            "lambda": [400, 413, 443, 490, 510, 560, 620, 665, 681, 708, 710],
            "band": [np.nan, 1, 2, 3, 4, 5, 6, 7, 8, 9, np.nan],
            "x": [0.154,  2.957, 10.861, 3.744,  3.750, 34.687, 41.853, 7.619, 0.844, 0.189, 0.006],
            "y": [0.004,  0.112,  1.711, 5.672, 23.263, 48.791, 23.949, 2.944, 0.307, 0.068, 0.002],
            "z": [0.731, 14.354, 58.356, 28.227, 4.022,  0.618,  0.026, 0.000, 0.000, 0.000, 0.000],
            "source": "Table 1. Van der Woerd & Wernand (2018): https://www.mdpi.com/2072-4292/10/2/180"
        },
        "CZCS": {
            "lambda": [400, 443, 520, 550, 670, 710],
            "band": [np.nan, 1, 2, 3, 4, np.nan],
            "x": [2.217, 13.237, 5.195, 50.856, 34.797, 0.364],
            "y": [0.082, 4.825, 25.217, 56.997, 19.571, 0.132],
            "z": [10.745, 74.083, 21.023, 0.462, 0.022, 0.000],
            "source": "Table 1. Van der Woerd & Wernand (2018): https://www.mdpi.com/2072-4292/10/2/180"
        },
        "MODIS-500": {
            "lambda": [400, 466, 553, 647, 710],
            "band": [np.nan, 3, 4, 1, np.nan],
            "x": [5.3754, 13.3280, 46.3789, 40.2774, 1.3053],
            "y": [0.337, 15.756, 67.793, 22.459, 0.478],
            "z": [26.827, 73.374, 6.111, 0.024, 0.000],
            "source": "Table 1. Van der Woerd & Wernand (2018): https://www.mdpi.com/2072-4292/10/2/180"
        },
        "S2 MSI-10 m": {
            "lambda": [400, 490, 560, 665, 710],
            "band": [np.nan, 2, 3, 4, np.nan],
            "x": [8.356, 12.040, 53.696, 32.087, 0.487],
            "y": [0.993, 23.122, 65.702, 16.830, 0.177],
            "z": [43.487, 61.055, 1.778, 0.015, 0.000],
            "source": "Table 1. Van der Woerd & Wernand (2018): https://www.mdpi.com/2072-4292/10/2/180"
        },
        "S2 MSI-20 m": {
            "lambda": [400, 490, 560, 665, 705, 710],
            "band": [np.nan, 2, 3, 4, 5, np.nan],
            "x": [8.356, 12.040, 53.696, 32.028, 0.529, 0.016],
            "y": [0.993, 23.122, 65.702, 16.808, 0.192, 0.006],
            "z": [43.487, 61.055, 1.778, 0.015, 0.000, 0.000],
            "source": "Table 1. Van der Woerd & Wernand (2018): https://www.mdpi.com/2072-4292/10/2/180"
        },
        "S2 MSI-60 m": {
            "lambda": [400, 443, 490, 560, 665, 705, 710],   # Let's assume R440 is a typo and should be R400
            "band": [np.nan, 1, 2, 3, 4, 5, np.nan],
            "x": [2.217, 11.756, 6.423, 53.696, 32.028, 0.529, 0.016],
            "y": [0.082, 1.744, 22.289, 65.702, 16.808, 0.192, 0.006],
            "z": [10.745, 62.696, 31.101, 1.778, 0.015, 0.000, 0.000],
            "source": "Table 1. Van der Woerd & Wernand (2018): https://www.mdpi.com/2072-4292/10/2/180"
        },
        "Landsat 8 OLI": {
            "lambda": [400, 443, 482, 561, 655, 710],
            "band": [np.nan, 1, 2, 3, 4, np.nan],
            "x": [2.217, 11.053, 6.950, 51.135, 34.457, 0.852],
            "y": [0.082, 1.320, 21.053, 66.023, 18.034, 0.311],
            "z": [10.745, 58.038, 34.931, 2.606, 0.016, 0.000],
            "source": "Table 1. Van der Woerd & Wernand (2018): https://www.mdpi.com/2072-4292/10/2/180"
        },
        "Landsat 7 ETM+": {
            "lambda": [400, 485, 565, 660, 710],
            "band": [np.nan, 1, 2, 3, np.nan],
            "x": [7.8195, 13.104, 53.791, 31.304, 0.6463],
            "y": [0.807, 24.097, 65.801, 15.883, 0.235],
            "z": [40.336, 63.845, 2.142, 0.013, 0.000],
            "source": "Table 1. Van der Woerd & Wernand (2018): https://www.mdpi.com/2072-4292/10/2/180"
        },
        "MERIS": {
            "lambda": [400, 412.5, 442.5, 490, 510, 560, 620, 665, 681.25, 708, 710],
            "band": [np.nan, 1, 2, 3, 4, 5, 6, 7, 8, 9, np.nan],
            "x": [0.154, 2.813, 10.867, 3.883, 3.750, 34.687, 41.853, 7.619, 0.844, 0.189, 0.006],
            "y": [0.004, 0.104, 1.687, 5.703, 23.263, 48.791, 23.949, 2.944, 0.307, 0.068, 0.002],
            "z": [0.731, 13.638, 58.288, 29.011, 4.022, 0.618, 0.026, 0.000, 0.000, 0.000, 0.000],
            "source": "Table 2. Van der Woerd & Wernand (2015): https://www.mdpi.com/1424-8220/15/10/25663/htm"
        },
        "OLCI": {
            "lambda": [400, 413, 443, 490, 510, 560, 620, 665, 673.5, 681.25, 708.75, 710],
            "band": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
            "x": [0.154, 2.957, 10.861, 3.744, 3.750, 34.687, 41.853, 7.323, 0.591, 0.549, 0.189, 0.006],
            "y": [0.004, 0.112, 1.711, 5.672, 23.263, 48.791, 23.949, 2.836, 0.216, 0.199, 0.068, 0.002],
            "z": [0.731, 14.354, 58.356, 28.227, 4.022, 0.618, 0.026, 0.000, 0.000, 0.000, 0.000, 0.000],
            "source": "Table 3. Van der Woerd & Wernand (2015): https://www.mdpi.com/1424-8220/15/10/25663/htm"
        },
        "MODIS": {
            "lambda": [400, 412.5, 443, 490, 531, 551, 667, 678, 710],
            "band": [np.nan, 8, 9, 10, 11, 12, 13, 14, np.nan],
            "x": [0.154, 2.957, 10.861, 4.031, 3.989, 49.037, 34.586, 0.829, 0.222],
            "y": [0.004, 0.112, 1.711, 11.106, 22.579, 51.477, 19.452, 0.301, 0.080],
            "z": [0.731, 14.354, 58.356, 29.993, 2.618, 0.262, 0.022, 0.000, 0.000],
            "source": "Table 3. Van der Woerd & Wernand (2015): https://www.mdpi.com/1424-8220/15/10/25663/htm"
        },
        "SeaWiFS": {
            "lambda": [400, 413, 443, 490, 510, 555, 670, 710],
            "band": [np.nan, 1, 2, 3, 4, 5, 6, np.nan],
            "x": [0.154, 2.957, 10.861, 3.744, 3.455, 52.304, 32.825, 0.364],
            "y": [0.004, 0.112, 1.711, 5.672, 21.929, 59.454, 17.810, 0.132],
            "z": [0.731, 14.354, 58.356, 28.227, 3.967, 0.682, 0.018, 0.000],
            "source": "Table 3. Van der Woerd & Wernand (2015): https://www.mdpi.com/1424-8220/15/10/25663/htm"
        },
    }
    if sensor in data.keys():
        return data[sensor]
    else:
        raise RuntimeWarning("Sensor: "+sensor+" does not have chromaticity values available.")


def hue_angle_coefficients(sensor):
    data = {
        "MERIS FR and RR": {
            "a": -164.70,
            "a2": 305.24,
            "a3": -244.70,
            "a4": 88.93,
            "a5": -12.05,
            "const": 28.53,
            "source": "Table 2. Van der Woerd & Wernand (2018): https://www.mdpi.com/2072-4292/10/2/180"
        },
        "CZCS": {
            "a": -1078.62,
            "a2": 1927.61,
            "a3": -1475-80,
            "a4": -510.37,
            "a5": -65.95,
            "const": 202.25,
            "source": "Table 2. Van der Woerd & Wernand (2018): https://www.mdpi.com/2072-4292/10/2/180"
        },
        "MODIS-500": {
            "a": -1157.00,
            "a2": 2042.42,
            "a3": -1552.76,
            "a4": 534.04,
            "a5": -68.36,
            "const": 223.04,
            "source": "Table 2. Van der Woerd & Wernand (2018): https://www.mdpi.com/2072-4292/10/2/180"
        },
        "S2 MSI-10 m": {
            "a": -1979.71,
            "a2": 3677.75,
            "a3": -3006.04,
            "a4": 1139.90,
            "a5": -164.83,
            "const": 371.38,
            "source": "Table 2. Van der Woerd & Wernand (2018): https://www.mdpi.com/2072-4292/10/2/180"
        },
        "S2 MSI-20 m": {
            "a": -1943.57,
            "a2": 3612.17,
            "a3": -2950.14,
            "a4": 1117.08,
            "a5": -161.23,
            "const": 364.28,
            "source": "Table 2. Van der Woerd & Wernand (2018): https://www.mdpi.com/2072-4292/10/2/180"
        },
        "S2 MSI-60 m": {
            "a": -751.59,
            "a2": 1524.96,
            "a3": -1279.99,
            "a4": 477.16,
            "a5": -65.74,
            "const": 116.56,
            "source": "Table 2. Van der Woerd & Wernand (2018): https://www.mdpi.com/2072-4292/10/2/180"
        },
        "Landsat 8 OLI": {
            "a": -533.61,
            "a2": 1134.19,
            "a3": -981.83,
            "a4": 373.81,
            "a5": -52.16,
            "const": 76.72,
            "source": "Table 2. Van der Woerd & Wernand (2018): https://www.mdpi.com/2072-4292/10/2/180"
        },
        "Landsat 7 ETM+": {
            "a": -918.11,
            "a2": 1852.50,
            "a3": -1559.86,
            "a4": 594.17,
            "a5": -84.94,
            "const": 151.49,
            "source": "Table 2. Van der Woerd & Wernand (2018): https://www.mdpi.com/2072-4292/10/2/180"
        },
        "MERIS": {
            "a": -164.6960,
            "a2": 305.2361,
            "a3": -244.6960,
            "a4": 88.9325,
            "a5": -12.0506,
            "const": 28.5255,
            "source": "Table 4. Van der Woerd & Wernand (2015): https://www.mdpi.com/1424-8220/15/10/25663/htm"
        },
        "OLCI": {
            "a": -165.4818,
            "a2": 308.6561,
            "a3": -249.8480,
            "a4": 91.6345,
            "a5": -12.5076,
            "const": 28.5608,
            "source": "Table 4. Van der Woerd & Wernand (2015): https://www.mdpi.com/1424-8220/15/10/25663/htm"
        },
        "MODIS": {
            "a": -666.5981,
            "a2": 1262.0348,
            "a3": -1011.7151,
            "a4": 362.6179,
            "a5": -48.0880,
            "const": 113.9215,
            "source": "Table 4. Van der Woerd & Wernand (2015): https://www.mdpi.com/1424-8220/15/10/25663/htm"
        },
        "SeaWiFS": {
            "a": -552.2701,
            "a2": 1154.6030,
            "a3": -978.1648,
            "a4": 363.2770,
            "a5": -49.4377,
            "const": 78.2940,
            "source": "Table 4. Van der Woerd & Wernand (2015): https://www.mdpi.com/1424-8220/15/10/25663/htm"
        },
    }
    if sensor in data.keys():
        return data[sensor]
    else:
        raise RuntimeWarning("Sensor: "+sensor+" does not have hue angle coefficients available.")
