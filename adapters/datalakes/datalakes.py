#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
The Datalakes adapter is designed to output specified bands to JSON format in order to facilitate web visualisation
in the Datalakes data portal https://www.datalakes-eawag.ch/.
"""

import os
import boto3
import numpy as np
import pandas as pd
import requests
from utils.auxil import log
from json import dump
from netCDF4 import Dataset
from utils.product_fun import get_satellite_name_from_product_name, get_sensing_datetime_from_product_name, \
    get_pixels_from_nc, write_all_pixels_to_nc, create_band, append_to_valid_pixel_expression


# the url to post new data notification to
NOTIFY_URL = "https://api.datalakes-eawag.ch/externaldata/sync/remotesensing"
# key of the params section for this adapter
PARAMS_SECTION = "DATALAKES"
# name of output directory
OUT_DIR = "DATALAKES"
# the file name pattern for json output files
JSON_FILENAME = "{}_{}_{}_{}.json"
# the file name pattern for json output files
NC_FILENAME = "{}_{}_{}.nc"


def apply(env, params, l2product_files, date):
    """Apply datalakes adapter.
    1. Converts specified band in NetCDF to JSON format
    2. Save files to S3 storage
    3. Hits Datalakes endpoint to inform server of new data

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

    if PARAMS_SECTION not in params:
        raise ValueError("Datalakes selection must be defined in the parameters file.")
    for key in params[PARAMS_SECTION].keys():
        processor = key[0:key.find("_")].upper()
        if processor in l2product_files.keys():
            log(env["General"]["log"], "Processing {} to Datalakes product".format(processor), indent=1)
            l2product_file = l2product_files[processor]
            satellite = get_satellite_name_from_product_name(os.path.basename(l2product_file))
            date = get_sensing_datetime_from_product_name(os.path.basename(l2product_file))
            out_path = os.path.join(os.path.dirname(os.path.dirname(l2product_file)), OUT_DIR, "datalakes", params['General']['wkt_name'], satellite + "_" + date)
            output_file_main = os.path.join(out_path, NC_FILENAME.format(processor, satellite, date))
            os.makedirs(out_path, exist_ok=True)
            bands_list = list(filter(None, params[PARAMS_SECTION][key].split(",")))
            bands, bands_min, bands_max = parse_bands(bands_list)

            if os.path.exists(output_file_main):
                if ("synchronise" in params["General"].keys() and params['General']['synchronise'] == "false") or \
                        ("synchronise" in params["DATALAKES"].keys() and params["DATALAKES"]["synchronise"] == "false"):
                    log(env["General"]["log"], "Removing file: ${}".format(output_file_main), indent=2)
                    os.remove(output_file_main)

            if os.path.exists(output_file_main):
                log(env["General"]["log"], "Skipping processor {}. Target already exists".format(processor), indent=2)
            else:
                log(env["General"]["log"], "Copying {} to Datalakes folder.".format(os.path.basename(l2product_file)), indent=2)
                with open(l2product_file, "rb") as f:
                    nc_bytes = f.read()
                with open(output_file_main, "wb") as f:
                    f.write(nc_bytes)

                try:
                    log(env["General"]["log"], "Merging {} with lake_mask_sui_S3.nc".format(os.path.basename(output_file_main)), indent=2)
                    lake_mask = get_pixels_from_nc(os.path.join(os.path.abspath(os.path.dirname(__file__)), "lake_mask_sui_S3.nc"), "Swiss_S3_water")
                    with Dataset(output_file_main, mode='r+') as dst:
                        create_band(dst, "lake_mask", "", "lake_mask>0")
                        write_all_pixels_to_nc(dst, "lake_mask", lake_mask)
                        append_to_valid_pixel_expression(dst, "lake_mask>0")
                except:
                    log(env["General"]["log"], "Failed to merge with lake_mask_sui_S3.nc", indent=2)

                for idx, val in enumerate(bands):
                    log(env["General"]["log"], "Converting {} band {} to JSON".format(processor, val), indent=3)
                    output_file = os.path.join(out_path, JSON_FILENAME.format(processor, val, satellite, date))
                    nc_to_json(output_file_main, output_file, val, 6, bands_min[idx], bands_max[idx], satellite, date, env)

            if "bucket" not in params[PARAMS_SECTION]:
                raise ValueError("S3 Bucket must be defined in parameters file")

            if not env.has_section(PARAMS_SECTION):
                raise ValueError("{} section required in envrionment file.".format(PARAMS_SECTION))

            if "aws_access_key_id" not in env[PARAMS_SECTION] or "aws_secret_access_key" not in env[PARAMS_SECTION]:
                raise ValueError("aws_access_key_id and aws_secret_access_key must be defined in environment file")

    if l2product_file:
        log(env["General"]["log"], "Uploading files to {}".format(params[PARAMS_SECTION]["bucket"]), indent=1)
        upload_directory(os.path.join(os.path.dirname(os.path.dirname(l2product_file)), OUT_DIR), params[PARAMS_SECTION]["bucket"], env[PARAMS_SECTION]["aws_access_key_id"], env[PARAMS_SECTION]["aws_secret_access_key"], env["General"]["log"])

        log(env["General"]["log"], "Notifying Datalakes API of updated data.", indent=1)
        requests.get(NOTIFY_URL)


