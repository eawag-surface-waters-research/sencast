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
from utils.product_fun import remove_superseded_products, get_l1product_path, filter_for_tiles, filter_for_baseline

conda_env_path = os.environ.get("CONDA_PREFIX")
if conda_env_path:
    proj_data_path = os.path.join(conda_env_path, "share", "proj")
    os.environ["PROJ_DATA"] = proj_data_path

global summary
summary = []


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
    sencast_core(env, params, l2_path, l2product_files, max_parallel_downloads, max_parallel_processors, max_parallel_adapters)
    return l2product_files


def sencast_core(env, params, l2_path, l2product_files, max_parallel_downloads=1, max_parallel_processors=1, max_parallel_adapters=1):
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

    # Dynamically import the remote dias api to use
    api = params['General']['remote_dias_api']


    try:
        authenticate_earthdata_anc(env)
    except Exception as e:
        print(e)
        log(env["General"]["log"], "WARNING failed to create earthdata credential files")

    try:
        authenticate_cds_anc(env)
    except Exception as e:
        print(e)
        log(env["General"]["log"], "WARNING failed to create cds credential files")

    start, end = params['General']['start'], params['General']['end']
    sensor, resolution, wkt = params['General']['sensor'], params['General']['resolution'], params['General']['wkt']

    products = False
    for api in [a.strip() for a in params['General']['remote_dias_api'].split(",")]:
        log(env["General"]["log"], "Attempting to access data from {}".format(api))
        try:
            authenticate = getattr(importlib.import_module("dias_apis.{}.{}".format(api.lower(), api.lower())),
                                   "authenticate")
            get_download_requests = getattr(importlib.import_module("dias_apis.{}.{}".format(api.lower(), api.lower())),
                                            "get_download_requests")
            do_download = getattr(importlib.import_module("dias_apis.{}.{}".format(api.lower(), api.lower())),
                                  "do_download")
            auth = authenticate(env[api])
            products = get_download_requests(auth, start, end, sensor, resolution, wkt, env)
            break
        except Exception as e:
            log(env["General"]["log"], "FAILED to access data from {}".format(api))
            print(e)
    if products == False:
        raise ValueError("Unable to access API's, please check your internet connectivity or try adding an alternative API")

    # filter for timeliness
    products = remove_superseded_products(products, env)

    # filter for tiles
    if "tiles" in params['General']:
        tiles = params['General']["tiles"].replace(" ", "").split(",")
        products = filter_for_tiles(products, tiles, env)

    # filter for baseline
    products = filter_for_baseline(products, sensor, env)

    # set up inputs for product hindcast
    for product in products:
        product["l1_product_path"] = get_l1product_path(env, product["name"])

    semaphores = {
        'download': Semaphore(max_parallel_downloads),
        'process': Semaphore(max_parallel_processors),
        'adapt': Semaphore(max_parallel_adapters)
    }

    # For readonly local dias, remove unavailable products
    if env['DIAS']['readonly'] == "True":
        log(env["General"]["log"], "{} products have been found.".format(len(products)))
        for i in range(len(products)):
            if not os.path.exists(products[i]["l1_product_path"]):
                products[i] = None
        products = list(filter(None, products))
        log(env["General"]["log"], "{} products are available and will be processed.".format(len(products)))
        log(env["General"]["log"],"Products which are available will not be downloaded because the local DIAS is set to 'readonly'.")
    else:
        actual_downloads = len([0 for product in products if not os.path.exists(product["l1_product_path"])])
        log(env["General"]["log"], "{} products are already locally available.".format(len(products) - actual_downloads))
        log(env["General"]["log"], "{} products must be downloaded first.".format(actual_downloads))

    # Group by Sensor and Sensing Date
    product_groups = {}
    for product in products:
        group = "{}_{}".format(product["satellite"], product["sensing_start"])
        if group not in product_groups.keys():
            product_groups[group] = []
        product_groups[group].append(product)

    log(env["General"]["log"], "The products have been grouped into {} group(s).".format(len(product_groups)))

    start_time = time.time()

    if "threading" in env["General"] and env["General"]["threading"].lower() == "false":
        log(env["General"]["log"], "Each group is run sequentially.")
        for group in product_groups.keys():
            sencast_product_group(env, params, do_download, auth, product_groups[group], l2_path, l2product_files, semaphores, group)
    else:
        log(env["General"]["log"], "Each group is handled by an individual thread.")
        hindcast_threads = []
        for group in product_groups.keys():
            args = (env, params, do_download, auth, product_groups[group], l2_path, l2product_files, semaphores, group)
            hindcast_threads.append(Thread(target=sencast_product_group, args=args, name="Thread-{}".format(group)))
            hindcast_threads[-1].start()

        # wait for all hindcast threads to terminate
        for hindcast_thread in hindcast_threads:
            hindcast_thread.join()

    log(env["General"]["log"], "Sencast completed in {0:.1f} seconds.".format(time.time() - start_time))
    log(env["General"]["log"], "", blank=True)

    log(env["General"]["log"], "SUMMARY")
    succeeded = [s for s in summary if s["status"] == "Succeeded"]
    errors = [e for e in summary if e["status"] == "Failed"]

    for p in succeeded:
        log(env["General"]["log"], "SUCCEEDED: {}".format(p))
    for p in errors:
        log(env["General"]["log"], "FAILED: {}".format(p))

    if len(errors) > 0:
        raise RuntimeError("Sencast failed for {}/{} processes.".format(len(errors), len(summary)))
    else:
        if 'remove_inputs' in params['General'] and params['General']['remove_inputs'] == "True":
            log(env["General"]["log"], "Deleting input files")
            for product in products:
                log(env["General"]["log"], "Removing: {}".format(product["l1_product_path"]), indent=1)
                if os.path.isfile(product["l1_product_path"]):
                    os.remove(product["l1_product_path"])
                elif os.path.isdir(product["l1_product_path"]):
                    shutil.rmtree(product["l1_product_path"])
        if 'remove_outputs' in params['General'] and params['General']['remove_outputs'] == "True":
            log(env["General"]["log"], "Deleting output files")
            shutil.rmtree(l2_path)


