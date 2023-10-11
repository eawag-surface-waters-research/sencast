# -*- coding: utf-8 -*-
import os
import sys
import time
import shutil
import argparse
import importlib
import traceback
from threading import Semaphore, Thread

from utils.auxil import authenticate_earthdata_anc, init_hindcast, log, authenticate_cds_anc
from utils.product_fun import filter_for_timeliness, get_satellite_name_from_product_name, \
    get_sensing_date_from_product_name, get_l1product_path, filter_for_tiles, filter_for_baseline

global errors
errors = []


def sencast(params_file, env_file=None, max_parallel_downloads=1, max_parallel_processors=1,
            max_parallel_adapters=1):
    """
    File-based interface for Sencast.

    Parameters
    ------------

    params_file
        File to read the parameters for this run from
    env_file
        | **Default: None**
        | Environment settings read from the environment .ini file, if None provided Sencast will search for file in environments folder.
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
    l2product_files = {}
    env, params, l2_path = init_hindcast(env_file, params_file)
    sencast_core(env, params, l2_path, l2product_files, max_parallel_downloads, max_parallel_processors,
                   max_parallel_adapters)
    return l2product_files


def sencast_core(env, params, l2_path, l2product_files, max_parallel_downloads=1, max_parallel_processors=1,
                   max_parallel_adapters=1):
    """
    Threading function for running Sencast.
    1. Calls API to find available data for given query
    2. Splits the processing into threads based on date and satellite
    3. Runs the Sencast for each thread

    Parameters
    ----------

    env
        Dictionary of environment parameters, loaded from input file
    params
        Dictionary of parameters, loaded from input file
    l2_path
        The output folder in which to save the output files
    l2product_files
        A dictionary to return the outputs (produced l2 product files)
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
    get_download_requests = getattr(importlib.import_module("dias_apis.{}.{}".format(api.lower(), api.lower())),
                                    "get_download_requests")
    do_download = getattr(importlib.import_module("dias_apis.{}.{}".format(api.lower(), api.lower())), "do_download")

    # create authentication to remote dias api
    auth = authenticate(env[api])

    # create .netrc if not yet there
    try:
        authenticate_earthdata_anc(env)
    except Exception as e:
        print(e)
        log(env["General"]["log"], "WARNING failed to create earthdata credential files")

    # create .cdsapirc if not yet there
    try:
        authenticate_cds_anc(env)
    except Exception as e:
        print(e)
        log(env["General"]["log"], "WARNING failed to create cds credential files")

    # find products which match the criterias from params
    start, end = params['General']['start'], params['General']['end']
    sensor, resolution, wkt = params['General']['sensor'], params['General']['resolution'], params['General']['wkt']
    try:
        download_requests, product_names = get_download_requests(auth, start, end, sensor, resolution, wkt, env)
    except Exception as e:
        print(e)
        raise ValueError("Unable to access {} API, please check your internet conectivity or try using an alternative API".format(api))

    # filter for timeliness
    download_requests, product_names = filter_for_timeliness(download_requests, product_names, env)

    # filter for tiles
    if "tiles" in params['General']:
        tiles = params['General']["tiles"].replace(" ", "").split(",")
        download_requests, product_names = filter_for_tiles(download_requests, product_names, tiles, env)

    # filter for baseline
    download_requests, product_names = filter_for_baseline(download_requests, product_names, sensor, env)

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
        log(env["General"]["log"],
            "Products which are available will not be downloaded because the local DIAS is set to 'readonly'.")
    else:
        actual_downloads = len([0 for l1product_path in l1product_paths if not os.path.exists(l1product_path)])
        log(env["General"]["log"],
            "{} products are already locally available.".format(len(l1product_paths) - actual_downloads))
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

    start_time = time.time()

    if "threading" in env["General"] and env["General"]["threading"].lower() == "false":
        log(env["General"]["log"], "Each group is run sequentially.")
        for group, _ in sorted(sorted(download_groups.items()), key=lambda item: len(item[1])):
            sencast_product_group(env, params, do_download, auth, download_groups[group], l1product_path_groups[group],
                                  l2_path, l2product_files, semaphores, group)
    else:
        log(env["General"]["log"], "Each group is handled by an individual thread.")
        hindcast_threads = []
        for group, _ in sorted(sorted(download_groups.items()), key=lambda item: len(item[1])):
            args = (
                env, params, do_download, auth, download_groups[group], l1product_path_groups[group], l2_path,
                l2product_files,
                semaphores, group)
            hindcast_threads.append(Thread(target=sencast_product_group, args=args, name="Thread-{}".format(group)))
            hindcast_threads[-1].start()

        # wait for all hindcast threads to terminate
        for hindcast_thread in hindcast_threads:
            hindcast_thread.join()

    log(env["General"]["log"], "Hindcast complete in {0:.1f} seconds.".format(time.time() - start_time))

    if len(errors) > 0:
        raise RuntimeError("Sencast returned the following {} errors: {}"
                           .format(len(errors), ", ".join(errors)))


