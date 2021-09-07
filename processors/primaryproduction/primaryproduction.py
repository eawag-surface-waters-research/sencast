#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""The Primary Production processor is an implementation of `T.Soomets et al. 2019 <https://core.ac.uk/reader/211997910>`_
in order to derive primary production from Satellite images.
"""

import os
import numpy as np
import re
from scipy.integrate import trapz
from snappy import ProductIO, PixelPos, jpy, ProductData, Product, ProductUtils

# key of the params section for this adapter
from utils.product_fun import get_sensing_date_from_product_name

PARAMS_SECTION = "PRIMARYPRODUCTION"

# the file name pattern for output file
FILENAME = "L2PP_{}"
FILEFOLDER = "L2PP"


# TODO: this should be a processor instead of an adapter!
def process(env, params, l1product_path, l2product_files, out_path):
    """Apply Primary Production adapter.
    1. Calculates primary production for Chl and KD

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
        raise RuntimeWarning("Primary Production was not configured in parameters.")
    print("Applying Primary Production...")

    if "chl_processor" not in params[PARAMS_SECTION] or "chl_bandname" not in params[PARAMS_SECTION]:
        raise RuntimeWarning("chl_processor and chl_bandname must be defined in the parameter file.")

    if "kd_processor" not in params[PARAMS_SECTION] or "kd_bandname" not in params[PARAMS_SECTION]:
        raise RuntimeWarning("kd_processor and kd_bandname must be defined in the parameter file.")

    chl_processor = params[PARAMS_SECTION]["chl_processor"]
    chl_bandname = params[PARAMS_SECTION]["chl_bandname"]
    kd_processor = params[PARAMS_SECTION]["kd_processor"]
    kd_bandname = params[PARAMS_SECTION]["kd_bandname"]

    # Check for precursor datasets
    if chl_processor not in l2product_files or not os.path.exists(l2product_files[chl_processor]):
        raise RuntimeWarning("Primary Production requires chlorophyll output file.")
    if kd_processor not in l2product_files or not os.path.exists(l2product_files[kd_processor]):
        raise RuntimeWarning("Primary Production requires KD output file.")

    # Create folder for file
    product_path = l2product_files[chl_processor]
    product_name = os.path.basename(product_path)
    product_dir = os.path.join(os.path.dirname(os.path.dirname(product_path)), FILEFOLDER)
    output_file = os.path.join(product_dir, FILENAME.format(product_name))
    l2product_files["PRIMARYPRODUCTION"] = output_file
    if os.path.isfile(output_file):
        if "synchronise" in params["General"].keys() and params['General']['synchronise'] == "false":
            print("Removing file: ${}".format(output_file))
            os.remove(output_file)
        else:
            print("Skipping Primary Production, target already exists: {}".format(FILENAME.format(product_name)))
            return output_file
    os.makedirs(product_dir, exist_ok=True)

    # Get depths
    zvals = np.array([0, 1, 2, 3.5, 5, 7.5, 10, 15, 20, 30])
    if "depths" in params[PARAMS_SECTION]:
        zvals = np.array(params[PARAMS_SECTION]["depths"])
    zvals_fine = np.linspace(np.min(zvals), np.max(zvals), 100)  # Fine spaced depths for integration

    # Read in chlorophyll band
    print("Reading Chlorophyll values from {}".format(product_path))
    product = ProductIO.readProduct(product_path)
    all_bns = product.getBandNames()
    if chl_bandname not in all_bns:
        raise RuntimeError("{} not in product bands. Edit the parameter file.".format(chl_bandname))
    chl = product.getBand(chl_bandname)
    w = chl.getRasterWidth()
    h = chl.getRasterHeight()
    chl_data = np.zeros(w * h, np.float32)
    chl.readPixels(0, 0, w, h, chl_data)
    chl_valid_pixel_expression = chl.getValidPixelExpression()

    # Convert from PH to CHL if required
    if "chl_parameter" in params[PARAMS_SECTION] and params[PARAMS_SECTION]["chl_parameter"] == "PH":
        chl_data = PhytoplanktonToChlorophyll(chl_data)

    # Read in KD band
    kd_product_path = l2product_files[kd_processor]
    print("Reading kd values from {}".format(kd_product_path))
    kd_product = ProductIO.readProduct(kd_product_path)
    all_bns_kd = kd_product.getBandNames()
    if kd_bandname not in all_bns_kd:
        raise RuntimeError("{} not in product bands. Edit the parameter file.".format(kd_bandname))
    kd = kd_product.getBand(kd_bandname)
    w_kd = kd.getRasterWidth()
    h_kd = kd.getRasterHeight()
    kd_data = np.zeros(w_kd * h_kd, np.float32)
    kd.readPixels(0, 0, w, h, kd_data)
    kd_valid_pixel_expression = kd.getValidPixelExpression()

    if chl_data.shape != kd_data.shape:
        raise RuntimeError("CHl and KD on different grids. Grid interpolation not yet implemented")

    # Create output file
    out_product = Product('PP', 'PP', w, h)
    writer = ProductIO.getProductWriter('NetCDF4-BEAM')
    ProductUtils.copyGeoCoding(product, out_product)
    out_product.setProductWriter(writer)

    # Add valid pixel expression bands
    all_bands = list(dict.fromkeys(list(all_bns) + list(all_bns_kd)))
    for band_name in all_bands:
        if band_name in str(chl_valid_pixel_expression):
            ProductUtils.copyBand(band_name, product, out_product, True)
        elif band_name in str(kd_valid_pixel_expression):
            ProductUtils.copyBand(band_name, kd_product, out_product, True)
    valid_pixel_expression = None
    if chl_valid_pixel_expression is not None and kd_valid_pixel_expression is not None and chl_valid_pixel_expression != kd_valid_pixel_expression:
        valid_pixel_expression = chl_valid_pixel_expression + " and " + kd_valid_pixel_expression
    elif chl_valid_pixel_expression is not None:
        valid_pixel_expression = chl_valid_pixel_expression
    elif kd_valid_pixel_expression is not None:
        valid_pixel_expression = kd_valid_pixel_expression

    # Get PAR
    date = get_sensing_date_from_product_name(product_name)
    month = datetomonth(date)
    qpar0 = qpar0_lookup(month, chl_data)

    # Get KdMorel
    KdMorel = 0.0864 + 0.884 * kd_data - 0.00137/kd_data

    # Calculate primary production
    pp_tni = pp_trapezoidal_numerical_integration(zvals_fine, qpar0, chl_data, KdMorel)

    # Add new bands
    pp_band = out_product.addBand('pp_integral', ProductData.TYPE_FLOAT32)
    pp_band.setUnit('mg C m^-2 h^-1')
    pp_band.setNoDataValueUsed(True)
    pp_band.setNoDataValue(np.NaN)
    pp_band.setValidPixelExpression(valid_pixel_expression)

    kd_band = out_product.addBand(kd_bandname, ProductData.TYPE_FLOAT32)
    kd_band.setUnit(kd.getUnit())
    kd_band.setNoDataValueUsed(True)
    kd_band.setNoDataValue(np.NaN)
    kd_band.setValidPixelExpression(kd_valid_pixel_expression)
    if len(re.findall('\d+', kd_bandname)) > 0:
        wavelength = re.findall('\d+', kd_bandname)[0]
        kd_band.setSpectralWavelength(float(wavelength))

    chl_band = out_product.addBand(chl_bandname, ProductData.TYPE_FLOAT32)
    chl_band.setUnit(chl.getUnit())
    chl_band.setNoDataValueUsed(True)
    chl_band.setNoDataValue(np.NaN)
    chl_band.setValidPixelExpression(chl_valid_pixel_expression)
    if len(re.findall('\d+', chl_bandname)) > 0:
        wavelength = re.findall('\d+', chl_bandname)[0]
        chl_band.setSpectralWavelength(float(wavelength))

    out_product.writeHeader(output_file)

    # Add data to valid pixel expression bands
    for band_name in all_bands:
        if band_name in str(chl_valid_pixel_expression):
            temp_arr = np.zeros(w * h)
            product.getBand(band_name).readPixels(0, 0, w, h, temp_arr)
            out_product.getBand(band_name).writePixels(0, 0, w, h, temp_arr)
        elif band_name in str(kd_valid_pixel_expression):
            temp_arr = np.zeros(w * h)
            kd_product.getBand(band_name).readPixels(0, 0, w, h, temp_arr)
            out_product.getBand(band_name).writePixels(0, 0, w, h, temp_arr)

    # Add other data
    pp_band.writePixels(0, 0, w, h, pp_tni)
    kd_band.writePixels(0, 0, w, h, kd_data)
    chl_band.writePixels(0, 0, w, h, chl_data)

    # Close output file
    out_product.closeIO()


