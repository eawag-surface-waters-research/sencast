#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""The core functions of Sencast

.. note::
    Download API's, processors, and adapters are imported dynamically to make Sencast also work on systems,
    where some of them might not be available.
"""

import os
import time
import traceback
import sys

from requests.auth import HTTPBasicAuth
from snappy import ProductIO
from threading import Semaphore, Thread

from auxil import get_l1product_path, get_sensing_date_from_product_name, get_satellite_name_from_product_name, init_hindcast, copy_metadata
from externalapis.earthdata_api import authenticate
from product_fun import minimal_subset_of_products, filter_for_timeliness


def hindcast(params_file, env_file=None, max_parallel_downloads=1, max_parallel_processors=1, max_parallel_adapters=1):
    """Main function for running Sencast. First initialises the sencast and then processes input parameters.

    Parameters
    -------------

    params_file
        Parameters read from the .ini input file
    env_file
        | **Default: None**
        | Environment settings read from the environment .ini file, if None provided Sencast will search for file in
        environments folder.
    max_parallel_downloads
        | **Default: 1**
        | Maximum number of parallel downloads of satellite images
    max_parallel_processors
        | **Default: 1**
        | Maximum number of processors to run in parallel
    max_parallel_adapters
        | **Default: 1**
        | Maximum number of adapters to run in parallel
    """

    env, params, l2_path = init_hindcast(env_file, params_file)
    do_hindcast(env, params, l2_path, max_parallel_downloads, max_parallel_processors, max_parallel_adapters)


def do_hindcast(env, params, l2_path, max_parallel_downloads=1, max_parallel_processors=1,
                max_parallel_adapters=1):
    """Threading function for running Sentinel Hindcast.
        1. Calls API to find available data for given query
        2. Splits the processing into threads based on date and satellite
        3. Runs the sencast for each thread

        Parameters
        -------------

        params
            Dictionary of parameters, loaded from input file
        env
            Dictionary of environment parameters, loaded from input file
        l2_path
            The output folder in which to save the output files
        max_parallel_downloads
            | **Default: 1**
            | Maximum number of parallel downloads of satellite images
        max_parallel_processors
            | **Default: 1**
            | Maximum number of processors to run in parallel
        max_parallel_adapters
            | **Default: 1**
            | Maximum number of adapters to run in parallel
        """
    # decide which API to use
    if env['General']['remote_dias_api'] == "COAH":
        from externalapis.coah_api import get_download_requests, do_download
        auth = HTTPBasicAuth(env['COAH']['username'], env['COAH']['password'])
    elif env['General']['remote_dias_api'] == "HDA":
        from externalapis.hda_api import get_download_requests, do_download
        auth = HTTPBasicAuth(env['HDA']['username'], env['HDA']['password'])
    elif env['General']['remote_dias_api'] == "CREODIAS":
        from externalapis.creodias_api import get_download_requests, do_download
        auth = [env['CREODIAS']['username'], env['CREODIAS']['password']]
    else:
        raise RuntimeError("Unknown DIAS API: {} (possible options are 'HDA', 'CREODIAS' or 'COAH').".format(env['General']['API']))

    # find products which match the criterias from params
    start, end = params['General']['start'], params['General']['end']
    sensor, resolution, wkt = params['General']['sensor'], params['General']['resolution'], params['General']['wkt']
    download_requests, product_names = get_download_requests(auth, start, end, sensor, resolution, wkt)

    # filter for timeliness
    download_requests, product_names = filter_for_timeliness(download_requests, product_names)

    # set up inputs for product hindcast
    l1product_paths = [get_l1product_path(env, product_name) for product_name in product_names]
    semaphores = {
        'download': Semaphore(max_parallel_downloads),
        'process': Semaphore(max_parallel_processors),
        'adapt': Semaphore(max_parallel_adapters)
    }

    # if running on creodias server
    server = False
    if "server" in env['General'] and env['General']['server'] is not False:
        server = env['General']['server']

    # for readonly local dias, remove unavailable products and their download_requests
    if env['DIAS']['readonly'] == "readonly":
        print("{} products have been found.".format(len(l1product_paths)))
        for i in range(len(l1product_paths)):
            if not os.path.exists(l1product_paths[i]):
                download_requests[i], l1product_paths[i] = None, None
        l1product_paths = list(filter(None, l1product_paths))
        download_requests = list(filter(None, download_requests))
        print("{} products are avaiable and will be processed.".format(len(l1product_paths)))
    else:
        actual_downloads = len([0 for l1product_path in l1product_paths if not os.path.exists(l1product_path)])
        print("{} products are already locally available.".format(len(l1product_paths) - actual_downloads))
        print("{} products must be downloaded first.".format(actual_downloads))

    # group download requests and product paths by date and sort them by group size and sensing date
    download_groups, l1product_path_groups = {}, {}
    for download_request, l1product_path in zip(download_requests, l1product_paths):
        date = get_sensing_date_from_product_name(os.path.basename(l1product_path))
        satellite = get_satellite_name_from_product_name(os.path.basename(l1product_path))
        group = date + "_" + satellite
        if group not in download_groups.keys():
            download_groups[group], l1product_path_groups[group] = [], []
        download_groups[group].append(download_request)
        l1product_path_groups[group].append(l1product_path)

    # print information about grouped products
    print("The products have been grouped into {} group(s).".format(len(l1product_path_groups)))
    print("Each group is handled by an individual thread.")

    # authenticate for earth data api
    authenticate(env['EARTHDATA']['username'], env['EARTHDATA']['password'])

    # do hindcast for every product group
    hindcast_threads = []
    for group, _ in sorted(sorted(download_groups.items()), key=lambda item: len(item[1])):
        args = (env, params, do_download, auth, download_groups[group], l1product_path_groups[group], l2_path, semaphores, group, server)
        hindcast_threads.append(Thread(target=hindcast_product_group, args=args))
        hindcast_threads[-1].start()

    # wait for all hindcast threads to terminate
    starttime = time.time()
    for hindcast_thread in hindcast_threads:
        hindcast_thread.join()
    print("Hindcast complete in {0:.1f} seconds.".format(time.time() - starttime))


def hindcast_product_group(env, params, do_download, auth, download_requests, l1product_paths, l2_path, semaphores, group, server):
    """Run sencast for given thread.
        1. Downloads required products
        2. Runs processors
        3. Runs mosaic
        4. Runs adapters

        Parameters
        -------------

        params
            Dictionary of parameters, loaded from input file
        env
            Dictionary of environment parameters, loaded from input file
        do_download
            Download function from the selected API
            The output folder in which to save the output files
        auth
            Auth details for the selected API
        download_requests
            Array of uuid's of sentinel products
        l1product_paths
            Array of l1 product paths
        l2_path
            The output folder in which to save the output files
        semaphores
            Dictionary of semaphore objects
        group
            Thread group name
        """
    # download the products, which are not yet available locally
    for download_request, l1product_path in zip(download_requests, l1product_paths):
        if not os.path.exists(l1product_path):
            with semaphores['download']:
                do_download(auth, download_request, l1product_path, server)

    # ensure all products have been downloaded
    for l1product_path in l1product_paths:
        if not os.path.exists(l1product_path):
            raise RuntimeError("Download of product was not successfull: {}".format(l1product_path))

    # FOR S3 MAKE SURE THE NON-DEFAULT S3TBX SETTING IS SELECTED IN THE SNAP PREFERENCES!
    if "OLCI" == params['General']['sensor']:
        product = ProductIO.readProduct(l1product_paths[0])
        if 'PixelGeoCoding2' not in str(product.getSceneGeoCoding()):
            raise RuntimeError("Pixelwise geocoding is not activated for S3TBX, please check the settings in SNAP!")
        product.closeIO()

    with semaphores['process']:
        # only process products, which are really necessary
        if len(l1product_paths) in [2, 4]:
            n_group_old = len(l1product_paths)
            l1product_paths, covered = minimal_subset_of_products(l1product_paths, params['General']['wkt'])
            n_group_new = len(l1product_paths)
            if n_group_old != n_group_new:
                print("Group has been reduced from {} to {} necessary product(s)".format(n_group_old, n_group_new))

        l2product_files = {}
        for processor in list(filter(None, params['General']['processors'].split(","))):
            # import processor
            if processor == "IDEPIX":
                from processors.idepix.idepix import process
            elif processor == "C2RCC":
                from processors.c2rcc.c2rcc import process
            elif processor == "POLYMER":
                from processors.polymer.polymer import process
            elif processor == "L_FLUO":
                from processors.fluo.l_fluo import process
            elif processor == "R_FLUO":
                from processors.fluo.r_fluo import process
            elif processor == "MPH":
                from processors.mph.mph import process
            elif processor == "SEN2COR":
                from processors.sen2cor.sen2cor import process
            else:
                raise RuntimeError("Unknown processor: {}".format(processor))

            # apply processor to all products
            for l1product_path in l1product_paths:
                if l1product_path not in l2product_files.keys():
                    l2product_files[l1product_path] = {}
                try:
                    output_file = process(env, params, l1product_path, l2product_files[l1product_path], l2_path)
                    if not output_file:
                        return
                    l2product_files[l1product_path][processor] = output_file

                except Exception:
                    print("An error occured while applying {} to product: {}".format(processor, l1product_path))
                    traceback.print_exc()

        # mosaic outputs
        for processor in list(filter(None, params['General']['processors'].split(","))):
            tmp = []
            for l1product_path in l1product_paths:
                if processor in l2product_files[l1product_path].keys():
                    tmp += [l2product_files[l1product_path][processor]]
            if len(tmp) == 1:
                l2product_files[processor] = tmp[0]
            elif len(tmp) > 1:
                from processors.mosaic.mosaic import mosaic
                try:
                    l2product_files[processor] = mosaic(env, params, tmp)
                    # mosaic output metadata missing: https://senbox.atlassian.net/browse/SNAP-745
                    copy_metadata(tmp[0], l2product_files[processor])
                except Exception:
                    print("An error occured while applying MOSAIC to products: {}".format(tmp))
                    traceback.print_exc()

        for l1product_path in l1product_paths:
            del(l2product_files[l1product_path])

    # apply adapters
    with semaphores['adapt']:
        for adapter in list(filter(None, params['General']['adapters'].split(","))):
            if adapter == "QLRGB":
                from adapters.qlrgb.qlrgb import apply
            elif adapter == "QLSINGLEBAND":
                from adapters.qlsingleband.qlsingleband import apply
            elif adapter == "PRIMARYPRODUCTION":
                from adapters.primaryproduction.primaryproduction import apply
            elif adapter == "DATALAKES":
                from adapters.datalakes.datalakes import apply
            elif adapter == "MERGE":
                from adapters.merge.merge import apply
            elif adapter == "SECCHIDEPTH":
                from adapters.secchidepth.secchidepth import apply
            else:
                raise RuntimeError("Unknown adapter: {}".format(adapter))

            try:
                apply(env, params, l2product_files, group)
            except Exception:
                print(sys.exc_info()[0])
                print("An error occured while applying {} to product: {}".format(adapter, l1product_path))
                traceback.print_exc()