def convert_valid_pixel_expression(vpe, variables):
    vpe = vpe.split("and")
    vpe = ['({0})'.format(v) for v in vpe]
    vpe = "&".join(vpe)
    vpe = vpe.replace("max", "np.maximum")
    vpe = vpe.replace("min", "np.minimum")
    for variable in variables:
        if variable in vpe:
            vpe = vpe.replace(variable, 'np.array(df["{}"])'.format(variable))
    return vpe


def nc_to_json(input_file, output_file, variable_name, decimals, band_min, band_max, satellite, date, env):
    nc = Dataset(input_file, "r", format="NETCDF4")
    _lons, _lats, _values = np.array(nc.variables['lon'][:]), np.array(nc.variables['lat'][:]), np.array(nc.variables[variable_name][:])
    valid_pixel_expression = None
    try:
        valid_pixel_expression = nc.variables[variable_name].valid_pixel_expression
    except:
        log(env["General"]["log"], "No valid pixel expression for {}".format(variable_name), indent=2)
    variables = nc.variables.keys()
    variables_dict = {}
    for variable in variables:
        temp = np.array(nc.variables[variable][:]).flatten()
        if len(temp) == len(_values.flatten()):
            variables_dict[variable] = np.array(nc.variables[variable][:]).flatten()
    nc.close()

    df = pd.DataFrame.from_dict(variables_dict)
    df["lons"] = np.repeat(_lons[np.newaxis, :], len(_lats), axis=0).flatten()
    df["lats"] = np.repeat(_lats[:, np.newaxis], len(_lons), axis=1).flatten()
    df.dropna(subset=[variable_name], inplace=True)
    df = df[df[variable_name] >= band_min]
    df = df[df[variable_name] <= band_max]
    df = df.astype(float).round(decimals)
    lonres, latres = float(round(abs(_lons[1] - _lons[0]), 12)), float(round(abs(_lats[1] - _lats[0]), 12))
    if valid_pixel_expression is not None:
        converted_vpe = convert_valid_pixel_expression(valid_pixel_expression, variables)
        df["valid_pixels"] = (eval(converted_vpe).astype(int) * -1) + 1
    else:
        df["valid_pixels"] = 0
    with open(output_file, "w") as f:
        f.truncate()
        dump({'lonres': lonres, 'latres': latres, 'lon': list(df["lons"]), 'lat': list(df["lats"]), 'v': list(df[variable_name]), 'vp': list(df["valid_pixels"]), 'vpe': valid_pixel_expression, 'satellite': satellite, 'datetime': date}, f, separators=(',', ':'))


def parse_bands(bands):
    bands_min = []
    bands_max = []
    for i in range(len(bands)):
        if "[" in bands[i]:
            sp = bands[i].replace("[", ",").replace(":", ",").replace("]", ",").split(",")
            bands[i] = sp[0]
            bands_min.append(float(sp[1]))
            bands_max.append(float(sp[2]))
        else:
            bands_min.append(None)
            bands_max.append(None)
    return bands, bands_min, bands_max


def upload_directory(path, bucket, aws_access_key_id, aws_secret_access_key, logger, failed=False):
    """Upload a file to an S3 bucket"""

    client = boto3.client(
        's3',
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key
    )
    for root, dirs, files in os.walk(path):
        for file in files:
            try:
                log(logger, "Uploading {}".format(file), indent=2)
                client.upload_file(os.path.join(root, file), bucket, os.path.relpath(os.path.join(root, file), path))
            except:
                failed = True
                log(logger, "Failed to upload: {}".format(file), indent=2)
    if failed:
        raise RuntimeError("Failed to upload all files to {}".format(bucket))
