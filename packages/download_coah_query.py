#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os

from threading import Semaphore, Thread

from packages import coah_api
from packages.auxil import load_wkt


def start_download_threads(env, params, max_parallel_downloads=2):
    basic_auth = coah_api.get_auth(env['COAH']['username'], env['COAH']['password'])
    sensor, resolution = params['General']['sensor'], params['General']['resolution']
    start, end = params['General']['start'], params['General']['end']
    wkt = load_wkt(os.path.join(env['DIAS']['wkt_path'], params['General']['wkt']))
    uuids, product_names = find_products_to_download(basic_auth, sensor, resolution, start, end, wkt)
    print("Found {} product(s)".format(len(uuids)))

    # Spawn download threads for products which are not yet available (locally)
    product_paths_available, product_paths_to_download = [], []
    semaphore, download_threads = Semaphore(max_parallel_downloads), []
    for uuid, product_name in zip(uuids, product_names):
        product_path = os.path.join(env['DIAS']['l1_path'].format(params['General']['sensor']), product_name)
        if os.path.exists(product_path):
            product_paths_available.append(product_path)
        else:
            product_paths_to_download.append(product_path)
            download_threads.append(Thread(target=do_download, args=(basic_auth, uuid, product_path, semaphore)))
            download_threads[-1].start()

    return product_paths_available, product_paths_to_download, download_threads


def find_products_to_download(basic_auth, sensor, resolution, start, end, wkt):
    if sensor == 'OLCI' and resolution == '1000':
        datatype = 'OL_1_ERR___'
    elif sensor == 'OLCI' and resolution != '1000':
        datatype = 'OL_1_EFR___'
    elif sensor == 'MSI':
        datatype = 'S2MSI1C'
    else:
        raise RuntimeError("Unknown sensor: {}".format(sensor))

    query = "instrumentshortname:{}+AND+producttype:{}+AND+beginPosition:[{}+TO+{}]+AND+footprint:\"Intersects({})\""
    query = query.format(sensor.lower(), datatype, start, end, wkt)

    return coah_api.search(basic_auth, query)


def do_download(basic_auth, uuid, product_path, semaphore=None):
    if semaphore:
        with semaphore:
            coah_api.download(basic_auth, uuid, product_path)
    else:
        coah_api.download(basic_auth, uuid, product_path)