def PhytoplanktonToChlorophyll(ph):
    # a_CHL = 0.054 CHL ** 0.96
    return (ph / 0.054) ** (1/0.96)


def LatLon_from_XY(product, x, y):
    geoPosType = jpy.get_type('org.esa.snap.core.datamodel.GeoPos')
    geocoding = product.getSceneGeoCoding()
    geo_pos = geocoding.getGeoPos(PixelPos(x, y), geoPosType())
    if str(geo_pos.lat) == 'nan':
        raise ValueError('x, y pixel coordinates not in this product')
    else:
        return geo_pos.lat, geo_pos.lon


def pp_trapezoidal_numerical_integration(zvals, qpar0, Cchl, KdMorel):
    if qpar0.shape == Cchl.shape and Cchl.shape == KdMorel.shape:
        pp_tni = np.zeros_like(Cchl)
        pp_tni[:] = np.nan
        for i in range(1, pp_tni.shape[0] - 1):
            if np.isfinite(Cchl[i]) and np.isfinite(qpar0[i]) and np.isfinite(KdMorel[i]) and Cchl[i] > 0:
                pp_tni[i] = trapz(PP(zvals, qpar0[i], Cchl[i], KdMorel[i]), zvals)
            else:
                continue
    else:
        raise RuntimeWarning("Matrices are not of consistent shape")
    return pp_tni


