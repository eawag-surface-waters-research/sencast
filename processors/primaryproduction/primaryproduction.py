#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Primary Production processor using the Lee et al. quantum yield model
with ERA5 hourly PAR.
"""

import os
import numpy as np
import xarray as xr

import cdsapi
from netCDF4 import Dataset
from utils.auxil import log
from utils.product_fun import copy_nc, get_band_names_from_nc, get_name_width_height_from_nc, \
    get_valid_pe_from_nc, write_pixels_to_nc, create_band, read_pixels_from_nc, \
    get_sensing_date_from_product_name, copy_band
from processors.primaryproduction.lee_pp import lee_pp

# key of the params section for this adapter
PARAMS_SECTION = "PRIMARYPRODUCTION"
# The name of the folder to which the output product will be saved
OUT_DIR = 'L2PP'
# A pattern for the name of the file to which the output product will be saved (completed with product name)
OUT_FILENAME = 'L2PP_{}'

# ERA5 ssrd (J/m² per hour) to surface PAR (µmol/m²/s)
# ssrd/3600 → W/m², ×0.45 PAR fraction, ×4.57 W/m²→µmol/m²/s, ×0.95 surface transmission
SSRD_TO_PAR = (1.0 / 3600) * 0.45 * 4.57 * 0.95


def read_era5_par(era5_dir, date, lat, lon):
    """Read 24h of ERA5 ssrd and convert to hourly surface PAR.
    Downloads from CDS if not cached.
    """
    year, month, day = date[:4], date[4:6], date[6:8]
    target = os.path.join(era5_dir, year, month, day, f'era5_ssrd_{date}.nc')
    if not os.path.exists(target):
        os.makedirs(os.path.dirname(target), exist_ok=True)
        client = cdsapi.Client()
        client.retrieve(
            'reanalysis-era5-single-levels',
            {
                'product_type': 'reanalysis',
                'variable': 'surface_solar_radiation_downwards',
                'year': year,
                'month': month,
                'day': day,
                'time': [f'{h:02d}:00' for h in range(24)],
                'format': 'netcdf',
            },
            target)
    ds = xr.open_dataset(target)
    ssrd = ds.ssrd.sel(latitude=lat, longitude=lon, method='nearest').values.flatten()
    ds.close()
    return ssrd * SSRD_TO_PAR


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
    kd_product_path = l2product_files[kd_processor]
    product_name = os.path.basename(product_path)
    product_dir = os.path.join(os.path.dirname(os.path.dirname(product_path)), OUT_DIR)
    output_file = os.path.join(product_dir, OUT_FILENAME.format(product_name))
    if os.path.isfile(output_file):
        if "overwrite" in params["General"].keys() and params['General']['overwrite'] == "true":
            log(env["General"]["log"], "Removing file: ${}".format(output_file), indent=1)
            os.remove(output_file)
        else:
            log(env["General"]["log"], "Skipping Primary Production, target already exists: {}".format(OUT_FILENAME.format(product_name)), indent=1)
            return output_file
    os.makedirs(product_dir, exist_ok=True)

    with Dataset(product_path) as chl_src, Dataset(kd_product_path) as kd_src, Dataset(output_file, mode='w') as dst:
        log(env["General"]["log"], "Reading Chlorophyll values from {}".format(product_path), indent=1)
        chl_band_names = get_band_names_from_nc(chl_src)
        if chl_bandname not in chl_band_names:
            raise RuntimeError("{} not in product bands. Edit the parameter file.".format(chl_bandname))
        _, width, height = get_name_width_height_from_nc(chl_src, product_path)
        chl_data = np.zeros(width * height, np.float32)
        read_pixels_from_nc(chl_src, chl_bandname, 0, 0, width, height, chl_data)
        chl_valid_pixel_expression = get_valid_pe_from_nc(chl_src, chl_bandname)

        log(env["General"]["log"], "Reading kd values from {}".format(kd_product_path), indent=1)
        kd_band_names = get_band_names_from_nc(kd_src)
        if kd_bandname not in kd_band_names:
            raise RuntimeError("{} not in product bands. Edit the parameter file.".format(kd_bandname))
        _, kd_width, kd_height = get_name_width_height_from_nc(kd_src, product_path)
        kd_data = np.zeros(kd_width * kd_height, np.float32)
        read_pixels_from_nc(kd_src, kd_bandname, 0, 0, kd_width, kd_height, kd_data)
        kd_valid_pixel_expression = get_valid_pe_from_nc(kd_src, kd_bandname)

        if chl_data.shape != kd_data.shape:
            raise RuntimeError("CHl and KD on different grids. Grid interpolation not yet implemented")

        log(env["General"]["log"], "Add valid pixel expression bands.", indent=1)
        copy_nc(chl_src, dst, [])
        for band_name in list(dict.fromkeys(chl_band_names + kd_band_names)):
            if band_name in str(chl_valid_pixel_expression) or band_name == chl_bandname:
                copy_band(chl_src, dst, band_name)
            elif band_name in str(kd_valid_pixel_expression) or band_name == kd_bandname:
                copy_band(kd_src, dst, band_name)
        valid_pixel_expression = None
        if chl_valid_pixel_expression is not None and kd_valid_pixel_expression is not None and chl_valid_pixel_expression != kd_valid_pixel_expression:
            valid_pixel_expression = '({}) and ({})'.format(chl_valid_pixel_expression, kd_valid_pixel_expression)
        elif chl_valid_pixel_expression is not None:
            valid_pixel_expression = chl_valid_pixel_expression
        elif kd_valid_pixel_expression is not None:
            valid_pixel_expression = kd_valid_pixel_expression

        date = get_sensing_date_from_product_name(product_name)

        log(env["General"]["log"], "Reading ERA5 hourly PAR.", indent=1)
        lat_mean = float(np.nanmean(kd_src.variables['lat'][:]))
        lon_mean = float(np.nanmean(kd_src.variables['lon'][:]))
        par_hourly = read_era5_par(env['CDS']['anc_path'], date, lat_mean, lon_mean)

        log(env["General"]["log"], "Calculating Lee Primary Production.", indent=1)
        pp_data, kdpar_data = lee_pp(chl_data, kd_data, par_hourly)
        pp_data = pp_data.astype(np.float32)
        kdpar_data = kdpar_data.astype(np.float32)

        log(env["General"]["log"], "Writing new bands to file.", indent=1)
        create_band(dst, 'pp_integral', 'mg C m^-2 day^-1', valid_pixel_expression)
        write_pixels_to_nc(dst, 'pp_integral', 0, 0, width, height, pp_data)
        create_band(dst, 'kdpar', 'm^-1', valid_pixel_expression)
        write_pixels_to_nc(dst, 'kdpar', 0, 0, width, height, kdpar_data)

    return output_file