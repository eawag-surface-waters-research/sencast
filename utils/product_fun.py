#! /usr/bin/env python
# -*- coding: utf-8 -*-
import os
import re
import subprocess

from haversine import haversine
from datetime import datetime
from utils.auxil import log
from netCDF4 import Dataset


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
    if "S3A" in product_name:
        return "S3A"
    elif "S3B" in product_name:
        return "S3B"
    elif "S2A" in product_name:
        return "S2A"
    elif "S2B" in product_name:
        return "S2B"
    elif "LC08" in product_name:
        return "L8"
    raise RuntimeError("Could not read satellite name from product name [{}]".format(product_name))


def filter_for_timeliness(download_requests, product_names, env):
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
                log(env["General"]["log"], "Removed superseded file: {}).".format(s3_products[j]["name"]))
        else:
            filtered_product_names.append(s3_products[j]["name"])
            filtered_download_requests.append({"uuid": s3_products[j]["uuid"]})

    return filtered_download_requests, filtered_product_names


def get_south_east_north_west_bound(wkt):
    """ Return south, east, north, and west boundery of a given wkt. """
    lons, lats = get_lons_lats(wkt)
    return min(lats), max(lons), max(lats), min(lons)


def get_lons_lats(wkt):
    """ Return one array with all longitudes and one array with all latitudes of the perimeter corners. """
    if wkt[0:7].lower() != "polygon":
        raise RuntimeError("Provided wkt must be a polygon!")
    corners = [float(c) for c in re.findall(r'[-]?\d+\.\d+', wkt)]
    lons = [float(corner) for corner in corners[::2]]
    lats = [float(corner) for corner in corners[1::2]]
    return lons, lats


def get_reproject_params_from_wkt(wkt, resolution):
    south, east, north, west = get_south_east_north_west_bound(wkt)
    x_dist = haversine((south, west), (south, east))
    y_dist = haversine((south, west), (north, west))
    x_pix = int(round(x_dist / (int(resolution) / 1000)))
    y_pix = int(round(y_dist / (int(resolution) / 1000)))
    x_pixsize = (east - west) / x_pix
    y_pixsize = (north - south) / y_pix

    return {'easting': str(west), 'northing': str(north), 'pixelSizeX': str(x_pixsize),
            'pixelSizeY': str(y_pixsize), 'width': str(x_pix), 'height': str(y_pix)}


def get_sensing_date_from_product_name(product_name):
    return re.findall(r"\d{8}", product_name)[0]


def get_sensing_datetime_from_product_name(product_name):
    return re.findall(r"\d{8}", product_name)[0] + "T" + re.findall(r"\d{6}", product_name)[1]


def get_l1product_path(env, product_name):
    if product_name.startswith("S3A") or product_name.startswith("S3B"):
        satellite = "Sentinel-3"
        sensor = "OLCI"
        dataset = product_name[4:12]
        date = datetime.strptime(get_sensing_date_from_product_name(product_name), r"%Y%m%d")
    elif product_name.startswith("S2A") or product_name.startswith("S2B"):
        satellite = "Sentinel-2"
        sensor = "MSI"
        dataset = product_name[7:10]
        date = datetime.strptime(get_sensing_date_from_product_name(product_name), r"%Y%m%d")
    elif product_name.startswith("LC08"):
        satellite = "Landsat8"
        sensor = "OLI_TIRS"
        dataset = product_name[5:9]
        date = datetime.strptime(get_sensing_date_from_product_name(product_name), r"%Y%m%d")
    else:
        raise RuntimeError("Unable to retrieve satellite from product name: {}".format(product_name))

    kwargs = {
        'product_name': product_name,
        'satellite': satellite,
        'sensor': sensor,
        'dataset': dataset,
        'year': date.strftime(r"%Y"),
        'month': date.strftime(r"%m"),
        'day': date.strftime(r"%d")
    }

    return env['DIAS']['l1_path'].format(**kwargs)


def get_main_file_from_product_path(l1product_path):
    product_name = os.path.basename(l1product_path)
    satellite = get_satellite_name_from_product_name(product_name)
    if satellite in ["S2A", "S2B"]:
        return os.path.join(l1product_path, "MTD_MSIL1C.xml")
    elif satellite in ["S3A", "S3B"]:
        return os.path.join(l1product_path, "xfdumanifest.xml")
    elif satellite == "L8":
        return os.path.join(l1product_path, "{}_MTL.txt".format(product_name))
    else:
        raise RuntimeError("Unknown satellite: {}".format(satellite))


def generate_l8_angle_files(env, l1product_path):
    product_name = os.path.basename(l1product_path)
    ang_file = os.path.join(l1product_path, "{}_ANG.txt".format(product_name))
    args = [os.path.join(env['L8_ANGLES']['root_path'], "l8_angles"), ang_file, "BOTH", "1", "-b", "1"]
    log(env["General"]["log"], "Calling [{}]...".format(" ".join(args)))
    return subprocess.call(args, cwd=l1product_path)


def get_band_names_from_nc(product_file):
    bands = []
    with Dataset(product_file) as nc:
        for var in nc.variables:
            if len(nc.variables[var].shape) == 2:
                if hasattr(nc.variables[var], 'orig_name'):
                    bands.append(nc.variables[var].orig_name)
                else:
                    bands.append(var)
    return bands

