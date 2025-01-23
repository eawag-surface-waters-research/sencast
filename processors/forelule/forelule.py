#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
The Forel-Ule processor is an implementation of `Giardino et al. (2019) <https://www.intechopen.com/books/geospatial-analyses-of-earth-observation-eo-data/the-color-of-water-from-space-a-case-study-for-italian-lakes-from-sentinel-2>`_
in order to estimate the Forel-Ule color from satellite images.
Adapter authors: Daniel Odermatt, James Runnalls
"""

import os
import math
import numpy as np
from colour import dominant_wavelength
from netCDF4 import Dataset
from utils.auxil import log
from utils.product_fun import copy_nc, create_band, get_band_from_nc, get_band_names_from_nc, get_name_width_height_from_nc, get_satellite_name_from_product_name, get_valid_pe_from_nc, read_pixels_from_band, write_pixels_to_nc


# key of the params section for this adapter
PARAMS_SECTION = 'FORELULE'
# The name of the folder to which the output product will be saved
OUT_DIR = 'L2FU'
# A pattern for the name of the file to which the output product will be saved (completed with product name)
OUT_FILENAME = 'L2FU_{}.nc'


def process(env, params, l1product_path, l2product_files, out_path):
    """
    Forel-Ule processor.
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
    if processor not in ['POLYMER', 'C2RCC', 'MSI-L2A']:
        raise RuntimeWarning('Forel-Ule adapter only works with Polymer, C2RCC and MSI-L2A processor output')

    # Check for precursor datasets
    if processor == "MSI-L2A":
        if not os.path.exists(l1product_path):
            raise RuntimeWarning('S2 L2A precursor file not found.')
        product_path = l1product_path
    else:
        if processor not in l2product_files or not os.path.exists(l2product_files[processor]):
            raise RuntimeWarning('Precursor file not found ensure a processor is run before this adapter.')
        product_path = l2product_files[processor]

    # Create folder for file
    product_name = os.path.splitext(os.path.basename(product_path))[0]
    product_dir = os.path.join(out_path, OUT_DIR)
    output_file = os.path.join(product_dir, OUT_FILENAME.format(product_name))
    if os.path.isfile(output_file):
        if "overwrite" in params["General"].keys() and params['General']['overwrite'] == "true":
            log(env["General"]["log"], 'Removing file: ${}'.format(output_file))
            os.remove(output_file)
        else:
            log(env["General"]["log"], 'Skipping Forel-Ule, target already exists: {}'.format(OUT_FILENAME.format(product_name)))
            return output_file
    os.makedirs(product_dir, exist_ok=True)

    log(env["General"]["log"], 'Reading processor output from {}'.format(product_path), indent=1)
    with Dataset(product_path) as src, Dataset(output_file, mode='w') as dst:
        name, width, height = get_name_width_height_from_nc(src, product_path)
        product_band_names = get_band_names_from_nc(src)

        log(env["General"]["log"], 'Product:      {}'.format(name), indent=1)
        log(env["General"]["log"], 'Raster size: {} x {} pixels'.format(width, height), indent=1)
        log(env["General"]["log"], 'Bands:       {}'.format(list(product_band_names)), indent=1)

        satellite = get_satellite_name_from_product_name(product_name)

        log(env["General"]["log"], "Defining chromaticity and hue angle coefficients.", indent=1)
        if "sensor" in params[PARAMS_SECTION] and "spectral_band_names" in params[PARAMS_SECTION] and "sample_band" in params[PARAMS_SECTION]:
            chromaticity = chromaticity_values(params[PARAMS_SECTION]["sensor"])
            hue_angle_coeff = hue_angle_coefficients(params[PARAMS_SECTION]["sensor"])
            spectral_band_names = params[PARAMS_SECTION]["spectral_band_names"]
            sample_band = params[PARAMS_SECTION]["sample_band"]
        elif satellite in ['S2A', 'S2B', 'S2C']:
            resolution = str(params["General"]['resolution'])
            if resolution not in ["10", "20", "60"]:
                raise RuntimeWarning('Forel-Ule only configured for 10, 20 & 60m Sentinel-2 resolutions')
            if resolution == "10":
                chromaticity = chromaticity_values("S2 MSI-10 m")
                hue_angle_coeff = hue_angle_coefficients("S2 MSI-10 m")
            elif resolution == "20":
                chromaticity = chromaticity_values("S2 MSI-20 m")
                hue_angle_coeff = hue_angle_coefficients("S2 MSI-20 m")
                log(env["General"]["log"], "WARNING. If run on raw product must be resampled to 20m", indent=1)
            elif resolution == "60":
                chromaticity = chromaticity_values("S2 MSI-60 m")
                hue_angle_coeff = hue_angle_coefficients("S2 MSI-60 m")
                log(env["General"]["log"], "WARNING. If run on raw product must be resampled to 60m", indent=1)
            if processor == 'POLYMER':
                chromaticity = chromaticity_values("S2 MSI-60 m")
                hue_angle_coeff = hue_angle_coefficients("S2 MSI-60 m")
                spectral_band_names = ["Rw443", "Rw490", "Rw560", "Rw665", "Rw705"]
                sample_band = 'tsm_binding740'
            elif processor == 'C2RCC':
                spectral_band_names = ["rhow_B1", "rhow_B2", "rhow_B3", "rhow_B4", "rhow_B5", "rhow_B6"]
                sample_band = 'conc_tsm'
            elif processor == 'MSI-L2A':
                spectral_band_names = ["B1", "B2", "B3", "B4", "B5", "B6"]
                sample_band = 'B1'
            else:
                raise RuntimeWarning('Forel-Ule not yet configured for S2 input: ' + processor)
        elif satellite in ['S3A', 'S3B']:
            chromaticity = chromaticity_values("OLCI")
            hue_angle_coeff = hue_angle_coefficients("OLCI")
            if processor == 'POLYMER':
                spectral_band_names = ["Rw400", "Rw412", "Rw443", "Rw490", "Rw510", "Rw560", "Rw620", "Rw665", "Rw681", "Rw709"]
                sample_band = 'tsm_binding754'
            elif processor == 'C2RCC':
                spectral_band_names = ["rhow_1", "rhow_2", "rhow_3", "rhow_4", "rhow_5", "rhow_6", "rhow_7", "rhow_8", "rhow_9", "rhow_10", "rhow_11", "rhow_12"]
                sample_band = 'conc_tsm'
            else:
                raise RuntimeWarning('Forel-Ule not yet configured for S3 processor: ' + processor)
        else:
            raise RuntimeError('Forel-Ule processor not implemented for satellite ' + satellite)

        log(env["General"]["log"], "Reading input bands and creating output file.", indent=1)

        bands = [get_band_from_nc(src, bname) for bname in spectral_band_names]
        valid_pixel_expression = get_valid_pe_from_nc(src)
        inclusions = [band for band in product_band_names if band in valid_pixel_expression]
        copy_nc(src, dst, inclusions)

        fu_band_names = ['hue_angle', 'dominant_wavelength', 'forel_ule']
        fu_band_units = ['rad', 'nm', 'dl']
        for band_name, band_unit in zip(fu_band_names, fu_band_units):
            create_band(dst, band_name, band_unit, valid_pixel_expression)

        if "max_chunk" in params[PARAMS_SECTION]:
            log(env["General"]["log"], "Splitting data into manageable chunks.", indent=1)
            max_chunk = int(params[PARAMS_SECTION]["max_chunk"])
            nw = math.ceil(width / max_chunk)
            nh = math.ceil(height / max_chunk)
            chunks = []
            for i in range(nw):
                for j in range(nh):
                    chunks.append({"x": i * max_chunk,
                                   "y": j * max_chunk,
                                   "w": min(max_chunk, width - (i * max_chunk)),
                                   "h": min(max_chunk, height - (j * max_chunk))})
        else:
            chunks = [{"x": 0, "y": 0, "w": width, "h": height}]

        for c in range(len(chunks)):
            log(env["General"]["log"], "Processing chunk {} of {}".format(c+1, len(chunks)), indent=1)
            log(env["General"]["log"], "Reading reflectance values.", indent=2)
            hue_angle_c, dom_wvl, FU = main_chunk(bands, chunks[c]["x"], chunks[c]["y"], chunks[c]["w"], chunks[c]["h"], width, height, chromaticity, hue_angle_coeff, env)
            if len(hue_angle_c) > 0:
                write_pixels_to_nc(dst, 'hue_angle', chunks[c]["x"], chunks[c]["y"], chunks[c]["w"], chunks[c]["h"], hue_angle_c)
                write_pixels_to_nc(dst, 'dominant_wavelength', chunks[c]["x"], chunks[c]["y"], chunks[c]["w"], chunks[c]["h"], dom_wvl)
                write_pixels_to_nc(dst, 'forel_ule', chunks[c]["x"], chunks[c]["y"], chunks[c]["w"], chunks[c]["h"], FU)

    return output_file


