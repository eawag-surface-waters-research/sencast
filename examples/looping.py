#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Import libs, some of them might be unused here, but something magical happens when they are imported
# which causes geos_c.dll and objectify.pyx errors to disappear in windows.

import netCDF4
import cartopy.crs as ccrs
import sys
import configparser
from datetime import datetime, timedelta
sys.path.append("/sencast")

from main import sencast

ini_file = '../parameters/test_S3_processors.ini'

wkts = ["greifen", "garda"]
dates = ["2022-05-21", "2022-05-22"]

# start_date = datetime(2023, 1, 1)
# end_date = datetime(2023, 12, 31)
# dates = [(start_date + timedelta(days=x)).strftime("%Y-%m-%d") for x in range((end_date - start_date).days + 1)]

config = configparser.ConfigParser()
config.read(ini_file)

for date in dates:
    for wkt in wkts:
        try:
            print("Running Sencast for {} on {}".format(wkt, date))
            config["General"]["wkt_name"] = wkt
            config["General"]["start"] = "{}T00:00:00.000Z".format(date)
            config["General"]["end"] = "{}T23:59:59.999Z".format(date)

            with open(ini_file, 'w') as configfile:
                config.write(configfile)

            sencast(ini_file)
        except Exception as e:
            print(e)

