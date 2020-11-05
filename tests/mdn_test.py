#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Import libs, some of them might be unused here, but something magical happens when they are imported
# which causes geos_c.dll and objectify.pyx errors to disappear in windows.
# import cartopy.crs
# import netCDF4

import sys
sys.path.append("/home/jamesrunnalls/eawagrs/sentinel-hindcast/build/sentinel-hindcast")
from main import hindcast

hindcast("/home/jamesrunnalls/eawagrs/sentinel-hindcast/build/sentinel-hindcast/parameters/mdn_test.ini")