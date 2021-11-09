#! /usr/bin/env python
# -*- coding: utf-8 -*-

import sys

sys.path.append("/home/jamesrunnalls/eawagrs/sentinel-hindcast/build/sentinel-hindcast")

from auxil import load_params
from main import hindcast

# Process New Data
dates = [["2019-01-01T00:00:00.000Z", "2019-01-05T23:59:59.999Z"],
         ["2019-04-08T00:00:00.000Z", "2019-04-12T23:59:59.999Z"],
         ["2019-07-15T00:00:00.000Z", "2019-07-19T23:59:59.999Z"],
         ["2019-09-29T00:00:00.000Z", "2019-10-03T23:59:59.999Z"],
         ["2019-12-25T00:00:00.000Z", "2019-12-29T23:59:59.999Z"]]

for date in dates:
    params, params_file = load_params("datalakes_sui_S3_test.ini")
    params['General']['start'] = date[0]
    params['General']['end'] = date[1]
    with open(params_file, "w") as f:
        params.write(f)
    hindcast(params_file, max_parallel_downloads=1, max_parallel_processors=1, max_parallel_adapters=1)
