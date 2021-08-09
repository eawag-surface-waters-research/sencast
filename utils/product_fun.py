#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re

from haversine import haversine
from netCDF4 import Dataset
from datetime import datetime


def parse_date_from_name(name):
    sensing_time = name.split("_")[7]
    sensing_year = sensing_time[:4]
    sensing_month = sensing_time[4:6]
    sensing_day = sensing_time[6:8]
    creation_time = datetime.strptime(name.split("_")[9], '%Y%m%dT%H%M%S')
    return "{}-{}-{}".format(sensing_year, sensing_month, sensing_day), creation_time


def parse_s3_name(name):
    if "S3A_" in name or "S3B_" in name:
        name_list = name.split("_")
        return name_list[7], name_list[8], name_list[9], name_list[0]
    else:
        return False, False, False, False


def get_satellite_name_from_product_name(product_name):
    if product_name.startswith("S3A"):
        return "S3A"
    elif product_name.startswith("S3B"):
        return "S3B"
    elif product_name.startswith("S2A"):
        return "S2A"
    elif product_name.startswith("S2B"):
        return "S2B"
    else:
        return "Unknown"


def get_satellite_name_from_name(product_name):
    satellite_names = ["S3A", "S3B", "S2A", "S2B"]
    for satellite_name in satellite_names:
        if satellite_name in product_name:
            return satellite_name
    # ToDo: add satellite name to mosaicking
    if 'Mosaic_' in product_name:
        return 'S2A'
    return "NA"


def filter_for_timeliness(download_requests, product_names):
    s3_products = []
    for i in range(len(product_names)):
        tmp = product_names[i]
        uuid = download_requests[i]["uuid"]
        if "S3A_" in tmp or "S3B_" in tmp:
            sensing_start, sensing_end, product_creation, satellite = parse_s3_name(tmp)
            s3_products.append({"name": tmp, "uuid": uuid, "sensing_start": sensing_start, "sensing_end": sensing_end,
                                "product_creation": product_creation, "satellite": satellite})
        else:
            s3_products.append({"name": tmp, "uuid": uuid})
    filtered_download_requests = []
    filtered_product_names = []
    for j in range(len(s3_products)):
        if "S3A_" in s3_products[j]["name"] or "S3B_" in s3_products[j]["name"]:
            matching_sensing = [f for f in s3_products if f['sensing_start'] == s3_products[j]['sensing_start']
                                and f['sensing_end'] == s3_products[j]['sensing_end']
                                and f['satellite'] == s3_products[j]['satellite']]
            creation = [d['product_creation'] for d in matching_sensing]
            creation.sort(reverse=True)
            if s3_products[j]['product_creation'] == creation[0]:
                filtered_product_names.append(s3_products[j]["name"])
                filtered_download_requests.append({"uuid": s3_products[j]["uuid"]})
            else:
                print("Removed superseded file: {}).".format(s3_products[j]["name"]))
        else:
            filtered_product_names.append(s3_products[j]["name"])
            filtered_download_requests.append({"uuid": s3_products[j]["uuid"]})

    return filtered_download_requests, filtered_product_names


def get_lons_lats(wkt):
    """ Return one array with all longitudes and one array with all latitudes of the perimeter corners. """
    if not wkt.startswith("POLYGON"):
        raise RuntimeError("Provided wkt must be a polygon!")
    corners = [float(c) for c in re.findall(r'[-]?\d+\.\d+', wkt)]
    lons = [float(corner) for corner in corners[::2]]
    lats = [float(corner) for corner in corners[1::2]]
    return lons, lats


def read_product(product_path):
    if os.path.isdir(product_path):
        return Dataset(product_path + "\\geo_coordinates.nc")
    elif os.path.isfile(product_path):
        return Dataset(product_path)
    raise RuntimeError("The provided path [{}] does not exist!".format(product_path))


def get_reproject_params_from_wkt(wkt, resolution):
    lons, lats = get_lons_lats(wkt)
    x_dist = haversine((min(lats), min(lons)), (min(lats), max(lons)))
    y_dist = haversine((min(lats), min(lons)), (max(lats), min(lons)))
    x_pix = int(round(x_dist / (int(resolution) / 1000)))
    y_pix = int(round(y_dist / (int(resolution) / 1000)))
    x_pixsize = (max(lons) - min(lons)) / x_pix
    y_pixsize = (max(lats) - min(lats)) / y_pix

    return {'easting': str(min(lons)), 'northing': str(max(lats)), 'pixelSizeX': str(x_pixsize),
            'pixelSizeY': str(y_pixsize), 'width': str(x_pix), 'height': str(y_pix)}


def get_band_names(product_path):
    if os.path.isdir(product_path):
        band_names = []
        for nc_file in os.listdir(product_path):
            if nc_file.endswith(".nc"):
                band_names.extend(list(Dataset(product_path + "\\" + nc_file).variables.keys()))
        return set(band_names)
    elif os.path.isfile(product_path):
        return set(Dataset(product_path).variables.keys())
    raise RuntimeError("The provided path [{}] does not exist!".format(product_path))
