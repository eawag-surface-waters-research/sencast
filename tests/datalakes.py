#! /usr/bin/env python
# -*- coding: utf-8 -*-

import sys

from datetime import date, timedelta, datetime

sys.path.append("/prj/sentinel-hindcast")

from auxil import load_params
from main import hindcast
from externalapis.creodias_api import get_updated_files
from auxil import load_environment, load_wkt
from product_fun import parse_date_from_name

# Process New Data
params, params_file = load_params("/prj/sentinel-hindcast/parameters/datalakes_sui_S3.ini")
finalStart = "{}T00:00:00.000Z".format(date.today().strftime(r"%Y-%m-%d"))
finalEnd = "{}T23:59:59.999Z".format(date.today().strftime(r"%Y-%m-%d"))
params['General']['start'] = finalStart
params['General']['end'] = finalEnd
with open(params_file, "w") as f:
    params.write(f)
hindcast(params_file, max_parallel_downloads=1, max_parallel_processors=1, max_parallel_adapters=1)
