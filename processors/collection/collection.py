#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Adapter authors: Daniel Odermatt, James Runnalls
"""

import os
import json
import shutil
import numpy as np
from netCDF4 import Dataset
from utils.auxil import log, gpt_subprocess


# key of the params section for this adapter
PARAMS_SECTION = 'COLLECTION'
# The name of the folder to which the output product will be saved
OUT_DIR = 'L2C'
# A pattern for the name of the file to which the output product will be saved (completed with product name)
OUT_FILENAME = 'L2C_{}.nc'
# Default number of attempts for the GPT
DEFAULT_ATTEMPTS = 1
# Default timeout for the GPT (doesn't apply to last attempt) in seconds
DEFAULT_TIMEOUT = False

def process(env, params, l1product_path, l2product_files, out_path):
    """
    Landsat collection2 processor.
    1. Converts TIFF band files to NetCDF
    2. Calculates parameters such as temperature
    3. Applies cloud and land masking

    Parameters
    -------------

    env
        Dictionary of environment parameters, loaded from input file
    params
        Dictionary of parameters, loaded from input file
    l1product_path
        unused
    l2product_files
        Dictionary of Level 2 product files created by processors
    out_path
        unused
    """
    gpt = env['General']['gpt_path']
    output_file = os.path.join(out_path, OUT_DIR, OUT_FILENAME.format(os.path.basename(l1product_path)))

    if os.path.exists(output_file):
        log(env["General"]["log"], "Collection file exists, skipping...", indent=2)
        return output_file

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    if params["General"]['sensor'] == "landsat_ot_c2_l2":

        water_only = False
        if PARAMS_SECTION in params and "water_only" in params[PARAMS_SECTION]:
            water_only = params[PARAMS_SECTION]["water_only"] == "true"

        st_file = os.path.join(l1product_path, os.path.basename(l1product_path) + "_ST_B10.TIF")
        st_file_temp = os.path.join(out_path, OUT_DIR, "_reproducibility", os.path.basename(l1product_path) + "_ST_B10_reprojected.nc")
        qa_file = os.path.join(l1product_path, os.path.basename(l1product_path) + "_QA_PIXEL.TIF")
        qa_file_temp = os.path.join(out_path, OUT_DIR, "_reproducibility", os.path.basename(l1product_path) + "_QA_PIXEL_reprojected.nc")

        if PARAMS_SECTION in params and "attempts" in params[PARAMS_SECTION]:
            attempts = int(params[PARAMS_SECTION]["attempts"])
        else:
            attempts = DEFAULT_ATTEMPTS

        if PARAMS_SECTION in params and "timeout" in params[PARAMS_SECTION]:
            timeout = int(params[PARAMS_SECTION]["timeout"])
        else:
            timeout = DEFAULT_TIMEOUT

        gpt_xml_file = os.path.join(out_path, OUT_DIR, "_reproducibility", "collection.xml")
        os.makedirs(os.path.dirname(gpt_xml_file), exist_ok=True)
        shutil.copy(os.path.join(os.path.dirname(__file__), "collection.xml"), gpt_xml_file)

        log(env["General"]["log"], "Reprojecting {}".format(os.path.basename(st_file)), indent=2)
        if os.path.exists(st_file_temp):

            os.remove(st_file_temp)
        args = [gpt, gpt_xml_file, "-c", env['General']['gpt_cache_size'], "-e",
                "-SsourceFile={}".format(st_file),
                "-PoutputFile={}".format(st_file_temp)]
        gpt_subprocess(args, env["General"]["log"], attempts=attempts, timeout=timeout, indent=3)

        log(env["General"]["log"], "Reprojecting {}".format(os.path.basename(qa_file)), indent=2)
        if os.path.exists(qa_file_temp):
            os.remove(qa_file_temp)
        args = [gpt, gpt_xml_file, "-c", env['General']['gpt_cache_size'], "-e",
                "-SsourceFile={}".format(qa_file),
                "-PoutputFile={}".format(qa_file_temp)]
        gpt_subprocess(args, env["General"]["log"], attempts=attempts, timeout=timeout, indent=3)

        log(env["General"]["log"], "Combining reprojected components", indent=2)

        nc_st = Dataset(st_file_temp, 'r')
        nc_qa = Dataset(qa_file_temp, 'r')

        log(env["General"]["log"], "Reading metadata", indent=3)
        image_metadata = {}
        if os.path.isfile(os.path.join(l1product_path, os.path.basename(l1product_path) + "_MTL.json")):
            with open(os.path.join(l1product_path, os.path.basename(l1product_path) + "_MTL.json"), 'r') as file:
                metadata = json.load(file)
                image_metadata = metadata["LANDSAT_METADATA_FILE"]["IMAGE_ATTRIBUTES"]
        elif os.path.isfile(os.path.join(l1product_path, os.path.basename(l1product_path) + "_MTL.txt")):
            with open(os.path.join(l1product_path, os.path.basename(l1product_path) + "_MTL.txt"), 'r') as file:
                add = False
                lines = [line.strip() for line in file]
                for line in lines:
                    if line == "GROUP = IMAGE_ATTRIBUTES":
                        add = True
                    elif line == "END_GROUP = IMAGE_ATTRIBUTES":
                        add = False
                    elif add:
                        parts = line.split("=")
                        image_metadata[parts[0].strip()] = parts[1].strip().replace('"', '')
        else:
            log(env["General"]["log"], "Unable to find metadata file", indent=4)

        log(env["General"]["log"], "Combining ST and QA files and calculating parameters", indent=3)
        with Dataset(output_file, 'w') as nc:
            for key in image_metadata.keys():
                setattr(nc, key, image_metadata[key])

            for dim_name, dim in nc_st.dimensions.items():
                nc.createDimension(dim_name, (len(dim) if not dim.isunlimited() else None))

            for var in ["lat", "lon"]:
                dst_var = nc.createVariable(var, nc_st[var].datatype, nc_st[var].dimensions)
                dst_var.setncatts({k: nc_st[var].getncattr(k) for k in nc_st[var].ncattrs()})
                dst_var[:] = nc_st[var][:]

            chunk_size = (256, 256)  # Adjust chunk size based on available memory and file size

            data_var = nc.createVariable(
                'ST',
                np.float32,
                ('lat', 'lon'),
                chunksizes=chunk_size,
                zlib=True,
                fill_value=np.nan
            )
            data_var.units = "degC"
            data_var.long_name = "Skin Temperature"
            data_var.valid_pixel_expression = "cloud<1"

            cloud_var = nc.createVariable(
                'cloud',
                np.float32,
                ('lat', 'lon'),
                chunksizes=chunk_size,
                zlib=True
            )
            cloud_var.units = ""
            cloud_var.long_name = "0 - Cloud, 1 - No cloud"

            water_var = nc.createVariable(
                'water',
                np.float32,
                ('lat', 'lon'),
                chunksizes=chunk_size,
                zlib=True
            )
            water_var.units = ""
            water_var.long_name = "0 - Cloud or land, 1 - Water"

            block_size = 256  # Adjust block size to match the chunk size or your memory limits
            data_shape = nc_st["band_1"].shape

            for i in range(0, data_shape[0], block_size):
                for j in range(0, data_shape[1], block_size):
                    # Calculate the block width and height dynamically for edge cases
                    block_width = min(block_size, data_shape[1] - j)
                    block_height = min(block_size, data_shape[0] - i)

                    # Read data in blocks from the TIFF file
                    data_chunk = np.array(nc_st["band_1"][i:i + block_height, j:j + block_width], dtype=float)
                    qa_chunk = np.array(nc_qa["band_1"][i:i + block_height, j:j + block_width], dtype=int)

                    tile_mask = data_chunk == 0

                    # Process chunks
                    cloud_chunk = (qa_chunk >> 6) & 1
                    cloud_chunk = np.abs(cloud_chunk - 1)
                    water_chunk = (qa_chunk >> 7) & 1

                    data_chunk[tile_mask] = np.nan
                    data_chunk = np.array(data_chunk) * 0.00341802 - 124.15
                    if water_only:
                        data_chunk[water_chunk == 0] = np.nan

                    # Write the chunk to the NetCDF file
                    data_var[i:i + block_height, j:j + block_width] = data_chunk
                    cloud_var[i:i + block_height, j:j + block_width] = cloud_chunk
                    water_var[i:i + block_height, j:j + block_width] = water_chunk

        log(env["General"]["log"], "Removing temporary reprojected files", indent=2)
        os.remove(st_file_temp)
        os.remove(qa_file_temp)
    else:
        raise ValueError("Collection not implemented for {}".format(params["General"]['sensor']))
    return output_file
