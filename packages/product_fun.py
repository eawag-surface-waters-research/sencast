#! /usr/bin/env python
# -*- coding: utf-8 -*-

import numpy as np
import re

from haversine import haversine
from snappy import GeoPos


def get_corner_pixels_roi(product, wkt):
    h = product.getSceneRasterHeight()
    w = product.getSceneRasterWidth()

    lons, lats = get_lons_lats(wkt)

    ul = [min(lons), max(lats)]
    ur = [max(lons), max(lats)]
    lr = [max(lons), min(lats)]
    ll = [min(lons), min(lats)]

    ul_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(ul[1], ul[0]), None)
    ur_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(ur[1], ur[0]), None)
    lr_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(lr[1], lr[0]), None)
    ll_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(ll[1], ll[0]), None)

    ul_bool = ul_pos.x > 0 and ul_pos.y > 0
    ur_bool = ur_pos.x > 0 and ur_pos.y > 0
    lr_bool = lr_pos.x > 0 and lr_pos.y > 0
    ll_bool = ll_pos.x > 0 and ll_pos.y > 0

    UL = np.array([np.floor(ul_pos.getY()).astype(int), np.floor(ul_pos.getX()).astype(int)])
    UR = np.array([np.floor(ur_pos.getY()).astype(int), np.floor(ur_pos.getX()).astype(int)])
    LR = np.array([np.ceil(lr_pos.getY()).astype(int), np.ceil(lr_pos.getX()).astype(int)])
    LL = np.array([np.ceil(ll_pos.getY()).astype(int), np.ceil(ll_pos.getX()).astype(int)])

    # missing with perimeter partly too north
    if not ul_bool and not ur_bool:
        # and too west (only LR covered)
        if not ll_bool:
            UL = [1, 1]
            UR = [1, LR[1]]
            LL = [LR[0], 1]
        # and too east (only LL covered)
        elif not lr_bool:
            UL = [1, LL[1]]
            UR = [1, w]
            LR = [LL[0], w]
        else:
            UL = [1, LL[1]]
            UR = [1, LR[1]]

    # missing with perimeter partly too south
    elif not ll_bool and not lr_bool:
        # and too west (only UR covered)
        if not ul_bool:
            UL = [UR[0], 1]
            LR = [h, UR[1]]
            LL = [h, 1]
        # and too east (only UL covered)
        elif not ur_bool:
            LL = [h, UL[1]]
            UR = [UL[0], w]
            LR = [h, w]
        else:
            LL = [h, UL[1]]
            LR = [h, UR[1]]

    # missing with perimeter partly too east
    elif not ur_bool and not lr_bool:
        UR = [UL[0], w]
        LR = [LL[0], w]

    # missing with perimeter partly too west
    elif not ul_bool and not ll_bool:
        UL = [UR[0], 1]
        LL = [LR[0], 1]

    # single missing corners
    elif not ul_bool:
        UL = [UR[0], 1]
    elif not ur_bool:
        UR = [UL[0], w]
    elif not ll_bool:
        LL = [LR[0], 1]
    elif not lr_bool:
        LR = [LL[0], w]

    return UL, UR, LR, LL


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
