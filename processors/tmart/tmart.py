#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
T-Mart solves radiative transfer in a 3D surface-atmosphere system. This can be used in modelling and correcting
for the adjacency effect. Although initially designed for aquatic environments, T-Mart can also handle simple
terrestrial applications.
Adapter authors: James Runnalls
"""

import os
import tmart
import shutil
import sysconfig
import glob
import inspect
from utils.auxil import log


# key of the params section for this adapter
PARAMS_SECTION = 'TMART'


def _validate_msi_safe_input(l1product_path):
    """
    Validate that an MSI SAFE directory contains the minimum files required by T-Mart.
    """
    if not os.path.isdir(l1product_path):
        return

    if not os.path.basename(l1product_path).upper().endswith(".SAFE"):
        return

    metadata_path = os.path.join(l1product_path, "MTD_MSIL1C.xml")
    if not os.path.isfile(metadata_path):
        raise RuntimeError(
            "TMART input validation failed: missing MTD_MSIL1C.xml in {}".format(l1product_path)
        )

    granule_root = os.path.join(l1product_path, "GRANULE")
    granule_dirs = []
    if os.path.isdir(granule_root):
        granule_dirs = [
            os.path.join(granule_root, entry)
            for entry in os.listdir(granule_root)
            if os.path.isdir(os.path.join(granule_root, entry))
        ]
    if len(granule_dirs) == 0:
        raise RuntimeError(
            "TMART input validation failed: no GRANULE directory found in {}".format(l1product_path)
        )

    required_bands = ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B09", "B10", "B11", "B12"]
    missing_entries = []
    for granule_dir in granule_dirs:
        img_data_dir = os.path.join(granule_dir, "IMG_DATA")
        if not os.path.isdir(img_data_dir):
            missing_entries.append("{}::IMG_DATA".format(granule_dir))
            continue
        for band in required_bands:
            band_files = glob.glob(os.path.join(img_data_dir, "*_{}.jp2".format(band)))
            if len(band_files) == 0:
                missing_entries.append("{}::{}".format(img_data_dir, band))

    if len(missing_entries) > 0:
        raise RuntimeError(
            "TMART input validation failed: missing required SAFE content ({} entries missing). "
            "First missing entries: {}".format(
                len(missing_entries),
                ", ".join(missing_entries[:10]),
            )
        )


def _validate_landsat_input(l1product_path):
    """
    Validate that a Landsat 8/9 product directory contains the files TMART reads.
    """
    product_name = os.path.basename(l1product_path)
    if not product_name.startswith(("LC08", "LC09")):
        return

    if not os.path.isdir(l1product_path):
        raise RuntimeError(
            "TMART input validation failed: Landsat product must be a directory: {}".format(l1product_path)
        )

    required_suffixes = [
        "_MTL.txt",
        "_QA_PIXEL.TIF",
        "_B1.TIF",
        "_B2.TIF",
        "_B3.TIF",
        "_B4.TIF",
        "_B5.TIF",
        "_B6.TIF",
        "_B7.TIF",
        "_B9.TIF",
    ]
    missing_entries = []
    for suffix in required_suffixes:
        expected = os.path.join(l1product_path, "{}{}".format(product_name, suffix))
        if not os.path.isfile(expected):
            missing_entries.append(os.path.basename(expected))

    if len(missing_entries) > 0:
        raise RuntimeError(
            "TMART input validation failed: missing required Landsat content ({} entries missing). "
            "Missing entries: {}".format(
                len(missing_entries),
                ", ".join(missing_entries),
            )
        )


def _read_aot(value):
    if str(value).upper() == "MERRA2":
        return "MERRA2"
    return float(value)


def _remove_path(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.isfile(path):
        os.remove(path)


def _run_tmart_aec(aec_file, env, aot, n_photon, n_jobs, mask_swir_threshold):
    kwargs = {
        "overwrite": True,
        "AOT": aot,
        "n_photon": n_photon,
        "n_jobs": n_jobs,
    }
    if "mask_SWIR_threshold" in inspect.signature(tmart.AEC.run).parameters:
        kwargs["mask_SWIR_threshold"] = mask_swir_threshold
    tmart.AEC.run(aec_file, env["EARTHDATA"]["username"], env["EARTHDATA"]["password"], **kwargs)


def process(env, params, l1product_path, l2product_files, out_path):
    """
    T-Mart processor.
    1. Edits L1 MSI product to account for adjacency effects

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
    if not params.has_section(PARAMS_SECTION):
        raise RuntimeWarning('T-Mart was not configured in parameters.')

    aot = "MERRA2"
    n_photon = 100000
    n_jobs = 100
    mask_swir_threshold = None

    if "aot" in params[PARAMS_SECTION].keys(): aot = _read_aot(params[PARAMS_SECTION]["aot"])
    if "n_photon" in params[PARAMS_SECTION].keys(): n_photon = int(params[PARAMS_SECTION]["n_photon"])
    if "n_jobs" in params[PARAMS_SECTION].keys(): n_jobs = int(params[PARAMS_SECTION]["n_jobs"])
    if "mask_swir_threshold" in params[PARAMS_SECTION]: mask_swir_threshold = float(params[PARAMS_SECTION]["mask_swir_threshold"])

    aec_folder = os.path.join(os.path.dirname(l1product_path), "TMART")
    os.makedirs(aec_folder, exist_ok=True)
    aec_file = os.path.join(aec_folder, os.path.basename(l1product_path))

    if os.path.exists(aec_file):
        if (
            ("synchronise" in params["General"].keys() and params['General']['synchronise'] == "false")
            or ("overwrite" in params["General"].keys() and params['General']['overwrite'] == "true")
        ):
            log(env["General"]["log"], "Removing file: ${}".format(aec_file))
            _remove_path(aec_file)
        else:
            log(env["General"]["log"], 'Skipping T-Mart, target already exists: {}'.format(aec_file), indent=1)
            return [aec_file]

    site_packages_path = sysconfig.get_paths()["purelib"]
    config_path = os.path.join(site_packages_path, 'tmart/config/config.txt')
    config_backup_path = os.path.join(site_packages_path, 'tmart/config/config_backup.txt')

    if not os.path.isfile(config_backup_path):
        shutil.copy(config_path, config_backup_path)

    with open(config_backup_path, 'r') as file:
        lines = file.readlines()

    for i in range(len(lines)):
        if not lines[i].startswith("#") and len(lines[i].split("=")) == 2:
            key = lines[i].split("=")[0].strip()
            if key in params[PARAMS_SECTION].keys():
                lines[i] = "{} = {}\n".format(key, params[PARAMS_SECTION][key])

    with open(config_path, 'w') as file:
        file.writelines(lines)

    try:
        _validate_msi_safe_input(l1product_path)
        _validate_landsat_input(l1product_path)
        if os.path.isfile(l1product_path):
            shutil.copy(l1product_path, aec_file)
        elif os.path.isdir(l1product_path):
            shutil.copytree(l1product_path, aec_file)
        _run_tmart_aec(aec_file, env, aot, n_photon, n_jobs, mask_swir_threshold)
        shutil.copy(config_backup_path, config_path)
    except:
        shutil.copy(config_backup_path, config_path)
        if os.path.exists(aec_file):
            _remove_path(aec_file)
        raise
    return [aec_file]
