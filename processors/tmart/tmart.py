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
from utils.auxil import log


# key of the params section for this adapter
PARAMS_SECTION = 'TMART'


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

    aot = 0.05
    n_photon = 100000
    n_jobs = 1

    if "aot" in params[PARAMS_SECTION].keys(): aot = float(params[PARAMS_SECTION]["aot"])
    if "n_photon" in params[PARAMS_SECTION].keys(): n_photon = int(params[PARAMS_SECTION]["n_photon"])
    if "n_jobs" in params[PARAMS_SECTION].keys(): n_jobs = int(params[PARAMS_SECTION]["n_jobs"])

    aec_folder = os.path.join(os.path.dirname(l1product_path), "AEC")
    os.makedirs(aec_folder, exist_ok=True)
    aec_file = os.path.join(aec_folder, os.path.basename(l1product_path))

    if os.path.exists(aec_file):
        if "synchronise" in params["General"].keys() and params['General']['synchronise'] == "false":
            log(env["General"]["log"], "Removing file: ${}".format(aec_file))
            shutil.rmtree(aec_file)
        else:
            log(env["General"]["log"], 'Skipping T-Mart, target already exists: {}'.format(aec_file), indent=1)
            return [aec_file]

    try:
        if os.path.isfile(l1product_path):
            shutil.copy(l1product_path, aec_file)
        elif os.path.isdir(l1product_path):
            shutil.copytree(l1product_path, aec_file)
        tmart.AEC.run(aec_file, env["EARTHDATA"]["username"], env["EARTHDATA"]["password"], overwrite=True, AOT=aot, n_photon=n_photon, n_jobs=n_jobs)
    except:
        if os.path.exists(aec_file):
            shutil.rmtree(aec_file)
        raise
    return [aec_file]
