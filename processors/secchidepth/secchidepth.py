#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""The Secchi Depth processor is an implementation of `Lee et al. 2002 <https://www.osapublishing.org/ao/abstract.cfm?uri=ao-41-27-5755>`_
in order to derive Secchi depth from Satellite images.
Adapter authors: Luca Brüderlin, Jasmin Kesselring, Daniel Odermatt
"""

import os
import re
import numpy as np
from snappy import ProductIO, ProductData, Product, ProductUtils
from utils.product_fun import get_satellite_name_from_product_name


# key of the params section for this adapter
PARAMS_SECTION = 'SECCHIDEPTH'

# the file name pattern for output file
FILENAME = 'L2QAA_{}'
FILEFOLDER = 'L2QAA'


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
        raise RuntimeWarning('Secchi depth was not configured in parameters.')
    print("Applying Secchi Depth...")

    if "processor" not in params[PARAMS_SECTION]:
        raise RuntimeWarning('processor must be defined in the parameter file.')

    processor = params[PARAMS_SECTION]['processor']
    if processor != 'POLYMER':
        raise RuntimeWarning('Secchi depth adapter only works with Polymer processor output')

    # Check for precursor datasets
    if processor not in l2product_files or not os.path.exists(l2product_files[processor]):
        raise RuntimeWarning('POLYMER precursor file not found ensure POLYMER is run before this adapter.')

    # Create folder for file
    product_path = l2product_files[processor]
    product_name = os.path.basename(product_path)
    product_dir = os.path.join(os.path.dirname(os.path.dirname(product_path)), FILEFOLDER)
    output_file = os.path.join(product_dir, FILENAME.format(product_name))
    l2product_files["SECCHIDEPTH"] = output_file
    if os.path.isfile(output_file):
        if "synchronise" in params["General"].keys() and params['General']['synchronise'] == "false":
            print('Removing file: ${}'.format(output_file))
            os.remove(output_file)
        else:
            print('Skipping Secchi Depth, target already exists: {}'.format(FILENAME.format(product_name)))
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

    satellite = get_satellite_name_from_product_name(product_name)

    ################## Setup band configuration for Sentinel-2 or Sentinel-3 ##################
    if satellite in ['S2A', 'S2B']:
        # ToDo: values for Sentinel-2 are yet to be configured
        print('')
        print('QAA Secchi for Sentinel-2 is not quite implemented yet!!')
        print('')
        # Coefficients for the calculation of the ratio of backscattering to the sum of absorption and backscattering Lee et al. 2002
        g0 = 0
        g1 = 0
        # Pure Water absorption coefficient at 443, 490, 560, 665, 705 nm from Pope and Fry (1997)
        aws = [0, 0, 0, 0, 0]
        # Pure Water backscattering at 443, 490, 560, 665, 705 nm from Morel (1974)
        bws = [0, 0, 0, 0, 0]
        # Center Wavelenghts
        wvl = [443, 490, 560, 665, 705]
        # Coefficients for the calculation of the Diffuse attenuation coefficient based on Lee et al. (2016)
        m0 = 0
        m1 = 0
        m2 = 0
        m3 = 0
        y1 = 0
        spectral_band_names = ['Rw443', 'Rw490', 'Rw560', 'Rw665', 'Rw705']
        tsm_band = 'tsm_binding740'
        a_gelb_band = ''

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
        m0 = 0.005
        m1 = 4.259
        m2 = 0.52
        m3 = 10.8
        y1 = 0.265
        spectral_band_names = ['Rw412', 'Rw443', 'Rw490', 'Rw510', 'Rw560', 'Rw620', 'Rw665', 'Rw681']
        tsm_band = 'tsm_binding754'
        a_gelb_band = 'a_gelb443'

    else:
        raise RuntimeError('Secchi adapter not implemented for satellite ' + satellite)

    bands = [product.getBand(bname) for bname in spectral_band_names]
    SZA = product.getBand('sza')
    secchiProduct = Product('Z0', 'Z0', width, height)

    secchi_names = ['Z' + band_name[2:] for band_name in spectral_band_names] + \
                   [a_gelb_band] + \
                   ['a_dg' + band_name[2:] for band_name in spectral_band_names] + \
                   ['a_ph' + band_name[2:] for band_name in spectral_band_names]

    valid_pixel_expression = product.getBand(tsm_band).getValidPixelExpression()
    for band_name in product_band_names:
        if band_name in valid_pixel_expression:
            ProductUtils.copyBand(band_name, product, secchiProduct, True)

    secchi_bands = []
    for secchi_name in secchi_names:
        temp_band = secchiProduct.addBand(secchi_name, ProductData.TYPE_FLOAT32)
        if 'Z' in secchi_name:
            temp_band.setUnit('m')
        elif 'a' in secchi_name:
            temp_band.setUnit('m^-1')
        temp_band.setNoDataValueUsed(True)
        temp_band.setNoDataValue(np.NaN)
        wavelength = re.findall(r'\d+', secchi_name)[0]
        temp_band.setSpectralWavelength(float(wavelength))
        temp_band.setValidPixelExpression(valid_pixel_expression)
        secchi_bands.append(temp_band)

    writer = ProductIO.getProductWriter('NetCDF4-BEAM')

    ProductUtils.copyGeoCoding(product, secchiProduct)

    secchiProduct.setProductWriter(writer)
    secchiProduct.writeHeader(output_file)

    rs = [np.zeros(width, dtype=np.float32) for _ in range(len(spectral_band_names))]

    sza = np.zeros(width, dtype=np.float32)

    # Write valid pixel bands
    for band_name in product_band_names:
        if band_name in valid_pixel_expression:
            temp_arr = np.zeros(width * height)
            product.getBand(band_name).readPixels(0, 0, width, height, temp_arr)
            secchiProduct.getBand(band_name).writePixels(0, 0, width, height, temp_arr)

    print("Calculating Secchi depth.")

    for n_row in range(height):
        # Reading the different bands per pixel into arrays
        rs = [b.readPixels(0, n_row, width, 1, r) for (b, r) in zip(bands, rs)]

        # Reading the solar zenith angle per pixel
        sza = SZA.readPixels(0, n_row, width, 1, sza)

        ################## Derivation of total absorption and backscattering coefficients ###########
        rrs = [r / (0.52 + (1.7 * r)) for r in rs]
        us = [(-g0 + (np.sqrt((g0 ** 2) + (4 * g1) * rr))) / (2 * g1) for rr in rrs]
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
        output = Zs + a_g_s + a_ph + rrs

        # Mark infinite values as NAN
        for bds in output:
            bds[bds == np.inf] = np.nan
            bds[bds == -np.inf] = np.nan

        # Write the secchi depth per band
        for secchi, bds in zip(secchi_bands, output):
            secchi.writePixels(0, n_row, width, 1, bds)

    secchiProduct.closeIO()
    print("Writing Secchi depth to file: {}".format(output_file))