def main_chunk(bands, x, y, w, h, width, height, chromaticity, hue_angle_coeff, env):
    input_band_values = []
    input_band_lambdas = []
    for i in range(len(bands)):
        if bands[i].shape[1] == width and bands[i].shape[0] == height:
            temp_arr = np.zeros(w * h)
            read_pixels_from_band(bands[i], x, y, w, h, temp_arr)
            if np.all(temp_arr == 0):
                return [], [], []
            input_band_values.append(temp_arr)
            input_band_lambdas.append(bands[i].wavelength)
    input_band_lambdas = np.array(input_band_lambdas)

    log(env["General"]["log"], 'Interpolating reflectance spectra to: {}'.format(list(chromaticity["lambda"])),
        indent=2)
    band_values = []
    band_index = []
    for i in range(len(chromaticity["lambda"])):
        if ~np.isnan(chromaticity["band"][i]):
            lbda = chromaticity["lambda"][i]
            band_index.append(i)
            if lbda in input_band_lambdas:
                log(env["General"]["log"], 'Reflectance {}nm matched exactly.'.format(lbda), indent=3)
                index = np.where(input_band_lambdas == lbda)[0][0]
                band_values.append(input_band_values[index])
            elif lbda > np.amax(input_band_lambdas):
                log(env["General"]["log"],
                    'Reflectance {}nm larger than max, selecting max: {}nm.'.format(lbda, np.amax(input_band_lambdas)),
                    indent=3)
                index = np.where(input_band_lambdas == np.amax(input_band_lambdas))[0][0]
                band_values.append(input_band_values[index])
            elif lbda < np.amin(input_band_lambdas):
                log(env["General"]["log"],
                    'Reflectance {}nm smaller than min, selecting min: {}nm.'.format(lbda, np.amin(input_band_lambdas)),
                    indent=3)
                index = np.where(input_band_lambdas == np.amin(input_band_lambdas))[0][0]
                band_values.append(input_band_values[index])
            else:
                u_lbda = input_band_lambdas[input_band_lambdas > lbda].min()
                l_lbda = input_band_lambdas[input_band_lambdas < lbda].max()
                u_index = np.where(input_band_lambdas == u_lbda)[0][0]
                l_index = np.where(input_band_lambdas == l_lbda)[0][0]
                log(env["General"]["log"],
                    'Interpolating reflectance {}nm between {}nm and {}nm'.format(lbda, l_lbda, u_lbda), indent=3)
                f = (lbda - l_lbda) / (u_lbda - l_lbda)
                band_values.append(
                    input_band_values[l_index] + (input_band_values[u_index] - input_band_values[l_index]) * f)

    log(env["General"]["log"], "Calculating Tristimulus values", indent=2)
    X = np.sum(np.array([chromaticity["x"][band_index[i]] * band_values[i] for i in range(len(band_index))]), axis=0)
    Y = np.sum(np.array([chromaticity["y"][band_index[i]] * band_values[i] for i in range(len(band_index))]), axis=0)
    Z = np.sum(np.array([chromaticity["z"][band_index[i]] * band_values[i] for i in range(len(band_index))]), axis=0)
    x_nan = X / (X + Y + Z)
    y_nan = Y / (X + Y + Z)
    x = x_nan[~np.isnan(x_nan)]
    y = y_nan[~np.isnan(x_nan)]

    if len(x) == 0:
        return [], [], []

    hue_angle_c = np.zeros(len(x_nan))
    dom_wvl = np.zeros(len(x_nan))
    hue_angle_c[:] = np.nan
    dom_wvl[:] = np.nan

    log(env["General"]["log"], "Calculating hue angle", indent=2)
    hue_angle = get_hue_angle(x, y)
    hue_angle_c[~np.isnan(x_nan)] = (hue_angle_coeff["a5"] * (hue_angle / 100) ** 5) + (
                hue_angle_coeff["a4"] * (hue_angle / 100) ** 4) + \
                                    (hue_angle_coeff["a3"] * (hue_angle / 100) ** 3) + (
                                                hue_angle_coeff["a2"] * (hue_angle / 100) ** 2) + \
                                    (hue_angle_coeff["a"] * (hue_angle / 100)) + hue_angle_coeff["const"] + hue_angle

    log(env["General"]["log"], "Calculating dominant wavelength", indent=2)
    try:
        dom_wvl[~np.isnan(x_nan)] = dominant_wavelength_wrapper(x, y)
    except Exception as e:
        log(env["General"]["log"], e, indent=3)
        log(env["General"]["log"], "Failed to calculate dominant wavelength", indent=3)

    log(env["General"]["log"], "Calculating Forel-Ule", indent=2)
    FU = get_FU_class(hue_angle_c)

    return hue_angle_c, dom_wvl, FU


