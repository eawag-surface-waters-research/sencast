#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import requests

from json import dump
from netCDF4 import Dataset

from auxil import get_sensing_date_from_product_name
from snappy import ProductIO, PixelPos

# key of the params section for this adapter
PARAMS_SECTION = "PRIMARYPRODUCTION"
# the file name pattern for output file
FILENAME = "{}_{}.nc"

def apply(env, params, l2product_files):
    if not env.has_section(PARAMS_SECTION):
        raise RuntimeWarning("Primary Production was not configured in this environment.")
    print("Applying Primary Production...")
