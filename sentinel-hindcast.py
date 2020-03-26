#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Import libs, some of them might be unused here, but something magical happens when they are imported
# which causes geos_c.dll and objectify.pyx errors to disappear.

from polymer.level1_msi import Level1_MSI
from polymer.gsw import GSW
import cartopy.crs as ccrs
from lxml import objectify
try:
    from snappy import jpy, GPF, ProductIO, ProductUtils
except RuntimeError:
    from snappy import jpy, GPF, ProductIO, ProductUtils

from packages.main import hindcast


hindcast("parameters_wdoc_S3.ini")
