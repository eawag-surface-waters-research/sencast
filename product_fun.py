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


def minimal_subset_of_products(product_paths, wkt):
    # ensure that all products are overlapping
    if len(product_paths) not in [2, 4]:
        print("Warning: Only sets of 2 or 4 products can be reduced!")
        return product_paths
    # ToDo: ensure that all products are overlapping

    # check which corners are covered by which products
    lons, lats = get_lons_lats(wkt)
    vertices = [{'lon': vertex[0], 'lat': vertex[1]} for vertex in zip(lons, lats)]
    product_corner_coverages = {}
    for product_path in product_paths:
        nc = read_product(product_path)
        product_perimeter = get_perimeter_from_product(nc)
        product_corner_coverages[product_path] = []
        for vertex in vertices:
            product_corner_coverages[product_path].append(contains(product_perimeter, vertex))

    # create superset of product_paths
    subsets = [[]]
    for product_path in product_paths:
        subsets = subsets + [subset + [product_path] for subset in subsets]

    # for all subsets of product_paths (beginning from smallest) try if they cover all vertices
    subsets.sort(key=len)
    for subset in subsets:
        if all([any([product_corner_coverages[product_path][idx] for product_path in subset]) for idx in range(len(vertices))]):
            return subset, True

    print("Warning: Could not find a subset of the delivered products, which fully covers the whole perimeter.")
    return product_paths, False


def get_lons_lats(wkt):
    """ Return one array with all longitudes and one array with all latitudes of the perimeter corners. """
    if not wkt.startswith("POLYGON"):
        raise RuntimeError("Provided wkt must be a polygon!")
    corners = [float(c) for c in re.findall(r'[-]?\d+\.\d+', wkt)]
    lons = [float(corner) for corner in corners[::2]]
    lats = [float(corner) for corner in corners[1::2]]
    return lons, lats


def contains(perimeter, location):
    """ Checks if a given convex perimeter[{lon, lat}] conatins a given location{lon, lat} """
    coverage = [False, False, False, False]
    for vertex in perimeter:
        if location['lon'] < vertex['lon'] and location['lat'] < vertex['lat']:
            coverage[0] = True
        if location['lon'] < vertex['lon'] and location['lat'] > vertex['lat']:
            coverage[1] = True
        if location['lon'] > vertex['lon'] and location['lat'] > vertex['lat']:
            coverage[2] = True
        if location['lon'] > vertex['lon'] and location['lat'] < vertex['lat']:
            coverage[3] = True
        if all(coverage):
            return True
    return False


def get_perimeter_from_product(nc):
    """ Returns the perimeter[{lon, lat}] of a sentinel image. """
    lats = nc.variables['latitude'][:]
    lons = nc.variables['longitude'][:]
    perimeter = []
    for lon, lat in zip(lons[0], lats[0]):
        perimeter.append({'lon': lon, 'lat': lat})
    for lon, lat in zip(lons[1:-1, -1], lats[1:-1, -1]):
        perimeter.append({'lon': lon, 'lat': lat})
    for lon, lat in zip(lons[-1], lats[-1]):
        perimeter.append({'lon': lon, 'lat': lat})
    for lon, lat in zip(lons[1:-1, 0], lats[1:-1, 0]):
        perimeter.append({'lon': lon, 'lat': lat})
    return perimeter


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
