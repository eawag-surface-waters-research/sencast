#! /usr/bin/env python
# coding: utf8

import numpy as np
from snappy import GeoPos
import re


def get_UL_LR_pixels_ROI(product, params):
        # Read the wkt parameter from params
        wkt = params['wkt']
        corners = re.findall("[-]?\d+\.\d+", wkt)
        corners = np.array([float(c) for c in corners], dtype=np.float32)
#         lat = np.array([corners[1], corners[5]])
#         lon = np.array([corners[0], corners[4]])
        # Get pixel coordinates of UL and LR corners for the selected ROI in the product
        h = product.getSceneRasterHeight()
        w = product.getSceneRasterWidth()
#         ul_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(lat.max(), lon.min()), None)
#         lr_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(lat.min(), lon.max()), None)
        ul_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(corners[1], 
                                                                corners[0]), None)
        ur_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(corners[3], 
                                                                corners[2]), None)
        lr_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(corners[5], 
                                                                corners[4]), None)
        ll_pos = product.getSceneGeoCoding().getPixelPos(GeoPos(corners[7], 
                                                                corners[6]), None)
        
        
        UL = np.array([np.floor(ul_pos.getY()).astype(int), 
                       np.floor(ul_pos.getX()).astype(int)])
        UR = np.array([np.floor(ur_pos.getY()).astype(int), 
                       np.floor(ur_pos.getX()).astype(int)])
        LR = np.array([np.ceil(lr_pos.getY()).astype(int), 
                       np.ceil(lr_pos.getX()).astype(int)])
        LL = np.array([np.ceil(ll_pos.getY()).astype(int), 
                       np.ceil(ll_pos.getX()).astype(int)])
        
        # If lat min < 0 
        if UL[0] < 0:
            UL[0] = 0
        if UR[0] < 0:
            UR[0] = 0
        # if lon min < 0
        if UL[1] < 0:
            UL[1] = 0
        if LL[1] < 0:
            LL[1] = 0
        # if lat max > h
        if LR[0] > h:
            LR[0] = h
        if LL[0] > h:
            LL[0] = h
        # if lon max > w
        if LR[1] > w:
            LR[1] = w
        if UR[1] > w:
            UR[1] = w
        return UL, UR, LR, LL


def get_UL_LR_geo_ROI(product, params):
        # Read the wkt parameter from params
        wkt = params['wkt']
        corners = re.findall("[-]?\d+\.\d+", wkt)
        corners = np.array([float(c) for c in corners], dtype=np.float32)
        lat = np.array([corners[1], corners[5]])
        lon = np.array([corners[0], corners[4]])
        return lat, lon
