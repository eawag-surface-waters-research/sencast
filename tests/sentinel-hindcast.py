#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Import libs, some of them might be unused here, but something magical happens when they are imported
# which causes geos_c.dll and objectify.pyx errors to disappear in windows.
import cartopy.crs
import netCDF4

from main import hindcast

hindcast("S3_geneva_2019.ini")
