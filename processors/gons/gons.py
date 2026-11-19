#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""The GONS adapter calculates Chlorophyll A from Polymer output using the semi-analytical red / red-edge
band ratio algorithm of Gons et al. (2005).

    bb   = 1.61 * Rw_nir / (0.082 - 0.6 * Rw_nir)
    achl = (Rw_rededge / Rw_red) * (aw_rededge + bb) - aw_red - bb^p
    chla = achl / a*chl

Gons, H.J., Rijkeboer, M., Ruddick, K.G., 2005. Effect of a waveband shift on chlorophyll retrieval from MERIS imagery
    of inland and coastal waters. Journal of Plankton Research 27, 125-127.
Warren, M.A., Simis, S.G.H., Selmes, N., 2021. Complementary water quality observations from high and medium
    resolution Sentinel sensors by aligning chlorophyll-a and turbidity algorithms. Remote Sensing of Environment 265,
    112651.
Quinten, V., Ruddick, K., Vanhellemont, Q., 2016. Sentinel-2A/MSI and Landsat-8/OLI for high resolution water quality
    monitoring. Ocean Optics XXIII.
"""

import os
import numpy as np
from netCDF4 import Dataset
from utils.auxil import log
from utils.product_fun import copy_nc, get_band_names_from_nc, get_name_width_height_from_nc, \
    get_satellite_name_from_product_name, get_valid_pe_from_nc, write_pixels_to_nc, create_band, read_pixels_from_nc


# key of the params section for this adapter
PARAMS_SECTION = "GONS"
# The name of the folder to which the output product will be saved
OUT_DIR = 'L2GONS'
# A pattern for the name of the file to which the output product will be saved (completed with product name)
OUT_FILENAME = 'L2GONS_{}'

# Pure water absorption (m-1) at the red-edge (~708 nm) and red (~665 nm) bands as used by Gons et al. (2005)
AW_REDEDGE = 0.70
AW_RED = 0.40

# Per-sensor configuration: Polymer bands (red, red-edge, NIR) and default coefficients (p, a*chl)
SENSOR_CONFIG = {
    # Original Gons et al. (2005) coefficients for MERIS-like bands
    "OLCI": {"red": "Rw665", "rededge": "Rw709", "nir": "Rw779", "p": 1.06, "astar": 0.016},
    # MSI coefficients tuned against OLCI: Warren et al. (2021), Table 8
    "MSI": {"red": "Rw665", "rededge": "Rw705", "nir": "Rw783", "p": 1.0624, "astar": 0.0192},
}


def process(env, params, l1product_path, l2product_files, out_path):
    """Apply GONS adapter.
        1. Uses the Gons et al. (2005) red-edge algorithm to output CHL-A

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
        raise RuntimeWarning("GONS was not configured in parameters.")

    if "processor" not in params[PARAMS_SECTION]:
        raise RuntimeWarning("GONS processor must be defined in the parameter file.")

    processor = params[PARAMS_SECTION]["processor"]
    if processor != "POLYMER" and not (processor == "COMBINE" and "polymer" in params["COMBINE"]):
        raise RuntimeWarning("GONS adapter only works with Polymer processor output")

    # Check for precursor datasets
    if processor not in l2product_files or not os.path.exists(l2product_files[processor]):
        raise RuntimeWarning("POLYMER precursor file not found ensure POLYMER is run before this adapter.")

    # Create folder for file
    product_path = l2product_files[processor]
    product_name = os.path.basename(product_path)
    product_dir = os.path.join(os.path.dirname(os.path.dirname(product_path)), OUT_DIR)
    output_file = os.path.join(product_dir, OUT_FILENAME.format(product_name))
    if os.path.isfile(output_file):
        if "overwrite" in params["General"].keys() and params['General']['overwrite'] == "true":
            log(env["General"]["log"], "Removing file: ${}".format(output_file), indent=1)
            os.remove(output_file)
        else:
            log(env["General"]["log"], "Skipping GONS, target already exists: {}".format(OUT_FILENAME.format(product_name)), indent=1)
            return output_file
    os.makedirs(product_dir, exist_ok=True)

    satellite = get_satellite_name_from_product_name(product_name)
    if satellite in ["S2A", "S2B", "S2C"]:
        sensor = "MSI"
    elif satellite in ["S3A", "S3B"]:
        sensor = "OLCI"
    else:
        raise RuntimeError("GONS adapter not implemented for satellite {}".format(satellite))
    config = SENSOR_CONFIG[sensor]
    p = float(params[PARAMS_SECTION].get("p", config["p"]))
    astar = float(params[PARAMS_SECTION].get("astar", config["astar"]))

    log(env["General"]["log"], "Reading POLYMER output from {}".format(product_path), indent=1)
    with Dataset(product_path) as src, Dataset(output_file, mode='w') as dst:
        name, width, height = get_name_width_height_from_nc(src, product_path)
        product_band_names = get_band_names_from_nc(src)

        log(env["General"]["log"], "Product:      {}".format(name), indent=1)
        log(env["General"]["log"], "Raster size: {} x {} pixels".format(width, height), indent=1)
        log(env["General"]["log"], "Bands:       {}".format(list(product_band_names)), indent=1)
        log(env["General"]["log"], "Sensor: {}, p: {}, a*chl: {}".format(sensor, p, astar), indent=1)

        log(env["General"]["log"], "Copying relevant bands from source product.", indent=2)
        valid_pixel_expression = get_valid_pe_from_nc(src)
        gons_valid_pixel_expression = params[PARAMS_SECTION].get("validexpression", "").strip()
        if gons_valid_pixel_expression:
            if valid_pixel_expression:
                valid_pixel_expression = "({}) and ({})".format(valid_pixel_expression, gons_valid_pixel_expression)
            else:
                valid_pixel_expression = gons_valid_pixel_expression
        inclusions = [band for band in product_band_names if valid_pixel_expression and band in valid_pixel_expression]
        copy_nc(src, dst, inclusions)

        log(env["General"]["log"], "Creating new bands.", indent=2)
        create_band(dst, "chla", "mg/m3", valid_pixel_expression)
        create_band(dst, "achl", "m-1", valid_pixel_expression)
        create_band(dst, "bb", "m-1", valid_pixel_expression)

        log(env["General"]["log"], "Reading input RW data.", indent=2)
        red, rededge, nir = [read_pixels_from_nc(src, config[b], 0, 0, width, height, np.zeros(width * height))
                             for b in ("red", "rededge", "nir")]

        log(env["General"]["log"], "Computing ChlA", indent=2)
        chla, achl, bb = gons(red, rededge, nir, p, astar)
        write_pixels_to_nc(dst, "chla", 0, 0, width, height, chla)
        write_pixels_to_nc(dst, "achl", 0, 0, width, height, achl)
        write_pixels_to_nc(dst, "bb", 0, 0, width, height, bb)

    return output_file


def gons(red, rededge, nir, p, astar):
    """Gons et al. (2005) chlorophyll-a from water reflectance (Polymer Rw) at the red, red-edge and NIR bands.

    Returns chla (mg m-3), achl (m-1) and bb (m-1). No masking is applied; negative and invalid values are left as
    computed and should be handled with the validexpression.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        bb = 1.61 * nir / (0.082 - 0.6 * nir)
        achl = (rededge / red) * (AW_REDEDGE + bb) - AW_RED - np.power(bb, p)
        chla = achl / astar
    return chla, achl, bb
