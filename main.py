#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
The core functions of Sencast
.. note::
    Download API's, processors, and adapters are imported dynamically to make Sencast also work on systems,
    where some of them might not be available.
"""
import importlib
import os
import time
import traceback
import sys

from requests.auth import HTTPBasicAuth
from threading import Semaphore, Thread

from utils.auxil import init_hindcast
from utils.product_fun import filter_for_timeliness, get_satellite_name_from_product_name, \
    get_sensing_date_from_product_name, get_l1product_path


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


def do_hindcast(env, params, l2_path, max_parallel_downloads=1, max_parallel_processors=1, max_parallel_adapters=1):
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
    # dynamically import the remote dias api to use
    api = env['General']['remote_dias_api']
    authenticate = getattr(importlib.import_module("dias_apis.{}.{}".format(api.lower(), api.lower())), "authenticate")
    get_download_requests = getattr(importlib.import_module("dias_apis.{}.{}".format(api.lower(), api.lower())), "get_download_requests")
    do_download = getattr(importlib.import_module("dias_apis.{}.{}".format(api.lower(), api.lower())), "do_download")

    # create authentication to remote dias api
    auth = authenticate(env[api])

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

    # group download requests and product paths by (date and satelite) and sort them by (group size and sensing date)
    download_groups, l1product_path_groups = {}, {}
    for download_request, l1product_path in zip(download_requests, l1product_paths):
        date = get_sensing_date_from_product_name(os.path.basename(l1product_path))
        satellite = get_satellite_name_from_product_name(os.path.basename(l1product_path))
        group = satellite + "_" + date
        if group not in download_groups.keys():
            download_groups[group], l1product_path_groups[group] = [], []
        download_groups[group].append(download_request)
        l1product_path_groups[group].append(l1product_path)

    # print information about grouped products
    print("The products have been grouped into {} group(s).".format(len(l1product_path_groups)))
    print("Each group is handled by an individual thread.")

    # do hindcast for every product group
    hindcast_threads = []
    for group, _ in sorted(sorted(download_groups.items()), key=lambda item: len(item[1])):
        args = (env, params, do_download, auth, download_groups[group], l1product_path_groups[group], l2_path, semaphores, group, server)
        hindcast_threads.append(Thread(target=hindcast_product_group, args=args, name="Thread-{}".format(group)))
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
        server
            only needed for COAH API
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

    with semaphores['process']:
        l2product_files = {}
        for processor in list(filter(None, params['General']['processors'].split(","))):
            # import processor
            process = getattr(importlib.import_module("processors.{}.{}".format(processor.lower(), processor.lower())), "process")

            # apply processor to all products
            for l1product_path in l1product_paths:
                if l1product_path not in l2product_files.keys():
                    l2product_files[l1product_path] = {}
                try:
                    output_file = process(env, params, l1product_path, l2product_files[l1product_path], l2_path)
                    if output_file:
                        l2product_files[l1product_path][processor] = output_file
                except RuntimeError:
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
                except RuntimeError:
                    print("An error occured while applying MOSAIC to products: {}".format(tmp))
                    traceback.print_exc()

        for l1product_path in l1product_paths:
            del(l2product_files[l1product_path])

    # apply adapters
    with semaphores['adapt']:
        for adapter in list(filter(None, params['General']['adapters'].split(","))):
            try:
                apply = getattr(importlib.import_module("adapters.{}.{}".format(adapter.lower(), adapter.lower())), "apply")
                apply(env, params, l2product_files, group)
            except RuntimeError:
                print(sys.exc_info()[0])
                print("An error occured while applying {} to product group: {}".format(adapter, group))
                traceback.print_exc()
