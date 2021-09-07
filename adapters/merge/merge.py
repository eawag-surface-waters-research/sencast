#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""The Merge adapter combines multiple L2 products into a single file with multiple bands.

The merge is only valid for files with identical geospatial information, it is not for merging geospatially distinct
regions.
"""

import os
from snappy import ProductIO, HashMap, GPF

# key of the params section for this adapter
PARAMS_SECTION = "MERGE"

# the file name pattern for output file
FILENAME = "L2MERGE_{}"
FILEFOLDER = "L2MERGE"


# TODO: this should be to util and be called from the processors!
def apply(env, params, l2product_files,date):
    """Apply merge adapter.
                1. Uses snappy to merge multiple L2 files

                Parameters
                -------------

                params
                    Dictionary of parameters, loaded from input file
                env
                    Dictionary of environment parameters, loaded from input file
                l2product_files
                    Dictionary of Level 2 product files created by processors
                date
                    Run date
                """
    if not params.has_section(PARAMS_SECTION):
        raise RuntimeWarning("Merge was not configured in parameters.")
    print("Applying Merge...")

    if "merge_nc" not in params[PARAMS_SECTION]:
        raise RuntimeWarning("Merge files must be defined in the parameter file under the merge_nc key.")

    merge_params = list(filter(None, params[PARAMS_SECTION]["merge_nc"].split(",")))

    # Create folder for file
    product_path = l2product_files[merge_params[0]]
    product_name = os.path.basename(product_path)
    product_dir = os.path.join(os.path.dirname(os.path.dirname(product_path)), FILEFOLDER)
    output_file = os.path.join(product_dir, FILENAME.format(product_name))
    l2product_files["MERGE"] = output_file
    if os.path.isfile(output_file):
        if "synchronise" in params["General"].keys() and params['General']['synchronise'] == "false":
            print("Removing file: ${}".format(output_file))
            os.remove(output_file)
        else:
            print("Skipping Merge, target already exists: {}".format(FILENAME.format(product_name)))
            return output_file
    os.makedirs(product_dir, exist_ok=True)

    products = HashMap()
    parameters = HashMap()
    products.put('masterProduct', ProductIO.readProduct(l2product_files[merge_params[0]]))
    for i in range(1, len(merge_params)):
        products.put('slaveProduct', ProductIO.readProduct(l2product_files[merge_params[i]]))
    target = GPF.createProduct("Merge", parameters, products)
    ProductIO.writeProduct(target, output_file, "NetCDF4-CF")