def dominant_wavelength_wrapper(x, y, max_chunk=1000):
    if len(x) > max_chunk:
        out = np.zeros(len(x))
        out[:] = np.nan
        n = math.ceil(len(x) / max_chunk)
        for i in range(n):
            start = i * max_chunk
            end = min(len(x), start + max_chunk)
            out[start:end] = dominant_wavelength(np.swapaxes(np.array([x[start:end], y[start:end]]), 0, 1), [1 / 3, 1 / 3])[0]
        return out
    else:
        return dominant_wavelength(np.swapaxes(np.array([x, y]), 0, 1), [1 / 3, 1 / 3])[0]


def get_hue_angle(x, y):
    """ Yields values for FU 1-21: [229.45, 224.79, 217.12, 203.09, 178.91, 147.64, 118.289, 99.75, 88.37, 78.25, 71.08, 65.06, 59.56, 53.64, 47.89, 42.18, 37.23, 32.63, 28.38, 24.3, 20.98]
        See also Table 6 in Novoa et al. (2013): https://www.jeos.org/index.php/jeos_rp/article/view/13057"""
    return (np.arctan2(x - 1/3, y - 1/3) * 180 / np.pi - 90) * -1


def get_FU_class(hue_angle):
    # Using the x, y for each FU class given in Novoa et al. (2013): https://www.jeos.org/index.php/jeos_rp/article/view/13057
    fu_hue_angles = np.array([229.4460181266636, 224.78594453445439, 217.11686068327026,
                              203.09011699782403, 178.906701806006, 147.63906244063008,
                              118.28627616573007, 99.752424941653771, 88.3676604984623,
                              78.253096073802809, 71.081710836489165, 65.061040636646254,
                              59.558194784801302, 53.640209130667706, 47.89451269235753,
                              42.176741925157287, 37.234833981574667, 32.629686435712884,
                              28.38124615489167, 24.349355340488756, 20.98489783588218])
    FU = 21.0 - np.searchsorted(np.sort(fu_hue_angles), hue_angle, side='left').astype(float)
    FU[np.isnan(hue_angle)] = np.nan
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
            "band": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
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
