#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re

from json import dump
from netCDF4 import Dataset


# Key of the params section for this adapter
PARAMS_SECTION = "DATALAKES"


def apply(env, region, input_file, params):
    if not env.has_section("Datalakes"):
        raise RuntimeWarning("Datalakes integration was not configured in this environment.")

    date = re.findall(r"\d{8}T\d{6}", os.path.basename(input_file))[0]
    out_path = os.path.join(env['Datalakes']['root_path'], region, date)
    os.makedirs(out_path, exist_ok=True)

    chl_file = os.path.join(out_path, "chl.json")
    nc_to_json(input_file, chl_file, params[PARAMS_SECTION]['chl_band'], lambda v: round(float(v), 6))

    qf_file = os.path.join(out_path, "quality_flags.json")
    nc_to_json(input_file, qf_file, "quality_flags", lambda v: int(v))

    pcf_file = os.path.join(out_path, "pixel_classif_flags.json")
    nc_to_json(input_file, pcf_file, "pixel_classif_flags", lambda v: int(v))

    with open(input_file, "rb") as f:
        nc_bytes = f.read()

    with open(os.path.join(out_path, os.path.basename(input_file)), "wb") as f:
        f.write(nc_bytes)


def nc_to_json(input_file, output_file, variable_name, value_read_expression):
    with Dataset(input_file, "r", format="NETCDF4") as nc:
        _lons, _lats, _values = nc.variables['lon'][:], nc.variables['lat'][:], nc.variables[variable_name][:]

    lonres, latres = float(round(abs(_lons[1] - _lons[0]), 12)), float(round(abs(_lats[1] - _lats[0]), 12))

    lons, lats, values = [], [], []
    for y in range(len(_values)):
        for x in range(len(_values[y])):
            if _values[y][x]:
                lons.append(round(float(_lons[x]), 6))
                lats.append(round(float(_lats[y]), 6))
                values.append(value_read_expression(_values[y][x]))

    with open(output_file, "w") as f:
        f.truncate()
        dump({'lonres': lonres, 'latres': latres, 'lon': lons, 'lat': lats, 'v': values}, f)
