#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
The Secchi Depth processor is an implementation of `Lee et al. 2002 <https://www.osapublishing.org/ao/abstract.cfm?uri=ao-41-27-5755>`_
in order to derive Secchi depth from Satellite images.
Authors: Luca Brüderlin, Jasmin Kesselring, Daniel Odermatt
"""

import os
import re
import numpy as np
import time
from netCDF4 import Dataset
from utils.auxil import log
from utils.product_fun import copy_nc, get_band_names_from_nc, get_name_width_height_from_nc, create_chunks, \
    get_satellite_name_from_product_name, get_valid_pe_from_nc, write_pixels_to_nc, create_band, read_pixels_from_nc

# key of the params section for this adapter
PARAMS_SECTION = 'SECCHIDEPTH'
# The name of the folder to which the output product will be saved
OUT_DIR = 'L2QAA'
# A pattern for the name of the file to which the output product will be saved (completed with product name)
OUT_FILENAME = 'L2QAA_{}'


def process(env, params, l1product_path, l2product_files, out_path):
    """Secchi Depth processor.
    1. Calculates Secchi depth from Polymer output

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
        raise RuntimeWarning('Secchi depth ({}) was not configured in parameters.'.format(PARAMS_SECTION))

    if "processor" not in params[PARAMS_SECTION]:
        raise RuntimeWarning('processor must be defined in the parameter file under {}.'.format(PARAMS_SECTION))

    processor = params[PARAMS_SECTION]['processor']
    if processor != 'POLYMER':
        raise RuntimeWarning('Secchi depth adapter only works with Polymer processor output')

    # Check for precursor datasets
    if processor not in l2product_files or not os.path.exists(l2product_files[processor]):
        raise RuntimeWarning('POLYMER precursor file not found ensure POLYMER is run before this adapter.')

    # Create folder for file
    product_path = l2product_files[processor]
    product_name = os.path.basename(product_path)
    product_dir = os.path.join(os.path.dirname(os.path.dirname(product_path)), OUT_DIR)
    output_file = os.path.join(product_dir, OUT_FILENAME.format(product_name))
    if os.path.isfile(output_file):
        if "overwrite" in params["General"].keys() and params['General']['overwrite'] == "true":
            log(env["General"]["log"], 'Removing file: ${}'.format(output_file), indent=1)
            os.remove(output_file)
        else:
            log(env["General"]["log"],
                'Skipping Secchi Depth, target already exists: {}'.format(OUT_FILENAME.format(product_name)), indent=1)
            return output_file
    os.makedirs(product_dir, exist_ok=True)

    chunks = 2 if "chunks" not in params[PARAMS_SECTION] else int(params[PARAMS_SECTION]["chunks"])

    log(env["General"]["log"], 'Reading POLYMER output from {}'.format(product_path))
    log(env["General"]["log"], 'Processing in {} chunks'.format(chunks), indent=1)
    try:
        with Dataset(product_path) as src, Dataset(output_file, mode='w') as dst:
            name, width, height = get_name_width_height_from_nc(src, product_path)
            product_band_names = get_band_names_from_nc(src)

            log(env["General"]["log"], 'Product:      {}'.format(name), indent=1)
            log(env["General"]["log"], 'Raster size: {} x {} pixels'.format(width, height), indent=1)
            log(env["General"]["log"], 'Bands:       {}'.format(list(product_band_names)), indent=1)

            satellite = get_satellite_name_from_product_name(product_name)

            ################## Setup band configuration for Sentinel-2 or Sentinel-3 ##################
            if satellite in ['S2A', 'S2B', 'S2C']:
                # ToDo: values for Sentinel-2 are yet to be configured
                log(env["General"]["log"], 'QAA Secchi for Sentinel-2 should be used with caution. Parameters are not fully validated.', indent=1)
                # Coefficients for the calculation of the ratio of backscattering to the sum of absorption and backscattering Lee et al. 2002
                g0 = 0.08945
                g1 = 0.1247
                # Pure Water absorption coefficient at 443, 490, 560, 665, 705 nm from Pope and Fry (1997)
                aws = [0.00696, 0.0150, 0.0619, 0.429, 0.704]
                # Pure Water backscattering at 443, 490, 560, 665, 705 nm from Morel (1974)
                bws = [0.00349, 0.00222, 0.00149, 0.00109, 0.00047282]
                # Center Wavelenghts
                wvl = [443, 490, 560, 665, 705]
                # Coefficients for the calculation of the Diffuse attenuation coefficient based on Lee et al. (2016)
                m0 = 0.005 if "m0" not in params[PARAMS_SECTION] else params[PARAMS_SECTION]["m0"]
                m1 = 4.26 if "m1" not in params[PARAMS_SECTION] else params[PARAMS_SECTION]["m1"]
                m2 = 0.52 if "m2" not in params[PARAMS_SECTION] else params[PARAMS_SECTION]["m2"]
                m3 = 10.8 if "m3" not in params[PARAMS_SECTION] else params[PARAMS_SECTION]["m3"]
                y1 = 0.265 if "y1" not in params[PARAMS_SECTION] else params[PARAMS_SECTION]["y1"]
                spectral_band_names = ['Rw443', 'Rw490', 'Rw560', 'Rw665', 'Rw705']
                a_gelb_band = 'a_gelb443_median'
                secchi_processing = secchi_s2
            elif satellite in ['S3A', 'S3B']:
                # Coefficients for the calculation of the ratio of backscattering to the sum of absorption and backscattering Lee et al. 2002
                g0 = 0.08945
                g1 = 0.1247
                # Pure Water absorption coefficient at 412.5, 442.5, 490, 510, 560, 620, 665, 673.75nm from Pope and Fry (1997)
                aws = [0.00452, 0.00696, 0.0150, 0.0325, 0.0619, 0.2755, 0.429, 0.448]
                # Pure Water backscattering at 412.5, 442.5, 490, 510, 560, 620, 665, 673.75nm from Morel (1974)
                bws = [0.00447, 0.00349, 0.00222, 0.00222, 0.00149, 0.00109, 0.00109, 0.00109]
                # Center Wavelenghts
                wvl = [412.5, 442.5, 490, 510, 560, 620, 665, 681.25]
                # Coefficients for the calculation of the Diffuse attenuation coefficient based on Lee et al. (2016)
                m0 = 0.005 if "m0" not in params[PARAMS_SECTION] else float(params[PARAMS_SECTION]["m0"])
                m1 = 4.259 if "m1" not in params[PARAMS_SECTION] else float(params[PARAMS_SECTION]["m1"])
                m2 = 0.52 if "m2" not in params[PARAMS_SECTION] else float(params[PARAMS_SECTION]["m2"])
                m3 = 10.8 if "m3" not in params[PARAMS_SECTION] else float(params[PARAMS_SECTION]["m3"])
                y1 = 0.265 if "y1" not in params[PARAMS_SECTION] else float(params[PARAMS_SECTION]["y1"])

                spectral_band_names = ['Rw412', 'Rw443', 'Rw490', 'Rw510', 'Rw560', 'Rw620', 'Rw665', 'Rw681']
                a_gelb_band = 'a_gelb443'
                secchi_processing = secchi_s3
            else:
                raise RuntimeError('Secchi adapter not implemented for satellite ' + satellite)

            secchi_band_names = ['Z' + band_name[2:] for band_name in spectral_band_names] + [a_gelb_band] + \
                                ['a_dg' + band_name[2:] for band_name in spectral_band_names] + \
                                ['a_ph' + band_name[2:] for band_name in spectral_band_names] + ['Zsd_lee', 'Zsd_jiang']
            secchi_band_units = ['m' if 'Z' in bn else ('m^-1' if 'a' in bn else None) for bn in secchi_band_names]

            valid_pixel_expression = get_valid_pe_from_nc(src)
            inclusions = []
            if valid_pixel_expression:
                inclusions = [band for band in product_band_names if band in valid_pixel_expression]
            copy_nc(src, dst, inclusions)

            secchi_bands = []
            for band_name, band_unit in zip(secchi_band_names, secchi_band_units):
                band = create_band(dst, band_name, band_unit, valid_pixel_expression)
                if len(re.findall(r'\d+', band_name)) > 0:
                    band.spectralWavelength = float(re.findall(r'\d+', band_name)[0])
                secchi_bands.append(band)

            log(env["General"]["log"], "Calculating Secchi depth.", indent=1)

            for chunk in create_chunks(width, height, chunks):

                # Reading the different bands per pixel into arrays
                rs = [read_pixels_from_nc(src, band_name, chunk["x"], chunk["y"], chunk["w"], chunk["h"]) for band_name in spectral_band_names]

                # Reading the solar zenith angle per pixel
                sza = read_pixels_from_nc(src, 'sza', chunk["x"], chunk["y"], chunk["w"], chunk["h"])

                ################## Derivation of total absorption and backscattering coefficients ###########
                # Divide r by pi for the conversion of polymer’s water-leaving reflectance output (Rw, unitless) to QAA’s expected remote sensing reflectance input (Rrs, unit per steradian, sr-1)
                rrs = [(r / np.pi) / (0.52 + (1.7 * (r / np.pi))) for r in rs]
                us = [(-g0 + (np.sqrt((g0 ** 2) + (4 * g1) * rr))) / (2 * g1) for rr in rrs]
                output = secchi_processing(len(rs[0]), rs, rrs, us, sza, aws, bws, wvl, m0, m1, m2, m3, y1)

                # Write the secchi depth per band
                for band_name, bds in zip(secchi_band_names, output):
                    write_pixels_to_nc(dst, band_name, chunk["x"], chunk["y"], chunk["w"], chunk["h"], bds)

            return output_file
    except Exception as e:
        if os.path.exists(output_file):
            os.remove(output_file)
        raise


