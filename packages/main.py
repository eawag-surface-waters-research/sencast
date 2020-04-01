#! /usr/bin/env python
# -*- coding: utf-8 -*-
import os
import time

from packages.auxil import init_hindcast
from packages.background_processing import start_processing_threads


def hindcast(params_file, env_file=None, wkt_file=None):
    # Init out_path with params and wkt file
    env, params, wkt, out_path = init_hindcast(env_file, params_file, wkt_file)

    do_hindcast(env, params, wkt, out_path)


def do_hindcast(env, params, wkt, out_path):
    # Removes SEVERE message in gpt log
    os.environ['LD_LIBRARY_PATH'] = "."

    # Download products
    print("Starting download threads using {}".format(env['General']['API']))
    if env['General']['API'] == "COAH":
        from packages.download_coah_query import start_download_threads
    elif env['General']['API'] == "HDA":
        from packages.download_hda_query import start_download_threads
    else:
        raise RuntimeError("Unknown API: {} (possible options are 'HDA' or 'COAH').".format(env['General']['API']))
    product_paths_available, product_paths_to_download, download_threads = start_download_threads(env, params, wkt)
    print("{} products are already available.".format(len(product_paths_available)))
    print("{} products are being downloaded by individual threads.".format(len(product_paths_to_download)))

    # Process products
    starttime = time.time()
    processing_threads = start_processing_threads(env, params, wkt, out_path, product_paths_available, product_paths_to_download, download_threads)
    print("Start processing of the products by indivitual threads. Some products may still be downloading.")
    for processing_thread in processing_threads:
        processing_thread.join()
    print("Processing complete in {0:.1f} seconds.".format(time.time() - starttime))
