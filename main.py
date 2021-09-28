#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
The core functions of Sencast
.. note::
    Download API's, processors, and adapters are imported dynamically to make Sencast also work on systems,
    where some of them might not be available.
"""
import importlib
import logging
import os
import time
import traceback
import sys

from utils import earthdata
from threading import Semaphore, Thread

from utils.auxil import init_hindcast, log
from utils.product_fun import filter_for_timeliness, get_satellite_name_from_product_name, \
    get_sensing_date_from_product_name, get_l1product_path


logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)


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

        env
            Dictionary of environment parameters, loaded from input file
        params
            Dictionary of parameters, loaded from input file
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
    api = params['General']['remote_dias_api']
    authenticate = getattr(importlib.import_module("dias_apis.{}.{}".format(api.lower(), api.lower())), "authenticate")
    get_download_requests = getattr(importlib.import_module("dias_apis.{}.{}".format(api.lower(), api.lower())), "get_download_requests")
    do_download = getattr(importlib.import_module("dias_apis.{}.{}".format(api.lower(), api.lower())), "do_download")

    # create authentication to remote dias api
    auth = authenticate(env[api])

    # find products which match the criterias from params
    start, end = params['General']['start'], params['General']['end']
    sensor, resolution, wkt = params['General']['sensor'], params['General']['resolution'], params['General']['wkt']
    download_requests, product_names = get_download_requests(auth, start, end, sensor, resolution, wkt, env)

    # filter for timeliness
    download_requests, product_names = filter_for_timeliness(download_requests, product_names, env)

    # set up inputs for product hindcast
    l1product_paths = [get_l1product_path(env, product_name) for product_name in product_names]
    semaphores = {
        'download': Semaphore(max_parallel_downloads),
        'process': Semaphore(max_parallel_processors),
        'adapt': Semaphore(max_parallel_adapters)
    }

    # for readonly local dias, remove unavailable products and their download_requests
    if env['DIAS']['readonly'] == "True":
        log(env["General"]["log"], "{} products have been found.".format(len(l1product_paths)))
        for i in range(len(l1product_paths)):
            if not os.path.exists(l1product_paths[i]):
                download_requests[i], l1product_paths[i] = None, None
        l1product_paths = list(filter(None, l1product_paths))
        download_requests = list(filter(None, download_requests))
        log(env["General"]["log"], "{} products are avaiable and will be processed.".format(len(l1product_paths)))
        log(env["General"]["log"], "Products which are available will not be downloaded because the local DIAS is set to 'readonly'.")
    else:
        actual_downloads = len([0 for l1product_path in l1product_paths if not os.path.exists(l1product_path)])
        log(env["General"]["log"], "{} products are already locally available.".format(len(l1product_paths) - actual_downloads))
        log(env["General"]["log"], "{} products must be downloaded first.".format(actual_downloads))

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
    log(env["General"]["log"], "The products have been grouped into {} group(s).".format(len(l1product_path_groups)))
    log(env["General"]["log"], "Each group is handled by an individual thread.")

    # authenticate to earthdata api for anchillary data download anchillary data (used by some processors)
    earthdata.authenticate(env)

    # do hindcast for every product group
    hindcast_threads = []
    for group, _ in sorted(sorted(download_groups.items()), key=lambda item: len(item[1])):
        args = (env, params, do_download, auth, download_groups[group], l1product_path_groups[group], l2_path, semaphores, group)
        hindcast_threads.append(Thread(target=hindcast_product_group, args=args, name="Thread-{}".format(group)))
        hindcast_threads[-1].start()

    # wait for all hindcast threads to terminate
    starttime = time.time()
    for hindcast_thread in hindcast_threads:
        hindcast_thread.join()
    log(env["General"]["log"], "Hindcast complete in {0:.1f} seconds.".format(time.time() - starttime))


def hindcast_product_group(env, params, do_download, auth, download_requests, l1product_paths, l2_path, semaphores, group):
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
                do_download(auth, download_request, l1product_path, env)

    # ensure all products have been downloaded
    for l1product_path in l1product_paths:
        if not os.path.exists(l1product_path):
            raise RuntimeError("Download of product was not successfull: {}".format(l1product_path))

    # process the products
    with semaphores['process']:
        l2product_files = {}
        # apply processors to all products
        for processor in list(filter(None, params['General']['processors'].split(","))):
            try:
                log(env["General"]["log"], "Processor {} starting...".format(processor))
                process = getattr(importlib.import_module("processors.{}.{}".format(processor.lower(), processor.lower())), "process")
                processor_outputs = []
                for l1product_path in l1product_paths:
                    if l1product_path not in l2product_files.keys():
                        l2product_files[l1product_path] = {}
                    output_file = process(env, params, l1product_path, l2product_files[l1product_path], l2_path)
                    l2product_files[l1product_path][processor] = output_file
                    processor_outputs.append(output_file)
                log(env["General"]["log"], "Processor {} finished: [{}].".format(processor, ", ".join(processor_outputs)))
                if len(processor_outputs) == 1:
                    l2product_files[processor] = processor_outputs[0]
                elif len(processor_outputs) > 1:
                    try:
                        log(env["General"]["log"], "Mosaicing outputs of processor {}...".format(processor))
                        from mosaic.mosaic import mosaic
                        l2product_files[processor] = mosaic(env, params, processor_outputs)
                        log(env["General"]["log"], "Mosaiced outputs of processor {}.".format(processor))
                    except (Exception, ):
                        log(env["General"]["log"], "Mosaicing outputs of processor {} failed.".format(processor))
                        traceback.print_exc()
            except (Exception, ):
                log(env["General"]["log"], "Processor {} failed on product {}.".format(processor, l1product_path))
                log(env["General"]["log"], sys.exc_info()[0])
                traceback.print_exc()
        del processor_outputs
        for l1product_path in l1product_paths:
            del(l2product_files[l1product_path])
        log(env["General"]["log"], "All processors finished! {}".format(str(l2product_files)))

    # apply adapters
    with semaphores['adapt']:
        for adapter in list(filter(None, params['General']['adapters'].split(","))):
            try:
                log(env["General"]["log"], "Adapter {} starting...".format(adapter))
                apply = getattr(importlib.import_module("adapters.{}.{}".format(adapter.lower(), adapter.lower())), "apply")
                apply(env, params, l2product_files, group)
                log(env["General"]["log"], "Adapter {} finished.".format(adapter))
            except (Exception, ):
                log(env["General"]["log"], "Adapter {} failed on product group {}.".format(adapter, group))
                log(env["General"]["log"], sys.exc_info()[0])
                traceback.print_exc()


if len(sys.argv) == 2:
    hindcast(params_file=sys.argv[1])
elif len(sys.argv) == 3:
    hindcast(params_file=sys.argv[1], env_file=sys.argv[2])
