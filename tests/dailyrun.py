#! /usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import datetime

sys.path.append("/home/jamesrunnalls/eawagrs/sentinel-hindcast/build/sentinel-hindcast")

from auxil import load_params
from main import hindcast

params, params_file = load_params("/home/jamesrunnalls/eawagrs/sentinel-hindcast/build/sentinel-hindcast/parameters/datalakes_sui_S3.ini")

start_date = datetime.datetime(2018, 1, 1)
number_of_days = 3

for days in range(number_of_days):
    process_date = start_date + datetime.timedelta(days=days)
    params['General']['start'] = process_date.strftime(r"%Y-%m-%d") + "T00:00:00.000Z"
    params['General']['end'] = process_date.strftime(r"%Y-%m-%d") + "T23:59:59.999Z"
    with open(params_file, "w") as f:
        params.write(f)

    hindcast(params_file, max_parallel_downloads=1, max_parallel_processors=1, max_parallel_adapters=1)
