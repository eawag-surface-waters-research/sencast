#! /usr/bin/env python
# -*- coding: utf-8 -*-

import sys

from datetime import date, datetime, timedelta

sys.path.append("/prj/sentinel-hindcast")

from auxil import load_params
from main import hindcast

params, params_file = load_params("/prj/datalakes/datalakes_sui_S3.ini")
params['General']['start'] = params['General']['end']
params['General']['end'] = (datetime.combine(date.today(), datetime.min.time()) - timedelta(days=5, seconds=1))\
    .strftime(r"%Y-%m-%dT%H:%M:%SZ")
with open(params_file, "w") as f:
    params.write(f)

hindcast(params_file, max_parallel_downloads=1, max_parallel_processors=1, max_parallel_adapters=1)
