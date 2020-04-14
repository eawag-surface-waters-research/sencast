#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Import libs, some of them might be unused here, but something magical happens when they are imported
# which causes geos_c.dll and objectify.pyx errors to disappear.

import cartopy.crs
import netCDF4

from packages.main import hindcast

hindcast("datalakes_sui_S3.ini")
