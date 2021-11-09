#! /usr/bin/env python
# -*- coding: utf-8 -*-

import sys

from datetime import date, datetime

sys.path.append("/prj/sentinel-hindcast")

from utils.auxil import load_params
from main import hindcast
from dias_apis.creodias.creodias import get_updated_files
from utils.auxil import load_environment, load_wkt


def parse_date_from_name(name):
    sensing_time = name.split("_")[7]
    sensing_year = sensing_time[:4]
    sensing_month = sensing_time[4:6]
    sensing_day = sensing_time[6:8]
    creation_time = datetime.strptime(name.split("_")[9], '%Y%m%dT%H%M%S')
    return "{}-{}-{}".format(sensing_year, sensing_month, sensing_day), creation_time


# Process New Data
params, params_file = load_params("/prj/sentinel-hindcast/parameters/datalakes_sui_S3.ini")
finalStart = "{}T00:00:00.000Z".format(date.today().strftime(r"%Y-%m-%d"))
finalEnd = "{}T23:59:59.999Z".format(date.today().strftime(r"%Y-%m-%d"))
params['General']['start'] = finalStart
params['General']['end'] = finalEnd
with open(params_file, "w") as f:
    params.write(f)
hindcast(params_file, max_parallel_downloads=1, max_parallel_processors=1, max_parallel_adapters=1)

# Re-process old data
env, env_file = load_environment()
auth = [env['CREODIAS']['username'], env['CREODIAS']['password']]
publishedAfter, end, start = params['General']['start'], params['General']['start'], params['DATALAKES']['origin_date']
sensor, resolution, wkt = params['General']['sensor'], params['General']['resolution'], params['General']['wkt']
if not wkt:
    wkt, _ = load_wkt("{}.wkt".format(params['General']['wkt_name']), env['General']['wkt_path'])
download_requests, product_names = get_updated_files(auth, start, end, sensor, resolution, wkt, publishedAfter)
dates = []
p_date = datetime.strptime(publishedAfter, "%Y-%m-%dT%H:%M:%S.%fZ")
for name in product_names:
    sensing_date, creation_date = parse_date_from_name(name)
    if creation_date > p_date and sensing_date not in dates:
        dates.append(sensing_date)

for run_date in dates:
    params['General']['start'] = "{}T00:00:00.000Z".format(run_date)
    params['General']['end'] = "{}T23:59:59.999Z".format(run_date)
    with open(params_file, "w") as f:
        params.write(f)
    hindcast(params_file, max_parallel_downloads=1, max_parallel_processors=1, max_parallel_adapters=1)

# Reset parameters file
params['General']['start'] = finalStart
params['General']['end'] = finalEnd
with open(params_file, "w") as f:
    params.write(f)
