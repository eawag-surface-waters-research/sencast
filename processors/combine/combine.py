#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Combine allows the user to combine multiple products into a single product.
Adapter authors: James Runnalls
"""

import os
from netCDF4 import Dataset
from utils.auxil import log
from utils.product_fun import copy_nc, get_name_width_height_from_nc, get_bounds_from_nc

# key of the params section for this adapter
PARAMS_SECTION = 'COMBINE'
# The name of the folder to which the output product will be saved
OUT_DIR = 'L2COMBINE'
# A pattern for the name of the file to which the output product will be saved (completed with product name)
OUT_FILENAME = 'L2COMBINE_{}'


def process(env, params, l1product_path, l2product_files, out_path):
    """
    Combine processor
    1. Combines products into a single product for further processing

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
        Root output path; combined product is written to out_path/COMBINE/
    """
    if not params.has_section(PARAMS_SECTION):
        raise RuntimeWarning('Combine was not configured in parameters.')

    combine_params = dict(params[PARAMS_SECTION])
    valid_pixel_expression = combine_params.pop('validexpression', None)

    # Build list of (processor_name, file_path, [band_names]) to include
    sources = []
    for processor_key, bands_str in combine_params.items():
        matched_processor = next((p for p in l2product_files if p.lower() == processor_key.lower()), None)
        if matched_processor is None:
            raise RuntimeWarning('Processor {} listed in COMBINE section but not found in l2product_files.'.format(processor_key))
        if not os.path.exists(l2product_files[matched_processor]):
            raise RuntimeWarning('Product file for {} not found: {}'.format(matched_processor, l2product_files[matched_processor]))
        band_names = bands_str.strip() if bands_str.strip().upper() == 'ALL' else [b.strip() for b in bands_str.split(',') if b.strip()]
        sources.append((matched_processor, l2product_files[matched_processor], band_names))

    if not sources:
        raise RuntimeWarning('No source processors defined in COMBINE section.')

    # Derive output path from out_path and the first source product name
    ref_processor, ref_path, _ = sources[0]
    product_name = os.path.basename(ref_path)
    product_dir = os.path.join(out_path, OUT_DIR)
    output_file = os.path.join(product_dir, OUT_FILENAME.format(product_name))

    if os.path.isfile(output_file):
        if "overwrite" in params["General"].keys() and params['General']['overwrite'] == "true":
            log(env["General"]["log"], "Removing file: ${}".format(output_file), indent=1)
            os.remove(output_file)
        else:
            log(env["General"]["log"], "Skipping COMBINE, target already exists: {}".format(os.path.basename(output_file)), indent=1)
            return output_file
    os.makedirs(product_dir, exist_ok=True)

    # Validate all sources have the same shape and geographic coverage
    log(env["General"]["log"], "Validating source products.", indent=1)
    ref_width, ref_height, ref_bounds = None, None, None
    for proc, path, bands in sources:
        with Dataset(path) as src:
            _, width, height = get_name_width_height_from_nc(src, path)
            lat_var = 'lat' if 'lat' in src.variables else 'latitude'
            lon_var = 'lon' if 'lon' in src.variables else 'longitude'
            bounds = get_bounds_from_nc(src, lat_var_name=lat_var, lon_var_name=lon_var)
            if ref_width is None:
                ref_width, ref_height, ref_bounds = width, height, bounds
            else:
                if width != ref_width or height != ref_height:
                    raise RuntimeWarning(
                        'Product {} has shape {}x{} but reference product {} has shape {}x{}. '
                        'All combined products must have the same shape.'.format(
                            proc, width, height, ref_processor, ref_width, ref_height))
                tol = 1e-3
                for key in ('lat_min', 'lat_max', 'lon_min', 'lon_max'):
                    if abs(float(bounds[key]) - float(ref_bounds[key])) > tol:
                        raise RuntimeWarning(
                            'Product {} has different geographic coverage than {} '
                            '({}: {} vs {}).'.format(proc, ref_processor, key, bounds[key], ref_bounds[key]))
    log(env["General"]["log"], "All source products validated: shape {}x{}.".format(ref_width, ref_height), indent=1)

    # Create the combined output file
    log(env["General"]["log"], "Creating combined output: {}".format(os.path.basename(output_file)), indent=1)
    with Dataset(ref_path) as ref_src, Dataset(output_file, mode='w') as dst:
        # Copy dimensions and coordinate variables (crs, lat, lon) from the reference source
        copy_nc(ref_src, dst, [])

        for proc, path, bands in sources:
            log(env["General"]["log"], "Copying bands {} from {}.".format(bands, proc), indent=2)
            with Dataset(path) as src:
                available = {src.variables[v].orig_name if hasattr(src.variables[v], 'orig_name') else v: v
                             for v in src.variables if len(src.variables[v].shape) == 2}
                bands_to_copy = list(available.keys()) if bands == 'ALL' else bands
                for band in bands_to_copy:
                    if band not in available:
                        raise RuntimeWarning('Band {} not found in {} (available: {}).'.format(
                            band, proc, list(available.keys())))
                    var_name = available[band]
                    src_var = src.variables[var_name]
                    b = dst.createVariable(var_name, src_var.datatype, src_var.dimensions, compression='zlib', complevel=6)
                    attrs = {k: v for k, v in src_var.__dict__.items() if k != 'valid_pixel_expression'}
                    b.setncatts(attrs)
                    if valid_pixel_expression:
                        b.valid_pixel_expression = valid_pixel_expression
                    b[:] = src_var[:]

    return output_file
