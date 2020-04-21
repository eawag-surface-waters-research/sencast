#! /usr/bin/env python
# -*- coding: utf-8 -*-

import numpy as np
import re

from haversine import haversine
from snappy import GeoPos, ProductIO


def get_corner_pixels_roi(product_path, wkt):
    product = ProductIO.readProduct(product_path)

    h, w = product.getSceneRasterHeight(), product.getSceneRasterWidth()

    lons, lats = get_lons_lats(wkt)
    ul, ur, ll, lr = [min(lons), max(lats)], [max(lons), max(lats)], [min(lons), min(lats)], [max(lons), min(lats)]

    ul_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(ul[1], ul[0]), None)
    ur_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(ur[1], ur[0]), None)
    ll_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(ll[1], ll[0]), None)
    lr_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(lr[1], lr[0]), None)

    ul_bool = ul_pos.x > 0 and ul_pos.y > 0
    ur_bool = ur_pos.x > 0 and ur_pos.y > 0
    ll_bool = ll_pos.x > 0 and ll_pos.y > 0
    lr_bool = lr_pos.x > 0 and lr_pos.y > 0

    UL = np.array([np.floor(ul_pos.getY()).astype(int), np.floor(ul_pos.getX()).astype(int)])
    UR = np.array([np.floor(ur_pos.getY()).astype(int), np.floor(ur_pos.getX()).astype(int)])
    LL = np.array([np.ceil(ll_pos.getY()).astype(int), np.ceil(ll_pos.getX()).astype(int)])
    LR = np.array([np.ceil(lr_pos.getY()).astype(int), np.ceil(lr_pos.getX()).astype(int)])

    # perimeter partly too north
    if not ul_bool and not ur_bool:
        # and too west (only LR covered)
        if not ll_bool:
            UL, UR, LL = [1, 1], [1, LR[1]], [LR[0], 1]
        # and too east (only LL covered)
        elif not lr_bool:
            UL, UR, LR = [1, LL[1]], [1, w], [LL[0], w]
        else:
            UL, UR = [1, LL[1]], [1, LR[1]]

    # perimeter partly too south
    elif not ll_bool and not lr_bool:
        # and too west (only UR covered)
        if not ul_bool:
            UL, LR, LL = [UR[0], 1], [h, UR[1]], [h, 1]
        # and too east (only UL covered)
        elif not ur_bool:
            LL, UR, LR = [h, UL[1]], [UL[0], w], [h, w]
        else:
            LL, LR = [h, UL[1]], [h, UR[1]]

    # perimeter partly too east
    elif not ur_bool and not lr_bool:
        UR, LR = [UL[0], w], [LL[0], w]

    # perimeter partly too west
    elif not ul_bool and not ll_bool:
        UL, LL = [UR[0], 1], [LR[0], 1]

    # single missing corners
    elif not ul_bool:
        UL = [UR[0], 1]
    elif not ur_bool:
        UR = [UL[0], w]
    elif not ll_bool:
        LL = [LR[0], 1]
    elif not lr_bool:
        LR = [LL[0], w]

    product.closeIO()
    return UL, UR, LR, LL


def minimal_subset_of_products(product_paths, wkt):
    # ensure that all products are overlapping
    if len(product_paths) not in [1, 2, 4]:
        print("Warning: Only sets of 1, 2, or 4 producst can be compared!")
        return product_paths
    # ToDo: ensure that all products are overlapping

    # check which corners are covered by which products
    ul_key, ur_key, ll_key, lr_key = 0, 1, 2, 3
    product_corner_coverages = {}
    for product_path in product_paths:
        product = ProductIO.readProduct(product_path)
        lons, lats = get_lons_lats(wkt)
        ul, ur, ll, lr = [min(lons), max(lats)], [max(lons), max(lats)], [min(lons), min(lats)], [max(lons), min(lats)]
        ul_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(ul[1], ul[0]), None)
        ur_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(ur[1], ur[0]), None)
        ll_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(ll[1], ll[0]), None)
        lr_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(lr[1], lr[0]), None)
        product_corner_coverages[product_path] = {}
        product_corner_coverages[product_path][ul_key] = ul_pos.x > 0 and ul_pos.y > 0
        product_corner_coverages[product_path][ur_key] = ur_pos.x > 0 and ur_pos.y > 0
        product_corner_coverages[product_path][ll_key] = ll_pos.x > 0 and ll_pos.y > 0
        product_corner_coverages[product_path][lr_key] = lr_pos.x > 0 and lr_pos.y > 0
        product.closeIO()

    # create superset of product_paths
    subsets = [[]]
    for product_path in product_paths:
        subsets = subsets + [subset + [product_path] for subset in subsets]

    # for all subsets of product_paths (beginning from smallest) try if they cover all corners
    subsets.sort(key=len)
    for subset in subsets:
        combined_coverage = [
            any([product_corner_coverages[product_path][ul_key] for product_path in subset]),
            any([product_corner_coverages[product_path][ur_key] for product_path in subset]),
            any([product_corner_coverages[product_path][ll_key] for product_path in subset]),
            any([product_corner_coverages[product_path][lr_key] for product_path in subset])
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
