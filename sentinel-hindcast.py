#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Import libs, some of them might be unused here, but something magical happens when they are imported
# which causes geos_c.dll and objectify.pyx errors to disappear.

import cartopy.crs
import os

from packages.main import hindcast

# Removes SEVERE message in gpt log
os.environ['LD_LIBRARY_PATH'] = "."

hindcast("parameters_wdoc_S3.ini")
