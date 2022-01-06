#! /usr/bin/env python
# -*- coding: utf-8 -*-

import sys

from datetime import date, datetime, timedelta

sys.path.append("/prj/sentinel-hindcast")

from utils.auxil import load_params
from main import hindcast

# Process New Data
params, params_file = load_params("/prj/sentinel-hindcast/parameters/datalakes_sui_S3.ini")
finalStart = "{}T00:00:00.000Z".format(date.today().strftime(r"%Y-%m-%d"))
finalEnd = "{}T23:59:59.999Z".format(date.today().strftime(r"%Y-%m-%d"))
params['General']['start'] = finalStart
params['General']['end'] = finalEnd
with open(params_file, "w") as f:
    params.write(f)
hindcast(params_file, max_parallel_downloads=1, max_parallel_processors=1, max_parallel_adapters=1)

# Re-process old data (2 weeks ago)
old_date = datetime.today() - timedelta(days=14)
params, params_file = load_params("/prj/sentinel-hindcast/parameters/datalakes_sui_S3.ini")
finalStart = "{}T00:00:00.000Z".format(old_date.strftime(r"%Y-%m-%d"))
finalEnd = "{}T23:59:59.999Z".format(old_date.strftime(r"%Y-%m-%d"))
params['General']['start'] = finalStart
params['General']['end'] = finalEnd
with open(params_file, "w") as f:
    params.write(f)
hindcast(params_file, max_parallel_downloads=1, max_parallel_processors=1, max_parallel_adapters=1)

