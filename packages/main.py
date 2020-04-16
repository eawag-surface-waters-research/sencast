#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import time

from requests.auth import HTTPBasicAuth
from snappy import ProductIO
from threading import Semaphore, Thread

from packages.auxil import init_hindcast
from packages.earthdata_api import authenticate

# download apis, processors, and adapters are imported dynamically to make hindcast also work on systems,
# where some of them might not be available


def hindcast(params_file, env_file=None, wkt_file=None, max_parallel_downloads=1, max_parallel_processing=1):
    # read env, params, and wkt file and copy files for reproducibility to l2_path
    env, params, wkt, l1_path, l2_path = init_hindcast(env_file, params_file, wkt_file)

    do_hindcast(env, params, wkt, l1_path, l2_path, max_parallel_downloads, max_parallel_processing)


def do_hindcast(env, params, wkt, l1_path, l2_path, max_parallel_downloads=1, max_parallel_processing=1):
    # decide which API to use
    if env['DIAS']['API'] == "COAH":
        from diasapis.coah_api import get_download_requests, do_download
    elif env['DIAS']['API'] == "HDA":
        from diasapis.hda_api import get_download_requests, do_download
    else:
        raise RuntimeError("Unknown API: {} (possible options are 'HDA' or 'COAH').".format(env['General']['API']))

    # find products which match the criterias from params
    auth = HTTPBasicAuth(env['COAH']['username'], env['COAH']['password'])
    start, end = params['General']['start'], params['General']['end']
    sensor, resolution = params['General']['sensor'], int(params['General']['resolution'])
    download_requests, product_names = get_download_requests(auth, wkt, start, end, sensor, resolution)
    print("Found {} product(s) which are handled by indivitual threads".format(len(product_names)))

    # set up inputs for product hindcast
    l1_product_paths = [os.path.join(l1_path, product_name) for product_name in product_names]
    semaphores = {'download': Semaphore(max_parallel_downloads), 'processing': Semaphore(max_parallel_processing)}

    # print information about available products
    actual_downloads = len([0 for l1_product_path in l1_product_paths if not os.path.exists(l1_product_path)])
    print("{} products are already available.".format(len(l1_product_paths) - actual_downloads))
    print("{} products must be downloaded first.".format(actual_downloads))

    # Authenticate for earth data api
    authenticate(env['Earthdata']['username'], env['Earthdata']['password'])

    # do hindcast for every product
    hindcast_threads = []
    for download_request, l1_product_path in zip(download_requests, l1_product_paths):
        args = (env, params, wkt, do_download, auth, download_request, l1_product_path, l2_path, semaphores)
        hindcast_threads.append(Thread(target=hindcast_product, args=args))
        hindcast_threads[-1].start()

    # wait for all hindcast threads to terminate
    starttime = time.time()
    for hindcast_thread in hindcast_threads:
        hindcast_thread.join()
    print("Hindcast complete in {0:.1f} seconds.".format(time.time() - starttime))


def hindcast_product(env, params, wkt, download_method, auth, download_request, l1_product_path, l2_path, semaphores):
    # download products, which are not yet available
    if not os.path.exists(l1_product_path):
        with semaphores['download']:
            download_method(auth, download_request, l1_product_path)

    with semaphores['processing']:
        # FOR S3 MAKE SURE THE NON-DEFAULT S3TBX SETTING IS SELECTED IN THE SNAP PREFERENCES!
        if "OLCI" == params['General']['sensor']:
            product = ProductIO.readProduct(l1_product_path)
            if 'PixelGeoCoding2' not in str(product.getSceneGeoCoding()):
                raise RuntimeError("Pixelwise geocoding is not activated for S3TBX, please check the settings in SNAP!")
            product.closeIO()

        # process the products
        gpt, product_name = env['General']['gpt_path'], os.path.basename(l1_product_path)
        sensor, resolution = params['General']['sensor'], params['General']['resolution']
        if "IDEPIX" in params['General']['preprocessor'].split(","):
            from processors.idepix import idepix
            l1p = idepix.process(gpt, wkt, l1_product_path, product_name, l2_path, sensor, resolution, params)
        if "C2RCC" in params['General']['processors'].split(","):
            from processors.c2rcc import c2rcc
            l2c2rcc = c2rcc.process(gpt, wkt, l1p, product_name, l2_path, sensor, params)
        if "POLYMER" in params['General']['processors'].split(","):
            from processors.polymer import polymer
            l2poly = polymer.process(gpt, wkt, l1_product_path, l1p, product_name, l2_path, sensor, resolution, params,
                                     env['GSW']['root_path'], env['CDS']['root_path'])
        if "MPH" in params['General']['processors'].split(","):
            from processors.mph import mph
            l2mph = mph.process(gpt, wkt, l1p, product_name, l2_path, sensor, params)

    # apply adapters
    if "DATALAKES" in params['General']['adapters'].split(","):
        from adapters import datalakes
        if "C2RCC" == params['DATALAKES']['input_processor']:
            date = re.findall(r"\d{8}T\d{6}", os.path.basename(l2c2rcc))[0]
            datalakes.apply(env, params['General']['wkt'].split('.')[0], date, l2c2rcc, params)
        if "POLYMER" == params['DATALAKES']['input_processor']:
            date = re.findall(r"\d{8}T\d{6}", os.path.basename(l2poly))[0]
            datalakes.apply(env, params['General']['wkt'].split('.')[0], date, l2poly, params)
        if "MPH" == params['DATALAKES']['input_processor']:
            date = re.findall(r"\d{8}T\d{6}", os.path.basename(l2mph))[0]
            datalakes.apply(env, params['General']['wkt'].split('.')[0], date, l2mph, params)
