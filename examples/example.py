#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Import libs, some of them might be unused here, but something magical happens when they are imported
# which causes geos_c.dll and objectify.pyx errors to disappear in windows.

import netCDF4
import cartopy.crs as ccrs
import sys
sys.path.append("/sencast")

from main import sencast

sencast("test_S3_processors.ini")

