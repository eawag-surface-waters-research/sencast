#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time
import traceback

from requests.auth import HTTPBasicAuth
from snappy import ProductIO
from threading import Semaphore, Thread

from auxil import get_l1product_path, get_sensing_date_from_product_name, init_hindcast
from externalapis.earthdata_api import authenticate
from product_fun import minimal_subset_of_products


# download apis, processors, and adapters are imported dynamically to make hindcast also work on systems,
# where some of them might not be available


def hindcast(params_file, env_file=None, max_parallel_downloads=1, max_parallel_processors=1, max_parallel_adapters=1):
    # read env and params file and copy the params file to l2_path for reproducibility
    env, params, l2_path = init_hindcast(env_file, params_file)

    do_hindcast(env, params, l2_path, max_parallel_downloads, max_parallel_processors, max_parallel_adapters)


def do_hindcast(env, params, l2_path, max_parallel_downloads=1, max_parallel_processors=1,
                max_parallel_adapters=1):
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

    # set up inputs for product hindcast
    l1product_paths = [get_l1product_path(env, product_name) for product_name in product_names]
    semaphores = {
        'download': Semaphore(max_parallel_downloads),
        'process': Semaphore(max_parallel_processors),
        'adapt': Semaphore(max_parallel_adapters)
    }

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
        if date not in download_groups.keys():
            download_groups[date], l1product_path_groups[date] = [], []
        download_groups[date].append(download_request)
        l1product_path_groups[date].append(l1product_path)

    # print information about grouped products
    print("The products have been grouped into {} group(s).".format(len(l1product_path_groups)))
    print("Each group is handled by an individual thread.")

    # authenticate for earth data api
    authenticate(env['EARTHDATA']['username'], env['EARTHDATA']['password'])

    # do hindcast for every product group
    hindcast_threads = []
    for date, _ in sorted(sorted(download_groups.items()), key=lambda item: len(item[1])):
        args = (env, params, do_download, auth, download_groups[date], l1product_path_groups[date], l2_path, semaphores)
        hindcast_threads.append(Thread(target=hindcast_product_group, args=args))
        hindcast_threads[-1].start()

    # wait for all hindcast threads to terminate
    starttime = time.time()
    for hindcast_thread in hindcast_threads:
        hindcast_thread.join()
    print("Hindcast complete in {0:.1f} seconds.".format(time.time() - starttime))


def hindcast_product_group(env, params, do_download, auth, download_requests, l1product_paths, l2_path, semaphores):
    """ hindcast a set of products with the same sensing date """
    # download the products, which are not yet available locally
    for download_request, l1product_path in zip(download_requests, l1product_paths):
        if not os.path.exists(l1product_path):
            with semaphores['download']:
                do_download(auth, download_request, l1product_path)

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
                    l2product_files[l1product_path][processor] =\
                        process(env, params, l1product_path, l2product_files[l1product_path], l2_path)
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
            elif adapter == "DATALAKES":
                from adapters.datalakes.datalakes import apply
            else:
                raise RuntimeError("Unknown adapter: {}".format(adapter))

            try:
                apply(env, params, l2product_files)
            except Exception:
                print("An error occured while applying {} to product: {}".format(adapter, l1product_path))
                traceback.print_exc()