def secchi_s2(width, rs, rrs, us, sza, aws, bws, wvl, m0, m1, m2, m3, y1):
    # Reading the different bands per pixel into arrays
    # ToDo: values for Sentinel-2 are yet to be configured
    ratioChi = rrs[3] / rrs[1]
    chi = np.log10((rrs[0] + rrs[1]) / (rrs[2] + 5 * ratioChi * rrs[3]))
    # Absorption ref. band:
    a0 = aws[2] + (10 ** (-1.146 - (1.366 * chi) - (0.469 * (chi ** 2))))
    # Backscattering suspended particles ref. band:
    bbp0 = ((us[2] * a0) / (1 - us[2])) - bws[2]
    ration = rrs[0] / rrs[2]
    Y = 2.0 * (1 - 1.2 * np.exp(-0.9 * ration))  # Lee et al. (update)
    # Backscattering susp. particles all bands
    bbps = [bbp0 * (wvl[2] / wv) ** Y for wv in wvl]
    # Absorption per band:
    a_s = [(1 - u) * (bw + bbp) / u for (u, bw, bbp) in zip(us, bws, bbps)]
    # Total backscatter per band:
    bbs = [bw + bbp for bw, bbp in zip(bws, bbps)]

    ################## Diffuse attenuation coefficient and Secchi Depth retrieval ###############
    # Kd per band:
    Kds = [(1 + m0 * sza) * a + (1 - y1 * (bw / bb)) * m1 * (1 - m2 * np.exp(-m3 * a)) * bb for (a, bw, bb) in
           zip(a_s, bws, bbs)]
    np.seterr(over='ignore')
    # Secchi depth per band:
    Zs = [(1 / (2.5 * Kd)) * np.log((np.absolute(0.14 - r)) / 0.013) for (Kd, r) in zip(Kds, rs)]

    Zsd_lee = np.empty(width)
    Zsd_lee[:] = np.nan
    Zsd_jiang = np.empty(width)
    Zsd_jiang[:] = np.nan
    Kda = np.array(Kds)
    rrsa = np.array(rrs)
    usa = np.array(us)
    Kda[Kda < 0] = np.nan
    non_nan_rows = np.any(Kda > 0, axis=0)
    if np.any(non_nan_rows is True):
        minKd_ind = np.nanargmin(Kda[:, non_nan_rows], axis=0)

        # Zsd(broadband) according to Lee et al. (2015)
        Zsd_lee[non_nan_rows] = (1 / (2.5 * Kda[:, non_nan_rows][minKd_ind].diagonal())) * np.log(
            (np.absolute(0.14 - rrsa[:, non_nan_rows][minKd_ind].diagonal())) / 0.013)

        # Zsd(broadband) according to Jiang et al.(2019)
        K_ratio = (1.04 * (1 + 5.4 * usa[:, non_nan_rows][minKd_ind].diagonal()) ** 0.5) / (
                1 / (1 - (np.sin(np.deg2rad(sza[non_nan_rows])) ** 2 / (1.34 ** 2))) ** 0.5)
        Zsd_jiang[non_nan_rows] = (1 / ((1 + K_ratio) * Kda[:, non_nan_rows][minKd_ind].diagonal())) * np.log(
            (np.absolute(0.14 - rrsa[:, non_nan_rows][minKd_ind].diagonal())) / 0.013)

    ############################### Decomposition of the total absorption coefficient ###########

    ratio = (rrs[0]) / (rrs[2])
    zeta = 0.74 + (0.2 / (0.8 + ratio))
    s = 0.015 + (0.002 / (0.6 + ratio))
    xi = np.exp(s * (442.5 - 412.5))
    # gelbstoff and detritus for 442.5 nm:
    a_g = ((a_s[0] - (zeta * a_s[0])) / (xi - zeta)) - ((aws[0] - (zeta * aws[0])) / (xi - zeta))
    # a_g for whole spectrum:
    a_g_s = [a_g * np.exp(-s * (wv - 442.5)) for wv in wvl]
    # phytoplancton pigments:
    a_ph = [a - aw - a_g_s for (a, a_g_s, aw) in zip(a_s, a_g_s, aws)]
    Zs.append(a_g)
    rrs.append(Zsd_lee)
    rrs.append(Zsd_jiang)
    output = Zs + a_ph + rrs

    # Mark infinite values as NAN
    for bds in output:
        bds[bds == np.inf] = np.nan
        bds[bds == -np.inf] = np.nan

    return output


