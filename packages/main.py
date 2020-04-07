#! /usr/bin/env python
# -*- coding: utf-8 -*-
import os
import time

from packages.adapters import start_adapter_threads
from packages.auxil import init_hindcast
from packages.background_processing import start_processing_threads


def hindcast(params_file, env_file=None, wkt_file=None):
    # read env, params and wkt file; create l2_path folder structure
    env, params, wkt, l2_path = init_hindcast(env_file, params_file, wkt_file)

    do_hindcast(env, params, wkt, l2_path)


def do_hindcast(env, params, wkt, l2_path):
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
    l1_product_paths, download_threads = start_download_threads(env, params, wkt)
    actual_downloads = len([t for t in download_threads if t.is_alive()])
    print("{} products are already available.".format(len(l1_product_paths) - actual_downloads))
    print("{} products are being downloaded by individual threads.".format(actual_downloads))

    # Process products
    print("Start processing of the products by indivitual threads. Some products may still be downloading.")
    starttime = time.time()
    l2_product_paths, processing_threads = start_processing_threads(env, params, wkt, l2_path, l1_product_paths, download_threads)

    # Apply adapters
    adapter_threads = start_adapter_threads(env, params, l2_product_paths, processing_threads)
    for adapter_thread in adapter_threads:
        adapter_thread.join()
    print("Processing complete in {0:.1f} seconds.".format(time.time() - starttime))