def sencast_product_group(env, params, do_download, auth, products, l2_path, l2product_files_outer, semaphores, group):
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
    products
        Array of dictionary's that contain product information
    l2_path
        The output folder in which to save the output files
    semaphores
        Dictionary of semaphore objects
    group
        Thread group name
    """
    log(env["General"]["log"], "", blank=True)
    log(env["General"]["log"], 'Processing group: "{}"'.format(group))
    log(env["General"]["log"], 'Outputting to folder : "{}"'.format(l2_path))
    for product in products:
        if not os.path.exists(product["l1_product_path"]):
            with semaphores['download']:
                log(env["General"]["log"], "Downloading file: " + product["l1_product_path"])
                try:
                    do_download(auth, product, env)
                except (Exception,):
                    log(env["General"]["log"], traceback.format_exc(), indent=2)
                    log(env["General"]["log"], "Failed to download file {}.".format(product["l1_product_path"]))
                    summary.append(
                        {"group": group, "input": product["l1_product_path"], "output": "", "type": "download",
                         "name": "Download", "status": "Failed", "time": "", "message": traceback.format_exc()})
                    return

    with semaphores['process']:
        l2product_files = {}
        for processor in [p.strip() for p in filter(None, params['General']['processors'].split(","))]:
            log(env["General"]["log"], "", blank=True)
            log(env["General"]["log"], "Processor {} starting...".format(processor))
            try:
                process = getattr(
                    importlib.import_module("processors.{}.{}".format(processor.lower(), processor.lower())), "process")
            except Exception as e:
                log(env["General"]["log"], "Failed to import processor.".format(processor))
                print(e)
                for product in products:
                    summary.append(
                        {"group": group, "input": product["l1_product_path"], "type": "processor", "name": processor,
                         "status": "Failed", "time": 0,
                         "message": "Unable to import processor."})
                continue

            processor_outputs = []
            for product in products:
                if product["l1_product_path"] not in l2product_files.keys():
                    l2product_files[product["l1_product_path"]] = {}
                if not os.path.exists(product["l1_product_path"]):
                    log(env["General"]["log"], "Failed. Processor {} requires input file {}.".format(processor, product["l1_product_path"]), indent=1)
                    summary.append({"group": group, "input": product["l1_product_path"], "type": "processor", "name": processor, "status": "Failed", "time": 0, "message": "Input file {} not available".format(os.path.basename(product["l1_product_path"]))})
                    continue
                start = time.time()
                try:
                    log(env["General"]["log"], "{} running for {}.".format(processor, product["l1_product_path"]), indent=1)
                    output_file = process(env, params, product["l1_product_path"], l2product_files[product["l1_product_path"]], l2_path)
                    duration = int(time.time() - start)
                    input_file = product["l1_product_path"]
                    if isinstance(output_file, list):
                        output_file = output_file[0]
                        product["l1_product_path"] = output_file
                        l2product_files[input_file][processor] = False
                    else:
                        l2product_files[input_file][processor] = output_file
                        processor_outputs.append(output_file)
                    log(env["General"]["log"], "{} finished for {} in .".format(processor, input_file), indent=1)
                    summary.append({"group": group, "input": input_file, "output": output_file, "type": "processor", "name": processor, "status": "Succeeded", "time": duration, "message": ""})
                except Exception as e:
                    duration = int(time.time() - start)
                    log(env["General"]["log"], traceback.format_exc(), indent=2)
                    log(env["General"]["log"], "{} failed for {} in {}s.".format(processor, product["l1_product_path"], duration), indent=1)
                    summary.append({"group": group, "input": product["l1_product_path"], "output": "", "type": "processor", "name": processor, "status": "Failed", "time": duration, "message": e})

            if len(processor_outputs) == 1:
                l2product_files[processor] = processor_outputs[0]
            elif len(processor_outputs) > 1:
                if "mosaic" in params["General"] and params["General"]["mosaic"] == "False":
                    log(env["General"]["log"], "Mosaic outputs set to false, not mosaicing {}".format(processor), indent=1)
                    l2product_files[processor] = processor_outputs
                else:
                    start = time.time()
                    try:
                        log(env["General"]["log"], "Mosaicing outputs of processor {}...".format(processor), indent=1)
                        from mosaic.mosaic import mosaic
                        l2product_files[processor] = mosaic(env, params, processor_outputs)
                        duration = int(time.time() - start)
                        log(env["General"]["log"], "Mosaiced outputs of processor {}.".format(processor), indent=1)
                        summary.append({"group": group, "input": "Multiple", "output": l2product_files[processor], "type": "mosaic", "name": processor, "status": "Succeeded", "time": duration, "message": ""})
                    except Exception as e:
                        duration = int(time.time() - start)
                        log(env["General"]["log"], traceback.format_exc(), indent=2)
                        log(env["General"]["log"], "Mosaicing outputs of processor {} failed.".format(processor), indent=1)
                        summary.append({"group": group, "input": "Multiple", "output": "", "type": "mosaic", "name": processor, "status": "Failed", "time": duration, "message": e})
            log(env["General"]["log"], "Processor {} complete.".format(processor))

        for product in products:
            try:
                del (l2product_files[product["l1_product_path"]])
            except:
                log(env["General"]["log"], "Failed to delete: {}".format(product["l1_product_path"]))

    if "adapters" in params["General"]:
        with semaphores['adapt']:
            for adapter in [a.strip() for a in filter(None, params['General']['adapters'].split(","))]:
                start = time.time()
                try:
                    log(env["General"]["log"], "", blank=True)
                    log(env["General"]["log"], "Adapter {} starting...".format(adapter))
                    apply = getattr(importlib.import_module("adapters.{}.{}".format(adapter.lower(), adapter.lower())),
                                    "apply")
                    apply(env, params, l2product_files, group)
                    duration = int(time.time() - start)
                    log(env["General"]["log"], "Adapter {} finished.".format(adapter))
                    summary.append({"group": group, "input": "Multiple", "output": "", "type": "adapter", "name": adapter, "status": "Succeeded", "time": duration, "message": traceback.format_exc()})
                except Exception as e:
                    duration = int(time.time() - start)
                    log(env["General"]["log"], traceback.format_exc(), indent=2)
                    log(env["General"]["log"], "Adapter {} failed on product group {}.".format(adapter, group))
                    summary.append({"group": group, "input": "Multiple", "output": "", "type": "adapter", "name": adapter, "status": "Failed", "time": duration, "message": e})

    l2product_files_outer[group] = l2product_files
    log(env["General"]["log"], "", blank=True)
    log(env["General"]["log"], 'Processing group: "{}" complete.'.format(group))


def test_installation(env, delete):
    tests = ["test_S3_processors",
             "test_S2_processors",
             "test_Collection_processors",
             "test_L8_processors",
             "test_PACE_processors"]
    for test in tests:
        if delete:
            _, params, out_path = init_hindcast(env, '{}.ini'.format(test))
            shutil.rmtree(out_path)
        try:
            sencast('{}.ini'.format(test), env_file=env)
        except Exception as e:
            print("Some processors failed in {}".format(test))
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
