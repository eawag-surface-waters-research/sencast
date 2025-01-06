#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
The Geotiff adapter is designed to output specified bands to Geotiff in order to facilitate web visualisation
"""
import os
import json
import boto3
import shutil
import numpy as np
import pandas as pd
from osgeo import osr
from osgeo import gdal
from utils.auxil import log
from json import dump
from netCDF4 import Dataset
from datetime import datetime
from pyproj import CRS
import shapely.vectorized
from shapely.geometry import shape, MultiPolygon, box
from utils.product_fun import (get_satellite_name_from_product_name, get_sensing_datetime_from_product_name,
    write_all_pixels_to_nc, create_band, append_to_valid_pixel_expression, get_tile_name_from_product_name,
                               get_commit_hash)
osr.UseExceptions()

# key of the params section for this adapter
PARAMS_SECTION = "GEOTIFF"
# name of output directory
OUT_DIR = "GEOTIFF"


def apply(env, params, l2product_files, date):
    """Apply Geotiff adapter.
    1. Converts specified band in NetCDF to Geotiff format
    2. Save files to S3 storage

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
        raise ValueError("GEOTIFF selection must be defined in the parameters file.")
    if not bool(l2product_files):
        raise ValueError("No l2 products available to process")
    errors = []
    commit_hash = get_commit_hash(os.path.abspath(__file__))
    for key in params[PARAMS_SECTION].keys():
        processor = key[0:key.find("_")].upper()
        if processor in l2product_files.keys():
            log(env["General"]["log"], "Processing {} to Geotiff".format(processor), indent=1)
            if not isinstance(l2product_files[processor], list):
                l2product_files[processor] = [l2product_files[processor]]
            for l2product_file in l2product_files[processor]:
                satellite = get_satellite_name_from_product_name(os.path.basename(l2product_file))
                tile = get_tile_name_from_product_name(os.path.basename(l2product_file))
                date = get_sensing_datetime_from_product_name(os.path.basename(l2product_file))
                base_folder = os.path.dirname(os.path.dirname(l2product_file))
                ini_file = [os.path.join(base_folder, f) for f in os.listdir(base_folder) if f.endswith(".ini")][0]
                out_path = os.path.join(os.path.dirname(os.path.dirname(l2product_file)), OUT_DIR, satellite + "_" + date)
                if tile:
                    input_file = os.path.join(out_path, "{}_{}_{}_{}.nc".format(processor, satellite, date, tile))
                else:
                    input_file = os.path.join(out_path, "{}_{}_{}.nc".format(processor, satellite, date))

                os.makedirs(out_path, exist_ok=True)
                bands_list = list(filter(None, params[PARAMS_SECTION][key].split(",")))
                bands, bands_min, bands_max = parse_bands(bands_list)

                if os.path.exists(input_file):
                    if ("overwrite" in params["General"].keys() and params['General']['overwrite'] == "true") or \
                            ("overwrite" in params[PARAMS_SECTION].keys() and params[PARAMS_SECTION]["overwrite"] == "true"):
                        for remove_file in os.listdir(out_path):
                            log(env["General"]["log"], "Removing file: ${}".format(remove_file), indent=2)
                            os.remove(os.path.join(out_path, remove_file))

                if os.path.exists(input_file):
                    log(env["General"]["log"], "Skipping processor {}. Target already exists".format(processor), indent=2)
                else:
                    log(env["General"]["log"], "Copying {} to Geotiff folder.".format(os.path.basename(l2product_file)), indent=2)
                    with open(l2product_file, "rb") as f:
                        nc_bytes = f.read()
                    with open(input_file, "wb") as f:
                        f.write(nc_bytes)
                    shutil.copy(ini_file, os.path.join(out_path, "reproduce.ini"))
                    if "lake_mask" in params[PARAMS_SECTION]:
                        mask_file = "{}m_watermask.geojson".format(params[PARAMS_SECTION]["lake_mask"])
                        mask_file_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), mask_file)
                        if not os.path.isfile(mask_file_path):
                            log(env["General"]["log"], "No lake_mask available for {}m".format(params[PARAMS_SECTION]["lake_mask"]), indent=2)
                        else:
                            try:
                                log(env["General"]["log"], "Merging {} with {}".format(os.path.basename(input_file), mask_file), indent=2)
                                lake_mask = get_mask_from_geojson(input_file, mask_file_path)
                                with Dataset(input_file, mode='r+') as dst:
                                    create_band(dst, "lake_mask", "", "lake_mask>0")
                                    write_all_pixels_to_nc(dst, "lake_mask", lake_mask)
                                    append_to_valid_pixel_expression(dst, "lake_mask>0")
                            except Exception as e:
                                print(e)
                                log(env["General"]["log"], "Failed to merge with {}".format(mask_file), indent=2)

                    for idx, val in enumerate(bands):
                        log(env["General"]["log"], "Processing {} band {}".format(processor, val), indent=3)
                        metadata = {
                            "Author": "Eawag",
                            "Parameter": val,
                            "Description": "Float32 GeoTiff where band1 is the value and band2 (when included) is a valid pixel mask",
                            "Origin File": os.path.basename(l2product_file),
                            "Satellite": satellite,
                            "Date": date,
                            "Produced": datetime.now().strftime("%Y%m%dT%H%M%S"),
                            "Commit Hash": commit_hash[:7],
                            "Reproduce": True
                        }
                        try:
                            if "S3" in satellite:
                                # This is legacy and should be removed when Datalakes is updated
                                json_outfile = os.path.join(out_path, "{}_{}_{}_{}.json".format(processor, val, satellite, date))
                                netcdf_json(input_file, json_outfile, val, 6, bands_min[idx], bands_max[idx], satellite, date, env)
                            if tile:
                                geotiff_outfile = os.path.join(out_path, "{}_{}_{}_{}_{}.tif".format(processor, val, satellite, date, tile))
                            else:
                                geotiff_outfile = os.path.join(out_path, "{}_{}_{}_{}.tif".format(processor, val, satellite, date))
                            number_bands = 2
                            if "single_band" in params[PARAMS_SECTION] and params[PARAMS_SECTION]["single_band"]:
                                number_bands = 1
                            netcdf_geotiff(input_file, geotiff_outfile, val, bands_min[idx], bands_max[idx], metadata, env, number_bands=number_bands)
                        except Exception as e:
                            print(e)
                            errors.append("Failed to convert {} band {}".format(processor, val))
                            log(env["General"]["log"], "Failed to convert {} band {}".format(processor, val), indent=3)

    if "upload" in params[PARAMS_SECTION] and params[PARAMS_SECTION]["upload"].lower() == "false":
        log(env["General"]["log"], "Not uploading files.", indent=1)
        return

    if "bucket" not in params[PARAMS_SECTION]:
        raise ValueError("bucket must be defined in parameters file")

    if "bucket_path" not in params[PARAMS_SECTION]:
        raise ValueError("bucket_path must be defined in parameters file")

    if not env.has_section("AWS"):
        raise ValueError("AWS section required in environment file.")

    if "aws_access_key_id" not in env["AWS"] or "aws_secret_access_key" not in env["AWS"]:
        raise ValueError("aws_access_key_id and aws_secret_access_key must be defined in [AWS] in the environment file")

    if l2product_file:
        log(env["General"]["log"], "Uploading files to {}".format(params[PARAMS_SECTION]["bucket"]), indent=1)
        client = boto3.client(
            's3',
            aws_access_key_id=env["AWS"]["aws_access_key_id"],
            aws_secret_access_key=env["AWS"]["aws_secret_access_key"]
        )
        out_folders = os.path.join(os.path.dirname(os.path.dirname(l2product_file)), OUT_DIR)
        failed = False
        bucket_path = params[PARAMS_SECTION]["bucket_path"]
        for root, dirs, files in os.walk(out_folders):
            for file in files:
                if file.endswith(".tif") or file.endswith(".json") or file.endswith(".ini"):
                    try:
                        log(env["General"]["log"], "Uploading {}".format(file), indent=2)
                        client.upload_file(os.path.join(root, file), params[PARAMS_SECTION]["bucket"], os.path.join(bucket_path, os.path.relpath(os.path.join(root, file), out_folders)))
                    except:
                        failed = True
                        log(env["General"]["log"], "Failed to upload: {}".format(file), indent=2)
        if failed:
            raise RuntimeError("Failed to upload all files to {}".format(params[PARAMS_SECTION]["bucket"]))

    if len(errors) > 0:
        raise ValueError(". ".join(errors))


