#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""The Datalakes adapter is designed to output specified bands to JSON format in order to facilitate web visualisation
in the Datalakes data portal https://www.datalakes-eawag.ch/.
"""

import os
import requests

from json import dump
from netCDF4 import Dataset
import numpy as np

from auxil import get_sensing_date_from_product_name


# the url of the datalakes api
API_URL = "https://api.datalakes-eawag.ch"
# the url to post new data notification to
NOTIFY_URL = API_URL + "/externaldata/sync/remotesensing"
# key of the params section for this adapter
PARAMS_SECTION = "DATALAKES"
# the file name pattern for json output files
JSON_FILENAME = "{}_{}_{}.json"
# the file name pattern for json output files
NC_FILENAME = "{}_{}.nc"



def apply(env, params, l2product_files, date):
    """Apply datalakes adapter.
            1. Converts specified band in NetCDF to JSON format
            2. Saves files to S3 storage
            3. Hits Datalakes endpoint to inform server of new data

            Parameters
            -------------

            params
                Dictionary of parameters, loaded from input file
            env
                Dictionary of environment parameters, loaded from input file
            l2product_files
                Dictionary of Level 2 product files created by processors
            date
                Run date
            """
    if not env.has_section("DATALAKES"):
        raise RuntimeWarning("Datalakes integration was not configured in this environment.")
    print("Applying datalakes...")
    for key in params[PARAMS_SECTION].keys():
        processor = key[0:key.find("_")].upper()
        if processor in l2product_files.keys():
            l2product_file = l2product_files[processor]
            date = get_sensing_date_from_product_name(os.path.basename(l2product_file))
            out_path = os.path.join(env['DATALAKES']['root_path'], params['General']['wkt_name'], date)
            output_file_main = os.path.join(out_path, NC_FILENAME.format(processor, date))
            os.makedirs(out_path, exist_ok=True)
            if os.path.exists(output_file_main):
                if "synchronise" in params["General"].keys() and params['General']['synchronise'] == "false":
                    print("Removing file: ${}".format(output_file_main))
                    os.remove(output_file_main)
                    for band in list(filter(None, params[PARAMS_SECTION][key].split(","))):
                        output_file = os.path.join(out_path, JSON_FILENAME.format(processor, band, date))
                        nc_to_json(l2product_file, output_file, band, lambda v: round(float(v), 6))
                    with open(l2product_file, "rb") as f:
                        nc_bytes = f.read()
                    with open(output_file_main, "wb") as f:
                        f.write(nc_bytes)
                else:
                    print("Skipping Datalakes. Target already exists")
            else:
                for band in list(filter(None, params[PARAMS_SECTION][key].split(","))):
                    output_file = os.path.join(out_path, JSON_FILENAME.format(processor, band, date))
                    nc_to_json(l2product_file, output_file, band, lambda v: round(float(v), 6))
                with open(l2product_file, "rb") as f:
                    nc_bytes = f.read()
                with open(output_file_main, "wb") as f:
                    f.write(nc_bytes)

    notify_datalakes(env['DATALAKES']['api_key'])


def nc_to_json(input_file, output_file, variable_name, value_read_expression):
    with Dataset(input_file, "r", format="NETCDF4") as nc:
        _lons, _lats, _values = nc.variables['lon'][:], nc.variables['lat'][:], nc.variables[variable_name][:]

    lonres, latres = float(round(abs(_lons[1] - _lons[0]), 12)), float(round(abs(_lats[1] - _lats[0]), 12))

    lons, lats, values = [], [], []
    for y in range(len(_values)):
        for x in range(len(_values[y])):
            if _values[y][x] and not np.isnan(_values[y][x]):
                lons.append(round(float(_lons[x]), 6))
                lats.append(round(float(_lats[y]), 6))
                values.append(value_read_expression(_values[y][x]))

    with open(output_file, "w") as f:
        f.truncate()
        dump({'lonres': lonres, 'latres': latres, 'lon': lons, 'lat': lats, 'v': values}, f)


def notify_datalakes(api_key):
    print("Notifying Datalakes about new data...")
    requests.get(NOTIFY_URL, auth=api_key)
