#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import numpy as np
from snappy import ProductIO, PixelPos, jpy, ProductData, Product, ProductUtils

# key of the params section for this adapter
PARAMS_SECTION = "PRIMARYPRODUCTION"

# the file name pattern for output file
FILENAME = "L2PP_{}"


def apply(env, params, l2product_files):
    if not env.has_section(PARAMS_SECTION):
        raise RuntimeWarning("Primary Production was not configured in this environment.")
    if not params.has_section(PARAMS_SECTION):
        raise RuntimeWarning("Primary Production was not configured in parameters.")
    print("Applying Primary Production...")

    if "chl_processor" not in params[PARAMS_SECTION] or "chl_bandname" not in params[PARAMS_SECTION]:
        raise RuntimeWarning("chl_processor and chl_bandname must be defined in the parameter file.")

    chl_processor = params[PARAMS_SECTION]["chl_processor"]
    chl_bandname = params[PARAMS_SECTION]["chl_bandname"]

    # Check for precursor datasets
    if chl_processor not in l2product_files or not os.path.exists(l2product_files[chl_processor]):
        raise RuntimeWarning("Primary Production requires chlorophyll output file.")

    # Create folder for file
    product_path = l2product_files[chl_processor]
    product_name = os.path.basename(product_path)
    output_file = os.path.join(os.path.dirname(product_path), FILENAME.format(product_name))
    if os.path.isfile(output_file):
        print("Skipping Primary Production, target already exists: {}".format(FILENAME.format(product_name)))
        return output_file

    # Read in chlorophyll band from C2RCC
    product = ProductIO.readProduct(l2product_files[chl_processor])
    all_bns = product.getBandNames()
    if chl_bandname not in all_bns:
        raise RuntimeError("{} not in product bands. Edit the parameter file.".format(chl_bandname))
    chl = product.getBand(chl_bandname)
    w = chl.getRasterWidth()
    h = chl.getRasterHeight()
    chl_data = np.zeros(w * h, np.float32)
    chl.readPixels(0, 0, w, h, chl_data)

    # Calculate primary production
    pp = primaryproduction(chl_data)

    # Add new band
    out_product = Product('PP', 'PP', w, h)
    target_band = out_product.addBand('pp', ProductData.TYPE_FLOAT32)
    writer = ProductIO.getProductWriter('NetCDF4-CF')
    ProductUtils.copyGeoCoding(product, out_product)
    out_product.setProductWriter(writer)
    out_product.writeHeader(output_file)
    target_band.writePixels(0, 0, w, h, pp)
    out_product.closeIO()

    print("Successfully processed Primary Production")


def LatLon_from_XY(product, x, y):
    geoPosType = jpy.get_type('org.esa.snap.core.datamodel.GeoPos')
    geocoding = product.getSceneGeoCoding()
    geo_pos = geocoding.getGeoPos(PixelPos(x, y), geoPosType())
    if str(geo_pos.lat) == 'nan':
        raise ValueError('x, y pixel coordinates not in this product')
    else:
        return geo_pos.lat, geo_pos.lon


def primaryproduction(chl):
    print("Primary production")
    return chl * 1000


def pp(Qstar_PAR, F_PAR):
    # Smith et al. 1989, Arst et al 2008
    # PP(z) = psi * Qstar_PAR(z) * F_PAR(z)
    # PP(z) - phytoplankton primary production at depth z
    # psi - factor 12000 for converting moles to milligrams of C
    # Qstar_PAR(z) - photosynthetically absorbed radiation at depth z (mol photons m-3 h-1)
    # F_PAR(z) - quantum yield of C fixation (mol C(mol photons)-1)
    psi = 12000
    return psi * Qstar_PAR * F_PAR
