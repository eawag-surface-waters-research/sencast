#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import time

from requests.auth import HTTPBasicAuth
from snappy import ProductIO
from threading import Semaphore, Thread

from packages.auxil import init_hindcast

# download apis, processors, and adapters are imported dynamically to make hindcast also work on systems,
# where some of them might not be available


def hindcast(params_file, env_file=None, wkt_file=None, max_parallel_downloads=1, max_parallel_processing=1):
    # read env, params, and wkt file and copy files for reproducibility to l2_path
    env, params, wkt, l1_path, l2_path = init_hindcast(env_file, params_file, wkt_file)

    # do_hindcast(env, params, wkt, l2_path)
    do_hindcast2(env, params, wkt, l1_path, l2_path, max_parallel_downloads, max_parallel_processing)


def do_hindcast2(env, params, wkt, l1_path, l2_path, max_parallel_downloads=1, max_parallel_processing=1):
    # decide which API to use
    if env['General']['API'] == "COAH":
        from diasapis.coah_api import get_download_requests, do_download
    elif env['General']['API'] == "HDA":
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
        gpt, gpt_xml_path = env['General']['gpt_path'], env['General']['gpt_xml_path']
        product_name = os.path.basename(l1_product_path)
        sensor, resolution = params['General']['sensor'], params['General']['resolution']
        l2_product_path = {}
        if "IDEPIX" in params['General']['preprocessor'].split(","):
            from processors import idepix
            l1m = idepix.process(gpt, gpt_xml_path, wkt, l1_product_path, product_name, l2_path, sensor, resolution, params['IDEPIX'])
            l2_product_path['l1m'] = l1m
        if "C2RCC" in params['General']['processors'].split(","):
            from processors import c2rcc
            l2c2rcc = c2rcc.process(gpt, gpt_xml_path, wkt, l1m, product_name, l2_path, sensor, params['C2RCC'])
            l2_product_path['l2c2rcc'] = l2c2rcc
        if "POLYMER" in params['General']['processors'].split(","):
            from processors import polymer
            gsw_path = os.path.join(env['GSW']['gsw_path'])
            l2poly = polymer.process(gpt, gpt_xml_path, wkt, l1_product_path, l1m, product_name, l2_path, sensor, resolution, params['POLY'], gsw_path)
            l2_product_path['l2poly'] = l2poly
        if "MPH" in params['General']['processors'].split(","):
            from processors import mph
            l2mph = mph.process(gpt, gpt_xml_path, wkt, l1m, product_name, l2_path, sensor, params['MPH'])
            l2_product_path['l2mph'] = l2mph

    # apply adapters
    if "datalakes" in params['General']['adapters'].split(","):
        from adapters import datalakes
        date = re.findall(r"\d{8}T\d{6}", os.path.basename(l2_product_path['l2poly']))[0]
        datalakes.apply(env, params['General']['wkt'].split('.')[0], date, l2_product_path['l2poly'])
