#! /usr/bin/env python
# -*- coding: utf-8 -*-

import numpy as np
from snappy import GeoPos, jpy
from snappy import WKTReader
import re

FileReader = jpy.get_type('java.io.FileReader')


def get_corner_pixels_ROI(product, params):
        # Read the wkt parameter from params
        wkt_file = params['wkt file']
        perimeter = WKTReader().read(FileReader(wkt_file))
        lats = []
        lons = []
        for coordinate in perimeter.getCoordinates():
            lats.append(coordinate.y)
            lons.append(coordinate.x)
            
        ul = [min(lons), max(lats)]
        ur = [max(lons), max(lats)]
        lr = [max(lons), min(lats)]
        ll = [min(lons), min(lats)]
        
        
        ul_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(ul[1], 
                                                                ul[0]), None)
        ur_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(ur[1], 
                                                                ur[0]), None)
        lr_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(lr[1], 
                                                                lr[0]), None)
        ll_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(ll[1], 
                                                                ll[0]), None)
        
        ul_bool = ul_pos.x > 0 and ul_pos.y > 0
        ur_bool = ur_pos.x > 0 and ur_pos.y > 0
        lr_bool = lr_pos.x > 0 and lr_pos.y > 0
        ll_bool = ll_pos.x > 0 and ll_pos.y > 0
        
        UL = np.array([np.floor(ul_pos.getY()).astype(int), 
                           np.floor(ul_pos.getX()).astype(int)])
        UR = np.array([np.floor(ur_pos.getY()).astype(int), 
                           np.floor(ur_pos.getX()).astype(int)])
        LR = np.array([np.ceil(lr_pos.getY()).astype(int), 
                       np.ceil(lr_pos.getX()).astype(int)])
        LL = np.array([np.ceil(ll_pos.getY()).astype(int), 
                       np.ceil(ll_pos.getX()).astype(int)])
        
        h = product.getSceneRasterHeight()
        w = product.getSceneRasterWidth()
        
        # I see 8 configurations which can give errors
        if not ul_bool and not ur_bool and lr_bool and not ll_bool:
            UL = [0, 0]
        if not ul_bool and ur_bool and lr_bool and not ll_bool:
            UL = [UR[0], 0]
        if not ul_bool and ur_bool and not lr_bool and not ll_bool:
            UL = [UR[0],0]
            LR = [h, UR[1]]
        if ul_bool and ur_bool and not lr_bool and not ll_bool:
            LR = [h, UR[1]]
        if ul_bool and not ur_bool and not lr_bool and not ll_bool:
            LR = [h, w]
        if ul_bool and not ur_bool and not lr_bool and ll_bool:
            LR = [LL[0], w]
        if not ul_bool and not ur_bool and not lr_bool and ll_bool:
            UL = [0, LL[1]]
            LR = [LL[0], w]
        if not ul_bool and not ur_bool and lr_bool and ll_bool:
            UL = [0, LL[1]]
        return UL, UR, LR, LL


def get_UL_LR_geo_ROI(product, params):
        # Read the wkt parameter from params
        wkt = params['wkt']
        corners = re.findall("[-]?\d+\.\d+", wkt)
        corners = np.array([float(c) for c in corners], dtype=np.float32)
        lat = np.array([corners[1], corners[5]])
        lon = np.array([corners[0], corners[4]])
        return lat, lon
