#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time

from requests.auth import HTTPBasicAuth
from snappy import ProductIO
from threading import Semaphore, Thread

from auxil import get_sensing_date_from_prodcut_name, init_hindcast
from externalapis.earthdata_api import authenticate
from product_fun import minimal_subset_of_products


# download apis, processors, and adapters are imported dynamically to make hindcast also work on systems,
# where some of them might not be available


def hindcast(params_file, env_file=None, max_parallel_downloads=1, max_parallel_processors=1, max_parallel_adapters=1):
    # read env and params file and copy the params file to l2_path for reproducibility
    env, params, l1_path, l2_path = init_hindcast(env_file, params_file)

    do_hindcast(env, params, l1_path, l2_path, max_parallel_downloads, max_parallel_processors, max_parallel_adapters)


def do_hindcast(env, params, l1_path, l2_path, max_parallel_downloads=1, max_parallel_processors=1,
                max_parallel_adapters=1):
    # decide which API to use
    if env['DIAS']['API'] == "COAH":
        from externalapis.coah_api import get_download_requests, do_download
        auth = HTTPBasicAuth(env['COAH']['username'], env['COAH']['password'])
    elif env['DIAS']['API'] == "HDA":
        from externalapis.hda_api import get_download_requests, do_download
        auth = HTTPBasicAuth(env['HDA']['username'], env['HDA']['password'])
    else:
        raise RuntimeError("Unknown API: {} (possible options are 'HDA' or 'COAH').".format(env['General']['API']))

    # find products which match the criterias from params
    start, end = params['General']['start'], params['General']['end']
    sensor, resolution, wkt = params['General']['sensor'], params['General']['resolution'], params['General']['wkt']
    download_requests, product_names = get_download_requests(auth, start, end, sensor, resolution, wkt)
    print("Found {} product(s) which are handled by indivitual threads".format(len(product_names)))

    # set up inputs for product hindcast
    l1_product_paths = [os.path.join(l1_path, product_name) for product_name in product_names]
    semaphores = {
        'download': Semaphore(max_parallel_downloads),
        'process': Semaphore(max_parallel_processors),
        'adapt': Semaphore(max_parallel_adapters)
    }

    # print information about available products
    actual_downloads = len([0 for l1_product_path in l1_product_paths if not os.path.exists(l1_product_path)])
    print("{} products are already available.".format(len(l1_product_paths) - actual_downloads))
    print("{} products must be downloaded first.".format(actual_downloads))

    # authenticate for earth data api
    authenticate(env['EARTHDATA']['username'], env['EARTHDATA']['password'])

    # group download requests and product paths by date and sort them by group size and sensing date
    download_groups, l1_product_groups = {}, {}
    for download_request, l1_product_path in zip(download_requests, l1_product_paths):
        date = get_sensing_date_from_prodcut_name(os.path.basename(l1_product_path))
        if date not in download_groups.keys():
            download_groups[date], l1_product_groups[date] = [], []
        download_groups[date].append(download_request)
        l1_product_groups[date].append(l1_product_path)

    # do hindcast for every product group
    hindcast_threads = []
    for date, _ in sorted(sorted(download_groups.items()), key=lambda item: len(item[1])):
        args = (env, params, do_download, auth, download_groups[date], l1_product_groups[date], l2_path, semaphores)
        hindcast_threads.append(Thread(target=hindcast_product_group, args=args))
        hindcast_threads[-1].start()

    # wait for all hindcast threads to terminate
    starttime = time.time()
    for hindcast_thread in hindcast_threads:
        hindcast_thread.join()
    print("Hindcast complete in {0:.1f} seconds.".format(time.time() - starttime))


def hindcast_product_group(env, params, do_download, auth, download_requests, l1_product_paths, l2_path, semaphores):
    """ hindcast a set of products with the same sensing date """
    # download the products, which are not yet available locally
    for download_request, l1_product_path in zip(download_requests, l1_product_paths):
        if not os.path.exists(l1_product_path):
            with semaphores['download']:
                do_download(auth, download_request, l1_product_path)

    # ensure all products have been downloaded
    for l1_product_path in l1_product_paths:
        if not os.path.exists(l1_product_path):
            raise RuntimeError("Download or mosaicing of product was not successfull: {}".format(l1_product_path))

    # FOR S3 MAKE SURE THE NON-DEFAULT S3TBX SETTING IS SELECTED IN THE SNAP PREFERENCES!
    if "OLCI" == params['General']['sensor']:
        product = ProductIO.readProduct(l1_product_paths[0])
        if 'PixelGeoCoding2' not in str(product.getSceneGeoCoding()):
            raise RuntimeError("Pixelwise geocoding is not activated for S3TBX, please check the settings in SNAP!")
        product.closeIO()

    # only process products, which are really necessary
    if len(l1_product_paths) in [2, 4]:
        l1_product_paths, covered = minimal_subset_of_products(l1_product_paths, params['General']['wkt'])

    with semaphores['process']:
        # process the products
        from processors.idepix.idepix import process
        l2_product_paths = {'IDEPIX': []}
        for l1_product_path in l1_product_paths:
            l2_product_paths['IDEPIX'] += [process(env, params, l1_product_path, l1_product_path, l2_path)]
        if "C2RCC" in params['General']['processors'].split(","):
            from processors.c2rcc.c2rcc import process
            l2_product_paths['C2RCC'] = []
            for l1_product_path, l1p_product_path in zip(l1_product_paths, l2_product_paths['IDEPIX']):
                l2_product_paths['C2RCC'] += [process(env, params, l1_product_path, l1p_product_path, l2_path)]
        if "POLYMER" in params['General']['processors'].split(","):
            from processors.polymer.polymer import process
            l2_product_paths['POLYMER'] = []
            for l1_product_path, l1p_product_path in zip(l1_product_paths, l2_product_paths['IDEPIX']):
                l2_product_paths['POLYMER'] += [process(env, params, l1_product_path, l1p_product_path, l2_path)]
        if "MPH" in params['General']['processors'].split(","):
            from processors.mph.mph import process
            l2_product_paths['MPH'] = []
            for l1_product_path, l1p_product_path in zip(l1_product_paths, l2_product_paths['IDEPIX']):
                l2_product_paths['MPH'] += [process(env, params, l1_product_path, l1p_product_path, l2_path)]

        # mosaic outputs
        if params['General']['sensor'] == "MSI" and len(l1_product_paths) > 1:
            from processors.mosaic.mosaic import mosaic
            for processor in l2_product_paths.keys():
                l2_product_paths[processor] = mosaic(env, params, l2_product_paths[processor])
        else:
            for processor in l2_product_paths.keys():
                l2_product_paths[processor] = l2_product_paths[processor][0]

    with semaphores['adapt']:
        # apply adapters
        if "QLRGB" in params['General']['adapters'].split(","):
            from adapters.qlrgb.qlrgb import apply
            apply(env, params, l2_product_paths)
        if "QLSINGLEBAND" in params['General']['adapters'].split(","):
            from adapters.qlsingleband.qlsingleband import apply
            apply(env, params, l2_product_paths)
        if "DATALAKES" in params['General']['adapters'].split(","):
            from adapters.datalakes.datalakes import apply
            apply(env, params, l2_product_paths)