def datetomonth(date):
    return int(date[4:6])


def qpar0_lookup(month, matrix):
    lookup = {1: 2.5, 2: 2.5, 3: 4.0, 4: 4.0, 5: 6.5, 6: 6.5, 7: 6.5, 8: 6.5, 9: 4.0, 10: 4.0, 11: 2.5, 12: 2.5}
    qpar0 = np.zeros_like(matrix)
    try:
        qpar_constant = lookup[month]
    except KeyError:
        qpar_constant = 6  # Default value
    return qpar0 + qpar_constant


def absorption(Cchl):
    staehr = np.array([[405,415,425,435,445,455,465,475,485,495,505,515,525,535,545,555,565,575,585,595,605,615,625,635,645,655,665,675,685,695],
    [0.0354096166,0.0421678948,0.0473295299,0.0518112242,0.0528416913,0.0492712169,0.0468541233,0.0438758593,0.0396055613,0.0344464397,0.0279767283,0.0218711903,0.0174634833,0.0144184829,0.0120222884,0.0099181185,0.0082114226,0.007502871,0.0076737813,0.0079705761,0.0079189265,0.0082036874,0.0091286864,0.010055497,0.0109449428,0.0124636724,0.0179222053,0.0238667838,0.0187654866,0.0081258648],
    [0.23925,0.25175,0.2665,0.27725,0.28625,0.29725,0.297,0.30275,0.30675,0.28,0.23575,0.19325,0.1535,0.123,0.104,0.099,0.1115,0.1205,0.1495,0.17375,0.188,0.16625,0.1715,0.18575,0.202,0.21875,0.21175,0.18075,0.13575,0.1185]])
    return staehr[1,:]*(Cchl**(1-staehr[2,:]))  # Should the 1 be removed?


def q0par(z, qpar0, Cchl, Kpar):
    C1 = 1.32*Kpar**0.153
    C2 = 0.0023*Cchl + 0.016
    return C1*np.exp(C2*z) * 0.94*qpar0*np.exp(-Kpar*z)


def Qstarpar(z, q0par, Cchl):
    return q0par*np.average(absorption(Cchl))


def M (qpar0, Cchl, Kpar):
    if Cchl < 35:
        return 3.18-0.2125*Kpar**2.5+0.34*qpar0
    if Cchl < 80:
        return 3.58-0.31*qpar0-0.0072*Cchl
    if Cchl < 120:
        return 2.46 - 0.106*qpar0 - 0.00083*Cchl**1.5
    else:
        return 0.67


def Fpar(z, q0par, M):
    Fmax = 0.08
    return Fmax/(1+M*q0par)**1.5


def PP(z, qpar0, Cchl, Kpar):
    Mval = M(qpar0, Cchl, Kpar)
    rad = q0par(z, qpar0, Cchl, Kpar)
    return 12000*Fpar(z, rad, Mval)*Qstarpar(z, rad, Cchl)