#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os

from threading import Semaphore, Thread

from packages import coah_api


def start_download_threads(params, outdir, max_parallel_downloads=2):
    uuids, product_names = find_products_to_download(params)
    print("Found {} product(s)".format(len(uuids)))

    # Spawn download threads for products which are not yet available (locally)
    product_paths_available, product_paths_to_download = [], []
    semaphore, download_threads = Semaphore(max_parallel_downloads), []
    basic_auth = coah_api.get_auth(params['username'], params['password'])
    for uuid, product_name in zip(uuids, product_names):
        if os.path.exists(os.path.join(outdir, product_name)):
            product_paths_available.append(os.path.join(outdir, product_name))
        else:
            product_paths_to_download.append(os.path.join(outdir, product_name))
            download_threads.append(Thread(target=do_download, args=(basic_auth, uuid, product_paths_to_download[-1], len(download_threads) + 1, semaphore)))
            download_threads[-1].start()

    return product_paths_available, product_paths_to_download, download_threads


def find_products_to_download(params):
    if params['sensor'].upper() == 'OLCI' and params['resolution'].upper() == '1000':
        datatype = 'OL_1_ERR___'
    elif params['sensor'].upper() == 'OLCI' and params['resolution'].upper() != '1000':
        datatype = 'OL_1_EFR___'
    elif params['sensor'].upper() == 'MSI':
        datatype = 'S2MSI1C'
    else:
        raise RuntimeError("Unknown sensor: {}".format(params["sensor"]))

    query = "instrumentshortname:{}+AND+producttype:{}+AND+beginPosition:[{}+TO+{}]+AND+footprint:\"Intersects({})\""
    query = query.format(params['sensor'].lower(), datatype, params['start'], params['end'], params['wkt'])

    basic_auth = coah_api.get_auth(params['username'], params['password'])
    return coah_api.search(basic_auth, query)


def do_download(basic_auth, uuid, product_path, count, semaphore=None):
    if semaphore:
        with semaphore:
            coah_api.download(basic_auth, uuid, product_path)
    else:
        coah_api.download(basic_auth, uuid, product_path)
    print("Product {} downloaded.".format(count), end="\r")
