#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""iCOR processor for athmospheric correction"""

import os
import subprocess

from constants import REPROD_DIR
from utils.product_fun import get_main_file_from_product_path
from utils.auxil import log

# Key of the params section for this processor
PARAMS_SECTION = "ICOR"
# The name of the folder to which the output product will be saved
OUT_DIR = "ICOR"
# A pattern for the name of the file to which the output product will be saved (completed with product name)
OUT_FILENAME = "icor_{}.nc"


def process(env, params, l1product_path, _, out_path):
    """This processor applies iCor to the source product and writes the result to disk. It returns the location of the output product."""

    # read env and params
    icor, product_name = env[PARAMS_SECTION]['icor_path'], os.path.basename(l1product_path)
    sensor, resolution, wkt = params['General']['sensor'], params['General']['resolution'], params['General']['wkt']
    use_product_water_mask = params[PARAMS_SECTION]['useProductWaterMask'] if 'useProductWaterMask' in params[PARAMS_SECTION] else "false"
    use_inland_water_mask = params[PARAMS_SECTION]['useInlandWaterMask'] if 'useInlandWaterMask' in params[PARAMS_SECTION] else "false"
    apply_simec_correction = params[PARAMS_SECTION]['applySimecCorrection'] if 'applySimecCorrection' in params[PARAMS_SECTION] else "false"
    glint = params[PARAMS_SECTION]['glintCorrectionPostProcessing'] if 'glintCorrectionPostProcessing' in params[PARAMS_SECTION] else "false"

    # check output path
    output_file = os.path.join(out_path, OUT_DIR, OUT_FILENAME.format(product_name))
    if os.path.isfile(output_file):
        if "overwrite" in params["General"].keys() and params['General']['overwrite'] == "true":
            log(env["General"]["log"], "Removing file: ${}".format(output_file))
            os.remove(output_file)
        else:
            log(env["General"]["log"], "Skipping ICOR, target already exists: {}".format(os.path.basename(output_file)))
            return output_file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # prepare call
    if sensor == "MSI":
        args = create_args_msi(icor, glint, apply_simec_correction, os.path.dirname(output_file), output_file, l1product_path)
    elif sensor == "OLCI":
        args = create_args_olci(icor, glint, apply_simec_correction, use_product_water_mask, use_inland_water_mask, os.path.dirname(output_file), output_file, l1product_path)
    elif sensor == "OLI_TIRS":
        args = create_args_oli_tirs(icor, glint, apply_simec_correction, os.path.dirname(output_file), output_file, l1product_path)
    else:
        raise RuntimeError("iCOR not implemented for sensor {}".format(sensor))

    # ensure reproducibility
    os.makedirs(os.path.join(out_path, OUT_DIR, REPROD_DIR), exist_ok=True)
    with open(os.path.join(out_path, OUT_DIR, REPROD_DIR, "cli_call.txt"), 'w') as f:
        f.write(" ".join(args))

    # execute call
    log(env["General"]["log"], "Calling '{}'".format(" ".join(args)))
    if subprocess.call(args):
        raise RuntimeError("Subprocess Failed.")
    return output_file


def create_args_msi(icor, glint, apply_simec_correction, working_folder, output_file, l1product_path):
    args = [icor]
    args.extend(["--sensor", "S2"])
    args.extend(["--generate_viewing_grids_s2", "false"])
    args.extend(["--glint_cor", glint])
    args.extend(["--keep_intermediate", "false"])
    args.extend(["--apply_gains", "false"])
    args.extend(["--cloud_average_threshold", "0.19"])
    args.extend(["--cloud_low_band", "B01"])
    args.extend(["--cloud_low_threshold", "0.25"])
    args.extend(["--cirrus", "true"])
    args.extend(["--aot", "true"])
    args.extend(["--aerosol_type", "RURAL"])
    args.extend(["--aot_window_size", "100"])
    args.extend(["--simec", apply_simec_correction])
    args.extend(["--watervapor", "true"])
    args.extend(["--bg_window", "1"])
    args.extend(["--cirrus_threshold", "0.01"])
    args.extend(["--aot_override", "0.1"])
    args.extend(["--ozone_override", "0.33"])
    args.extend(["--wv_override", "2.0"])
    args.extend(["--water_band", "B08"])
    args.extend(["--water_threshold", "0.05"])
    args.extend(["--working_folder", working_folder])
    args.extend(["--output_file", output_file])
    args.append(get_main_file_from_product_path(l1product_path))
    return args


def create_args_olci(icor, apply_simec_correction, glint, use_inland_water_mask, use_product_water_mask, working_folder, output_file, l1product_path):
    args = [icor]
    args.extend(["--keep_intermediate", "false"])
    args.extend(["--cloud_average_threshold", "0.23"])
    args.extend(["--cloud_low_band", "B02"])
    args.extend(["--cloud_low_threshold", "0.2"])
    args.extend(["--aot", "true"])
    args.extend(["--aerosol_type", "RURAL"])
    args.extend(["--aot_window_size", "100"])
    args.extend(["--simec", apply_simec_correction])
    args.extend(["--bg_window", "1"])
    args.extend(["--aot_override", "0.1"])
    args.extend(["--ozone", "true"])
    args.extend(["--aot_override", "0.1"])
    args.extend(["--ozone_override", "0.33"])
    args.extend(["--watervapor", "true"])
    args.extend(["--wv_override", "2.0"])
    args.extend(["--water_band", "B18"])
    args.extend(["--water_threshold", "0.06"])
    args.extend(["--output_file", output_file])
    args.extend(["--sensor", "S3"])
    args.extend(["--apply_gains", "false"])
    args.extend(["--glint_cor", glint])
    args.extend(["--inlandwater", use_inland_water_mask])
    args.extend(["--productwater", use_product_water_mask])
    args.extend(["--keep_land", "false"])
    args.extend(["--keep_water", "false"])
    args.extend(["--project", "false"])
    args.extend(["--working_folder", working_folder])
    args.append(get_main_file_from_product_path(l1product_path))
    return args


def create_args_oli_tirs(icor, glint, apply_simec_correction, working_folder, output_file, l1product_path):
    args = [icor]
    args.extend(["--keep_intermediate", "false"])
    args.extend(["--apply_gains", "false"])
    args.extend(["--glint_cor", glint])
    args.extend(["--cloud_average_threshold", "0.2"])
    args.extend(["--cloud_low_band", "B01"])
    args.extend(["--cloud_low_threshold", "0.15"])
    args.extend(["--cirrus", "true"])
    args.extend(["--aot", "true"])
    args.extend(["--aerosol_type", "RURAL"])
    args.extend(["--aot_override", "0.1"])
    args.extend(["--aot_window_size", "500"])
    args.extend(["--simec", apply_simec_correction])
    args.extend(["--watervapor", "true"])
    args.extend(["--wv_override", "2.0"])
    args.extend(["--bg_window", "1"])
    args.extend(["--cirrus_threshold", "0.005"])
    args.extend(["--ozone_override", "0.33"])
    args.extend(["--water_band", "B05"])
    args.extend(["--water_threshold", "0.05"])
    args.extend(["--sensor", "L8"])
    args.extend(["--working_folder", working_folder])
    args.extend(["--output_file", output_file])
    args.append(get_main_file_from_product_path(l1product_path))
    return args