def sencast_product_group(env, params, do_download, auth, download_requests, l1product_paths, l2_path,
                          l2product_files_outer, semaphores, group):
    """
    Run Sencast for given thread.
    1. Downloads required products
    2. Runs processors
    3. Runs mosaic
    4. Runs adapters

    Parameters
    ----------

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
                log(env["General"]["log"], "Downloading file: " + l1product_path)
                try:
                    do_download(auth, download_request, l1product_path, env)
                except (Exception,):
                    log(env["General"]["log"], traceback.format_exc(), indent=2)
                    log(env["General"]["log"], "Failed to download file {}.".format(l1product_path))

    with semaphores['process']:
        l2product_files = {}
        # apply processors to all products
        for processor in list(filter(None, params['General']['processors'].split(","))):

            log(env["General"]["log"], "", blank=True)
            log(env["General"]["log"], "Processor {} starting...".format(processor))
            process = getattr(
                importlib.import_module("processors.{}.{}".format(processor.lower(), processor.lower())), "process")
            processor_outputs = []
            for l1product_path in l1product_paths:
                if l1product_path not in l2product_files.keys():
                    l2product_files[l1product_path] = {}
                if not os.path.exists(l1product_path):
                    log(env["General"]["log"], "Failed. Processor {} requires input file {}.".format(processor, l1product_path), indent=1)
                    errors.append("{} failed for {} (no input file available)".format(processor, os.path.basename(l1product_path)))
                    continue
                try:
                    log(env["General"]["log"], "{} running for {}.".format(processor, l1product_path), indent=1)
                    output_file = process(env, params, l1product_path, l2product_files[l1product_path], l2_path)
                    l2product_files[l1product_path][processor] = output_file
                    processor_outputs.append(output_file)
                    log(env["General"]["log"], "{} finished for {}.".format(processor, l1product_path), indent=1)
                except (Exception,):
                    log(env["General"]["log"], traceback.format_exc(), indent=2)
                    log(env["General"]["log"], "{} failed for {}.".format(processor, l1product_path), indent=1)
                    errors.append("{} failed for {} (see log for details)".format(processor, os.path.basename(l1product_path)))

            if len(processor_outputs) == 1:
                l2product_files[processor] = processor_outputs[0]
            elif len(processor_outputs) > 1:
                if "mosaic" in params["General"] and params["General"]["mosaic"] == "False":
                    log(env["General"]["log"], "Mosaic outputs set to false, not mosaicing {}".format(processor), indent=1)
                    l2product_files[processor] = processor_outputs
                else:
                    try:
                        log(env["General"]["log"], "Mosaicing outputs of processor {}...".format(processor), indent=1)
                        from mosaic.mosaic import mosaic
                        l2product_files[processor] = mosaic(env, params, processor_outputs)
                        log(env["General"]["log"], "Mosaiced outputs of processor {}.".format(processor), indent=1)
                    except (Exception,):
                        log(env["General"]["log"], traceback.format_exc(), indent=2)
                        log(env["General"]["log"], "Mosaicing outputs of processor {} failed.".format(processor), indent=1)
                        errors.append("{} mosaic failed (see log for details)".format(processor))
            log(env["General"]["log"], "Processor {} complete.".format(processor))

        for l1product_path in l1product_paths:
            try:
                del (l2product_files[l1product_path])
            except:
                log(env["General"]["log"], "Failed to delete: {}".format(l1product_path))
        log(env["General"]["log"], "", blank=True)
        log(env["General"]["log"], "All processors finished! {}".format(str(l2product_files)))

    # apply adapters
    if "adapters" in params["General"]:
        with semaphores['adapt']:
            for adapter in list(filter(None, params['General']['adapters'].split(","))):
                try:
                    log(env["General"]["log"], "", blank=True)
                    log(env["General"]["log"], "Adapter {} starting...".format(adapter))
                    apply = getattr(importlib.import_module("adapters.{}.{}".format(adapter.lower(), adapter.lower())),
                                    "apply")
                    apply(env, params, l2product_files, group)
                    log(env["General"]["log"], "Adapter {} finished.".format(adapter))
                except (Exception,):
                    log(env["General"]["log"], traceback.format_exc(), indent=2)
                    log(env["General"]["log"], "Adapter {} failed on product group {}.".format(adapter, group))
                    errors.append("Adapter {} failed for {} (see log for details)".format(adapter, group))

    if 'remove_inputs' in params['General'] and params['General']['remove_inputs']:
        log(env["General"]["log"], "Deleting input files")
        for l1product_path in l1product_paths:
            log(env["General"]["log"], "Removing: {}".format(l1product_path), indent=1)
            if os.path.isfile(l1product_path):
                os.remove(l1product_path)
            elif os.path.isdir(l1product_path):
                shutil.rmtree(l1product_path)

    l2product_files_outer[group] = l2product_files


def test_installation(env, delete):
    if delete:
        _, params_s3, l2_path_s3 = init_hindcast(env, 'test_S3_processors.ini')
        shutil.rmtree(l2_path_s3)
    try:
        sencast('test_S3_processors.ini', env_file=env)
    except Exception as e:
        print("Some S3 processors failed")
        print(e)

    if delete:
        _, params_s2, l2_path_s2 = init_hindcast(env, 'test_S2_processors.ini')
        shutil.rmtree(l2_path_s2)
    try:
        sencast('test_S2_processors.ini', env_file=env)
    except Exception as e:
        print("Some S2 processors failed")
        print(e)

    if delete:
        _, params_l8, l2_path_l8 = init_hindcast(env, 'test_L8_processors.ini')
        shutil.rmtree(l2_path_l8)
    try:
        sencast('test_L8_processors.ini', env_file=env)
    except Exception as e:
        print("Some L8 processors failed.")
        print(e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--parameters', '-p', help="Absolute path to parameter file", type=str)
    parser.add_argument('--environment', '-e', help="Absolute path to environment file", type=str, default=None)
    parser.add_argument('--downloads', '-d', help="Maximum number of parallel downloads of satellite images", type=int,
                        default=1)
    parser.add_argument('--processors', '-r', help="Maximum number of processors to run in parallel", type=int,
                        default=1)
    parser.add_argument('--adapters', '-a', help="Maximum number of adapters to run in parallel", type=int, default=1)
    parser.add_argument('--tests', '-t', help="Run test scripts to check Sencast installation", action='store_true')
    parser.add_argument('--delete_tests', '-x', help="Delete previous test run.", action='store_true')
    args = parser.parse_args()
    variables = vars(args)
    sys.argv = [sys.argv[0]]
    if variables["tests"]:
        test_installation(variables["environment"], variables["delete_tests"])
    else:
        if variables["parameters"] is None:
            raise ValueError("Sencast FAILED. Link to parameters file must be provided.")
        sencast(variables["parameters"],
                env_file=variables["environment"],
                max_parallel_downloads=variables["downloads"],
                max_parallel_processors=variables["processors"],
                max_parallel_adapters=variables["adapters"])
