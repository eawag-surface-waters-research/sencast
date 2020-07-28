#! /usr/bin/env python
# -*- coding: utf-8 -*-

import re

from haversine import haversine
from snappy import GeoPos, ProductIO
from datetime import datetime


def get_corner_pixels_roi(product_path, wkt):
    product = ProductIO.readProduct(product_path)

    h, w = product.getSceneRasterHeight(), product.getSceneRasterWidth()

    lons, lats = get_lons_lats(wkt)
    ul_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(max(lats), min(lons)), None)
    ur_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(max(lats), max(lons)), None)
    ll_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(min(lats), min(lons)), None)
    lr_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(min(lats), max(lons)), None)

    UL = [int(ul_pos.y) if (0 <= ul_pos.y < h) else 0, int(ul_pos.x) if (0 <= ul_pos.x < w) else 0]
    UR = [int(ur_pos.y) if (0 <= ur_pos.y < h) else 0, int(ur_pos.x) if (0 <= ur_pos.x < w) else w]
    LL = [int(ll_pos.y) if (0 <= ll_pos.y < h) else h, int(ll_pos.x) if (0 <= ll_pos.x < w) else 0]
    LR = [int(lr_pos.y) if (0 <= lr_pos.y < h) else h, int(lr_pos.x) if (0 <= lr_pos.x < w) else w]

    product.closeIO()
    return UL, UR, LR, LL


def parse_date_from_name(name):
    sensing_time = name.split("_")[7]
    sensing_year = sensing_time[:4]
    sensing_month = sensing_time[4:6]
    sensing_day = sensing_time[6:8]
    creation_time = datetime.strptime(name.split("_")[9], '%Y%m%dT%H%M%S')
    return "{}-{}-{}".format(sensing_year, sensing_month, sensing_day), creation_time


def minimal_subset_of_products(product_paths, wkt):
    # ensure that all products are overlapping
    if len(product_paths) not in [2, 4]:
        print("Warning: Only sets of 2 or 4 products can be compared!")
        return product_paths
    # ToDo: ensure that all products are overlapping

    # check which corners are covered by which products
    product_corner_coverages = {}
    for product_path in product_paths:
        product = ProductIO.readProduct(product_path)
        h, w = product.getSceneRasterHeight(), product.getSceneRasterWidth()
        lons, lats = get_lons_lats(wkt)
        ul, ur, ll, lr = [min(lons), max(lats)], [max(lons), max(lats)], [min(lons), min(lats)], [max(lons), min(lats)]
        ul_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(ul[1], ul[0]), None)
        ur_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(ur[1], ur[0]), None)
        ll_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(ll[1], ll[0]), None)
        lr_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(lr[1], lr[0]), None)
        product_corner_coverages[product_path] = {}
        product_corner_coverages[product_path]['ul'] = (0 <= ul_pos.x < w) and (0 <= ul_pos.y < h)
        product_corner_coverages[product_path]['ur'] = (0 <= ur_pos.x < w) and (0 <= ur_pos.y < h)
        product_corner_coverages[product_path]['ll'] = (0 <= ll_pos.x < w) and (0 <= ll_pos.y < h)
        product_corner_coverages[product_path]['lr'] = (0 <= lr_pos.x < w) and (0 <= lr_pos.y < h)
        product.closeIO()

    # create superset of product_paths
    subsets = [[]]
    for product_path in product_paths:
        subsets = subsets + [subset + [product_path] for subset in subsets]

    # for all subsets of product_paths (beginning from smallest) try if they cover all corners
    subsets.sort(key=len)
    for subset in subsets:
        combined_coverage = [
            any([product_corner_coverages[product_path]['ul'] for product_path in subset]),
            any([product_corner_coverages[product_path]['ur'] for product_path in subset]),
            any([product_corner_coverages[product_path]['ll'] for product_path in subset]),
            any([product_corner_coverages[product_path]['lr'] for product_path in subset])
        ]
        if all(combined_coverage):
            return subset, True

    print("Warning: Could not find a subset of the delivered products, which fully covers the whole perimeter.")
    return product_paths, False


def get_coordinates(wkt):
    return [{'x': lon, 'y': lat} for lon, lat in zip(get_lons_lats(wkt))]


def get_lons_lats(wkt):
    if not wkt.startswith("POLYGON"):
        raise RuntimeError("Provided wkt must be a polygon!")
    corners = [float(c) for c in re.findall(r'[-]?\d+\.\d+', wkt)]
    lons = [float(corner) for corner in corners[::2]]
    lats = [float(corner) for corner in corners[1::2]]
    return lons, lats


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