def netcdf_geotiff(input_file, output_file, band, band_min, band_max, metadata, env, projection=4326, number_bands=2):
    log(env["General"]["log"], "Reading data from {}".format(input_file), indent=4)
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
            valid_pixel_expression = ""
            valid_pixels = np.zeros_like(values_flat)

    valid_pixels[values_flat < band_min] = 1
    valid_pixels[values_flat > band_max] = 1
    valid_pixels[np.isnan(values_flat)] = 1
    valid_pixels = valid_pixels.reshape(values.shape)

    if number_bands == 1:
        values[valid_pixels == 1] = np.nan

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

    dst_ds = gdal.GetDriverByName('GTiff').Create(temp_file, ny, nx, number_bands, gdal.GDT_Float32)

    dst_ds.SetGeoTransform(geotransform)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(projection)
    dst_ds.SetProjection(srs.ExportToWkt())
    dst_ds.GetRasterBand(1).WriteArray(values)
    if number_bands == 2:
        dst_ds.GetRasterBand(2).WriteArray(valid_pixels)
    dst_ds.SetMetadata(metadata)
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


def netcdf_json(input_file, output_file, band, decimals, band_min, band_max, satellite, date, env, projection=4326):
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


def get_mask_from_geojson(input_file, geojson_path):
    with open(geojson_path, 'r') as file:
        geojson_data = json.load(file)
    with Dataset(input_file, 'r+') as nc:
        if "latitude" in nc.variables.keys():
            latitudes = nc.variables['latitude'][:]
            longitudes = nc.variables['longitude'][:]
        else:
            latitudes = nc.variables['lat'][:]
            longitudes = nc.variables['lon'][:]

    lat_min, lat_max = np.min(latitudes), np.max(latitudes)
    lon_min, lon_max = np.min(longitudes), np.max(longitudes)
    netcdf_bounds = box(lon_min, lat_min, lon_max, lat_max)

    filtered_geometries = [
        shape(feature['geometry']) for feature in geojson_data['features']
        if shape(feature['geometry']).intersects(netcdf_bounds)
    ]
    multi_polygon = MultiPolygon(filtered_geometries)
    if len(latitudes.shape) == 1:
        x, y = len(longitudes), len(latitudes)
        latitudes = np.transpose(np.tile(latitudes, (x, 1)))
        longitudes = np.tile(longitudes, (y, 1))
    return shapely.vectorized.contains(multi_polygon, longitudes, latitudes).astype("int") * 255
