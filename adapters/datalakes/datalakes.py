#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
The Datalakes adapter is designed to output specified bands in order to facilitate web visualisation
in the Datalakes data portal https://www.datalakes-eawag.ch/.
"""
import os
import boto3
import numpy as np
import pandas as pd
from osgeo import osr
from osgeo import gdal
import requests
from utils.auxil import log
from json import dump
from netCDF4 import Dataset
from pyproj import CRS
from utils.product_fun import get_satellite_name_from_product_name, get_sensing_datetime_from_product_name, \
    get_pixels_from_nc, write_all_pixels_to_nc, create_band, append_to_valid_pixel_expression
osr.UseExceptions()

# the url to post new data notification to
NOTIFY_URL = "https://api.datalakes-eawag.ch/externaldata/sync/remotesensing"
# key of the params section for this adapter
PARAMS_SECTION = "DATALAKES"
# name of output directory
OUT_DIR = "DATALAKES"
# the file name pattern for json output files
JSON_FILENAME = "{}_{}_{}_{}.json"
# the file name pattern for geotiff output files
GEOTIFF_FILENAME = "{}_{}_{}_{}_{}.tif"
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
    if not bool(l2product_files):
        raise ValueError("No l2 products available to process")
    errors = []
    for key in params[PARAMS_SECTION].keys():
        processor = key[0:key.find("_")].upper()
        if processor in l2product_files.keys():
            log(env["General"]["log"], "Processing {} to Datalakes product".format(processor), indent=1)
            if not isinstance(l2product_files[processor], list):
                l2product_files[processor] = [l2product_files[processor]]
            for l2product_file in l2product_files[processor]:
                satellite = get_satellite_name_from_product_name(os.path.basename(l2product_file))
                date = get_sensing_datetime_from_product_name(os.path.basename(l2product_file))
                out_path = os.path.join(os.path.dirname(os.path.dirname(l2product_file)), OUT_DIR, "datalakes", params['General']['wkt_name'], satellite + "_" + date)
                input_file = os.path.join(out_path, NC_FILENAME.format(processor, satellite, date))
                os.makedirs(out_path, exist_ok=True)
                bands_list = list(filter(None, params[PARAMS_SECTION][key].split(",")))
                bands, bands_min, bands_max = parse_bands(bands_list)

                if os.path.exists(input_file):
                    if ("synchronise" in params["General"].keys() and params['General']['synchronise'] == "false") or \
                            ("synchronise" in params["DATALAKES"].keys() and params["DATALAKES"]["synchronise"] == "false"):
                        log(env["General"]["log"], "Removing file: ${}".format(input_file), indent=2)
                        os.remove(input_file)

                if os.path.exists(input_file):
                    log(env["General"]["log"], "Skipping processor {}. Target already exists".format(processor), indent=2)
                else:
                    log(env["General"]["log"], "Copying {} to Datalakes folder.".format(os.path.basename(l2product_file)), indent=2)
                    with open(l2product_file, "rb") as f:
                        nc_bytes = f.read()
                    with open(input_file, "wb") as f:
                        f.write(nc_bytes)

                    if "S3" in satellite:
                        try:
                            log(env["General"]["log"], "Merging {} with lake_mask_sui_S3.nc".format(os.path.basename(input_file)), indent=2)
                            lake_mask = get_pixels_from_nc(os.path.join(os.path.abspath(os.path.dirname(__file__)), "lake_mask_sui_S3.nc"), "Swiss_S3_water")
                            with Dataset(input_file, mode='r+') as dst:
                                create_band(dst, "lake_mask", "", "lake_mask>0")
                                write_all_pixels_to_nc(dst, "lake_mask", lake_mask)
                                append_to_valid_pixel_expression(dst, "lake_mask>0")
                        except:
                            log(env["General"]["log"], "Failed to merge with lake_mask_sui_S3.nc", indent=2)

                    for idx, val in enumerate(bands):
                        log(env["General"]["log"], "Converting {} band {} to JSON".format(processor, val), indent=3)
                        try:
                            if "S3" in satellite:
                                json_outfile = os.path.join(out_path, JSON_FILENAME.format(processor, val, satellite, date))
                                geotiff_outfile = os.path.join(out_path, GEOTIFF_FILENAME.format(processor, val, satellite, date, "sui"))
                                convert_nc("json", input_file, json_outfile, val, 6, bands_min[idx], bands_max[idx], satellite, date, env)
                                convert_nc("geotiff", input_file, geotiff_outfile, val, 6, bands_min[idx], bands_max[idx], satellite, date, env)
                            if "S2" in satellite:
                                tile = l2product_file.split("_")[-2]
                                geotiff_outfile = os.path.join(out_path, GEOTIFF_FILENAME.format(processor, val, satellite, date, tile))
                                convert_nc("geotiff", input_file, geotiff_outfile, val, 6, bands_min[idx], bands_max[idx], satellite, date, env)
                        except Exception as e:
                            print(e)
                            errors.append("Failed to convert {} band {} to JSON".format(processor, val))
                            log(env["General"]["log"], "Failed to convert {} band {} to JSON".format(processor, val), indent=3)

    if "bucket" not in params[PARAMS_SECTION]:
        raise ValueError("S3 Bucket must be defined in parameters file")

    if not env.has_section(PARAMS_SECTION):
        raise ValueError("{} section required in environment file.".format(PARAMS_SECTION))

    if "aws_access_key_id" not in env[PARAMS_SECTION] or "aws_secret_access_key" not in env[PARAMS_SECTION]:
        raise ValueError("aws_access_key_id and aws_secret_access_key must be defined in environment file")

    if l2product_file:
        log(env["General"]["log"], "Uploading files to {}".format(params[PARAMS_SECTION]["bucket"]), indent=1)
        if "S2" in satellite:
            upload_directory(os.path.join(os.path.dirname(os.path.dirname(l2product_file)), OUT_DIR),
                             params[PARAMS_SECTION]["bucket"], env[PARAMS_SECTION]["aws_access_key_id"],
                             env[PARAMS_SECTION]["aws_secret_access_key"], env["General"]["log"], extension=".tif")
        else:
            upload_directory(os.path.join(os.path.dirname(os.path.dirname(l2product_file)), OUT_DIR),
                             params[PARAMS_SECTION]["bucket"], env[PARAMS_SECTION]["aws_access_key_id"],
                             env[PARAMS_SECTION]["aws_secret_access_key"], env["General"]["log"])

        log(env["General"]["log"], "Notifying Datalakes API of updated data.", indent=1)
        requests.get(NOTIFY_URL)

    if len(errors) > 0:
        raise ValueError(". ".join(errors))


def convert_nc(output_type, input_file, output_file, band, decimals, band_min, band_max, satellite, date, env, projection=4326):
    log(env["General"]["log"], "Reading data from {}".format(input_file), indent=4)
    valid_pixel_expression = ""
    with Dataset(input_file, "r", format="NETCDF4") as nc:
        variables = nc.variables.keys()
        values = np.array(nc.variables[band][:])
        values_flat = values.flatten()
        y = np.array(nc.variables[nc.variables[band].dimensions[0]][:])
        x = np.array(nc.variables[nc.variables[band].dimensions[1]][:])
        if "proj4_string" in nc.ncattrs():
            c = CRS.from_string(nc.getncattr("proj4_string"))
            projection = c.to_epsg()
            log(env["General"]["log"], 'Adjusted projection to {} based on the proj4_string "{}"'.format(projection, nc.getncattr("proj4_string")), indent=4)
        try:
            valid_pixel_expression = nc.variables[band].valid_pixel_expression
            vpe_dict = {}
            for variable in variables:
                if variable in valid_pixel_expression:
                    extract = np.array(nc.variables[variable][:]).flatten()
                    if len(extract) == len(values_flat):
                        vpe_dict[variable] = extract
            df = pd.DataFrame.from_dict(vpe_dict)
            converted_vpe = convert_valid_pixel_expression(valid_pixel_expression, variables)
            valid_pixels = (eval(converted_vpe).astype(int) * -1) + 1
        except:
            log(env["General"]["log"], "No valid pixel expression for {}".format(band), indent=4)
            valid_pixels = np.zeros_like(values_flat)

    valid_pixels[values_flat < band_min] = 1
    valid_pixels[values_flat > band_max] = 1
    valid_pixels[np.isnan(values_flat)] = 1

    if output_type == "json":
        log(env["General"]["log"], "Outputting JSON file {}".format(output_file), indent=4)
        out_dict = {band: values_flat}
        df = pd.DataFrame.from_dict(out_dict)
        if len(y.shape) > 1:
            df["lon"] = x.flatten()
            df["y"] = y.flatten()
            xmin, ymin, xmax, ymax = [np.nanmin(x), np.nanmin(y), np.nanmax(x), np.nanmax(y)]
            lonres, latres = (xmax - xmin) / float(values.shape[0]), (ymax - ymin) / float(values.shape[1])
        else:
            df["lon"] = np.repeat(x[np.newaxis, :], len(y), axis=0).flatten()
            df["lat"] = np.repeat(y[:, np.newaxis], len(x), axis=1).flatten()
            lonres, latres = float(round(abs(x[1] - x[0]), 12)), float(round(abs(y[1] - y[0]), 12))
        df["valid_pixels"] = valid_pixels
        df.dropna(subset=[band], inplace=True)
        df = df.astype(float).round(decimals)
        with open(output_file, "w") as f:
            f.truncate()
            dump({'lonres': lonres, 'latres': latres, 'lon': list(df["lon"]), 'lat': list(df["lat"]),
                  'v': list(df[band]), 'vp': list(df["valid_pixels"]), 'vpe': valid_pixel_expression,
                  'satellite': satellite, 'datetime': date}, f, separators=(',', ':'))

    elif output_type == "geotiff":
        log(env["General"]["log"], "Outputting GEOTIFF file {}".format(output_file), indent=4)
        temp_file = os.path.join(os.path.dirname(output_file), "temp_" + os.path.basename(output_file))
        if len(y.shape) > 1:
            image_size = values.shape
            nx = image_size[0]
            ny = image_size[1]
        else:
            ny = len(x)
            nx = len(y)
        xmin, ymin, xmax, ymax = [np.nanmin(x), np.nanmin(y), np.nanmax(x), np.nanmax(y)]
        xres = (xmax - xmin) / float(ny)
        yres = (ymax - ymin) / float(nx)
        geotransform = (xmin, xres, 0, ymax, 0, -yres)

        dst_ds = gdal.GetDriverByName('GTiff').Create(temp_file, ny, nx, 2, gdal.GDT_Float32)
        dst_ds.SetGeoTransform(geotransform)
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(projection)
        dst_ds.SetProjection(srs.ExportToWkt())
        dst_ds.GetRasterBand(1).WriteArray(values)
        dst_ds.GetRasterBand(2).WriteArray(valid_pixels.reshape(values.shape))
        dst_ds.FlushCache()
        dst_ds = None

        if projection != 4326:
            dsReproj = gdal.Warp(temp_file, temp_file, dstSRS="EPSG:4326", dstNodata=np.nan)
            dsReproj = None

        translate_options = gdal.TranslateOptions(gdal.ParseCommandLine(
            '-co TILED=YES -co COPY_SRC_OVERVIEWS=YES -co COMPRESS=DEFLATE'))
        ds = gdal.Open(temp_file, gdal.OF_READONLY)
        gdal.SetConfigOption('COMPRESS_OVERVIEW', 'DEFLATE')
        ds.BuildOverviews('NEAREST', [2, 4, 8, 16, 32])
        ds = None
        del ds
        ds = gdal.Open(temp_file)
        gdal.Translate(output_file, ds, options=translate_options)
        ds = None

        if os.path.isfile(temp_file):
            os.unlink(temp_file)
        if os.path.isfile(temp_file + ".ovr"):
            os.unlink(temp_file + ".ovr")
        if os.path.isfile(output_file + ".aux.xml"):
            os.unlink(output_file + ".aux.xml")


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


def upload_directory(path, bucket, aws_access_key_id, aws_secret_access_key, logger, failed=False, extension=False):
    """Upload a file to an S3 bucket"""

    client = boto3.client(
        's3',
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key
    )
    for root, dirs, files in os.walk(path):
        for file in files:
            if extension == False or file[-len(extension):] == extension:
                try:
                    log(logger, "Uploading {}".format(file), indent=2)
                    client.upload_file(os.path.join(root, file), bucket, os.path.relpath(os.path.join(root, file), path))
                except:
                    failed = True
                    log(logger, "Failed to upload: {}".format(file), indent=2)
    if failed:
        raise RuntimeError("Failed to upload all files to {}".format(bucket))
