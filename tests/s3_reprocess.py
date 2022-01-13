#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Import libs, some of them might be unused here, but something magical happens when they are imported
# which causes geos_c.dll and objectify.pyx errors to disappear in windows.

import netCDF4
import cartopy.crs as ccrs
import sys
import os
import shutil
from utils.auxil import load_params, log

sys.path.append("/home/jamesrunnalls/eawagrs/sentinel-hindcast/build/sentinel-hindcast")
from main import hindcast


def date_from_folder(folder):
    return folder.split("_")[-1]


output_folders = "/media/jamesrunnalls/JamesSSD/Eawag/EawagRS/Sencast/build/DIAS/output_data"
param_file = "/home/jamesrunnalls/eawagrs/sentinel-hindcast/build/sentinel-hindcast/parameters/datalakes_sui_S3.ini"
logfile = "/home/jamesrunnalls/eawagrs/sentinel-hindcast/build/sentinel-hindcast/tests/s3_reprocess_log.txt"

folders = os.listdir(output_folders)
folders = [x for x in folders if "datalakes_sui_S3_sui" in x]
folders.sort()

for folder in folders:
    log(logfile, "RUNNING: {}".format(folder))
    try:
        try:
            os.remove(os.path.join(output_folders, folder, "datalakes_sui_S3.ini"))
        except:
            log(logfile, "WARNING: Could not find .ini file.")

        # Remove old Secchi, PP
        shutil.rmtree(os.path.join(output_folders, folder, "L2PP"), ignore_errors=True)
        shutil.rmtree(os.path.join(output_folders, folder, "L2QAA"), ignore_errors=True)

        # Parse date from folder name
        date = date_from_folder(folder)

        # Update parameter file with date
        params, params_file = load_params(param_file)
        finalStart = "{}T00:00:00.000Z".format(date)
        finalEnd = "{}T23:59:59.999Z".format(date)
        params['General']['start'] = finalStart
        params['General']['end'] = finalEnd
        with open(params_file, "w") as f:
            params.write(f)

        # Re-run hindcast
        hindcast(params_file, max_parallel_downloads=1, max_parallel_processors=1, max_parallel_adapters=1)
        log(logfile, "COMPLETE: Completed processing for: {}".format(folder))
    except:
        log(logfile, "FAILED: Unable to complete processing for: {}".format(folder))
    break

