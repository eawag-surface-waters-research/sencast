#! /usr/bin/env python
# -*- coding: utf-8 -*-
import datetime
import sys

sys.path.append("/prj/sentinel-hindcast")

from main import do_hindcast
from auxil import load_environment, load_params, load_wkt

env, _ = load_environment()

params, params_file = load_params("/prj/datalakes/datalakes_sui_S3.ini")
if not params['General']['wkt']:
    params['General']['wkt'], _ = load_wkt("{}.wkt".format(params['General']['wkt_name']), env['General']['wkt_path'])
params['General']['start'] = params['General']['end']
params['General']['end'] = datetime.datetime.now().strftime(r"%Y-%m-%dT%H:%M:%SZ")
with open(params_file, "w") as f:
    params.write(f)

l1_path = env['DIAS']['l1_path'].format(params['General']['sensor'])

l2_path = "/prj/DIAS/datalakes"

do_hindcast(env, params, l1_path, l2_path, 1, 1, 1)
