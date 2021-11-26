#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Import libs, some of them might be unused here, but something magical happens when they are imported
# which causes geos_c.dll and objectify.pyx errors to disappear in windows.

import netCDF4
import cartopy.crs as ccrs
import sys
import os
import shutil
from utils.auxil import load_params
sys.path.append("/home/jamesrunnalls/eawagrs/sentinel-hindcast/build/sentinel-hindcast")
from main import hindcast


def date_from_folder(folder):
    return folder.split("_")[-1]


output_folders = "/media/jamesrunnalls/JamesSSD/Eawag/EawagRS/Sencast/build/DIAS/output_data"
param_file = "/home/jamesrunnalls/eawagrs/sentinel-hindcast/build/sentinel-hindcast/parameters/datalakes_sui_S3.ini"
for folder in os.listdir(output_folders):
    if "datalakes_sui_S3_sui" in folder:
        print(folder)
        # Remove .ini file
        try:
            os.remove(os.path.join(output_folders, folder, "datalakes_sui_S3.ini"))
        except:
            print("File not found.")

        # Remove old Secchi, PP
        shutil.rmtree(os.path.join(output_folders, folder, "L2PP"), ignore_errors=True)
        shutil.rmtree(os.path.join(output_folders, folder, "L2QAA"), ignore_errors=True)

        # Rename Polymer folder
        os.rename(os.path.join(output_folders, folder, "L2POLY"), os.path.join(output_folders, folder, "ss_L2POLY"))

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
        break
