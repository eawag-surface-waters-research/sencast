#! /usr/bin/env python
# -*- coding: utf-8 -*-
import os
import platform
import time

from packages.auxil import load_environment, load_params
from packages.background_processing import start_processing_threads
from packages.download_coah_query import start_download_threads as start_download_threads_c
from packages.download_hda_query import start_download_threads as start_download_threads_h

# Removes SEVERE message in gpt log


def hindcast(params, env=None):

    if not env:
        env = load_environment()
    elif isinstance(env, str):
        env = load_environment(env)

    if isinstance(params, str):
        params = load_params(params, env['General']['params_path'])

    # *********************************************************
    # Download products
    # *********************************************************
    print("Starting download threads using {}".format(env['General']['API']))
    if env['General']['API'] == "COAH":
        product_paths_available, product_paths_to_download, download_threads = start_download_threads_c(env, params)
    elif env['General']['API'] == "HDA":
        product_paths_available, product_paths_to_download, download_threads = start_download_threads_h(env, params)
    else:
        raise RuntimeError("Unknown API: {} (possible options are 'HDA' or 'COAH').".format(env['General']['API']))
    print("{} products are already available.".format(len(product_paths_available)))
    print("{} products are being downloaded by individual threads.".format(len(product_paths_to_download)))

    # *********************************************************
    # Processing
    # *********************************************************
    starttime = time.time()
    processing_threads = start_processing_threads(env, params, product_paths_available, product_paths_to_download, download_threads)
    print("Started processing of the products by indivitual threads. Some products may still be downloading.")
    for processing_thread in processing_threads:
        processing_thread.join()
    print("Processing complete in {0:.1f} seconds.".format(time.time() - starttime))