def secchi_s3(width, rs, rrs, us, sza, aws, bws, wvl, m0, m1, m2, m3, y1):
    ratioChi = rrs[6] / rrs[2]
    chi = np.log10((rrs[1] + rrs[2]) / (rrs[4] + 5 * ratioChi * rrs[6]))
    # Absorption ref. band:
    a0 = aws[4] + (10 ** (-1.146 - (1.366 * chi) - (0.469 * (chi ** 2))))
    # Backscattering suspended particles ref. band:
    bbp0 = ((us[4] * a0) / (1 - us[4])) - bws[4]
    ration = rrs[1] / rrs[4]
    Y = 2.0 * (1 - 1.2 * np.exp(-0.9 * ration))  # Lee et al. (update)
    # Backscattering susp. particles all bands
    bbps = [bbp0 * (wvl[4] / wv) ** Y for wv in wvl]
    # Absorption per band:
    a_s = [(1 - u) * (bw + bbp) / u for (u, bw, bbp) in zip(us, bws, bbps)]
    # Total backscatter per band:
    bbs = [bw + bbp for bw, bbp in zip(bws, bbps)]

    ################## Diffuse attenuation coefficient and Secchi Depth retrieval ###############
    # Kd per band:
    Kds = [(1 + m0 * sza) * a + (1 - y1 * (bw / bb)) * m1 * (1 - m2 * np.exp(-m3 * a)) * bb for (a, bw, bb) in
           zip(a_s, bws, bbs)]
    np.seterr(over='ignore')
    # Secchi depth per band:
    Zs = [(1 / (2.5 * Kd)) * np.log((np.absolute(0.14 - r)) / 0.013) for (Kd, r) in zip(Kds, rs)]

    Zsd_lee = np.empty(width)
    Zsd_lee[:] = np.nan
    Zsd_jiang = np.empty(width)
    Zsd_jiang[:] = np.nan
    Kda = np.array(Kds)
    rrsa = np.array(rrs)
    usa = np.array(us)
    Kda[Kda < 0] = np.nan
    non_nan_rows = np.any(Kda > 0, axis=0)
    if np.any(non_nan_rows == True):
        minKd_ind = np.nanargmin(Kda[:, non_nan_rows], axis=0)

        # Zsd(broadband) according to Lee et al. (2015)
        Zsd_lee[non_nan_rows] = (1 / (2.5 * Kda[:, non_nan_rows][minKd_ind].diagonal())) * np.log(
            (np.absolute(0.14 - rrsa[:, non_nan_rows][minKd_ind].diagonal())) / 0.013)

        # Zsd(broadband) according to Jiang et al.(2019)
        K_ratio = (1.04 * (1 + 5.4 * usa[:, non_nan_rows][minKd_ind].diagonal()) ** 0.5) / (
                1 / (1 - (np.sin(np.deg2rad(sza[non_nan_rows])) ** 2 / (1.34 ** 2))) ** 0.5)
        Zsd_jiang[non_nan_rows] = (1 / ((1 + K_ratio) * Kda[:, non_nan_rows][minKd_ind].diagonal())) * np.log(
            (np.absolute(0.14 - rrsa[:, non_nan_rows][minKd_ind].diagonal())) / 0.013)

    ############################### Decomposition of the total absorption coefficient ###########

    ratio = (rrs[1]) / (rrs[4])
    zeta = 0.74 + (0.2 / (0.8 + ratio))
    s = 0.015 + (0.002 / (0.6 + ratio))
    xi = np.exp(s * (442.5 - 412.5))
    # gelbstoff and detritus for 442.5 nm:
    a_g = ((a_s[0] - (zeta * a_s[1])) / (xi - zeta)) - ((aws[0] - (zeta * aws[1])) / (xi - zeta))
    # a_g for whole spectrum:
    a_g_s = [a_g * np.exp(-s * (wv - 442.5)) for wv in wvl]
    # phytoplancton pigments:
    a_ph = [a - aw - a_g_s for (a, a_g_s, aw) in zip(a_s, a_g_s, aws)]
    Zs.append(a_g)
    rrs.append(Zsd_lee)
    rrs.append(Zsd_jiang)
    output = Zs + a_ph + rrs

    # Mark infinite values as NAN
    for bds in output:
        bds[bds == np.inf] = np.nan
        bds[bds == -np.inf] = np.nan

    return output
