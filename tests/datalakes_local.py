#! /usr/bin/env python
# -*- coding: utf-8 -*-

import sys

sys.path.append("/home/jamesrunnalls/eawagrs/sentinel-hindcast/build/sentinel-hindcast")

from auxil import load_params
from main import hindcast

params, params_file = load_params("/home/jamesrunnalls/eawagrs/sentinel-hindcast/build/sentinel-hindcast/parameters/datalakes_sui_S3.ini")
#params['General']['start'] = params['General']['end']
#params['General']['end'] = (date.today() - timedelta(days=5)).strftime(r"%Y-%m-%dT%H:%M:%SZ")
with open(params_file, "w") as f:
    params.write(f)

hindcast(params_file, max_parallel_downloads=1, max_parallel_processors=1, max_parallel_adapters=1)
