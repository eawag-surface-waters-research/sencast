#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os

from threading import Semaphore, Thread

from packages import hda_api
from packages.product_fun import get_lons_lats


def start_download_threads(env, params, wkt, max_parallel_downloads=2):
    print("Step-1")
    access_token = hda_api.get_access_token(env['HDA']['username'], env['HDA']['password'])
    start, end = params['General']['start'], params['General']['end']
    sensor, resolution = params['General']['sensor'], params['General']['resolution']
    job_id, (uris, product_names) = find_products_to_download(access_token, wkt, start, end, sensor, resolution)
    print("Found {} product(s)".format(len(uris)))

    l1_path = env['DIAS']['l1_path'].format(params['General']['sensor'])
    os.makedirs(l1_path, exist_ok=True)

    # Spawn download threads for products which are not yet available (locally)
    product_paths_available, product_paths_to_download = [], []
    semaphore, download_threads = Semaphore(max_parallel_downloads), []
    for uri, product_name in zip(uris, product_names):
        product_path = os.path.join(l1_path, product_name)
        if os.path.exists(product_path):
            product_paths_available.append(product_path)
        else:
            product_paths_to_download.append(product_path)
            download_threads.append(Thread(target=do_download, args=(access_token, job_id, uri, product_path, semaphore)))
            download_threads[-1].start()

    return product_paths_available, product_paths_to_download, download_threads


def find_products_to_download(access_token, wkt, start, end, sensor, resolution):
    if sensor == "OLCI":
        lons, lats = get_lons_lats(wkt)
        datarequest = {
            'datasetId': "EO:EUM:DAT:SENTINEL-3:OL_1_{}___".format("EFR" if resolution < 1000 else "ERR"),
            'boundingBoxValues': [{'name': "bbox", 'bbox': [min(lons), max(lats), max(lons), min(lats)]}],
            'dateRangeSelectValues': [{'name': "dtrange", 'start': start, 'end': end}],
            'stringChoiceValues': []
        }
    elif sensor == "MSI":
        datarequest = "tofill"
    else:
        raise RuntimeError("Unknown sensor: " + sensor)

    print("Step-2")
    hda_api.accept_tc_if_required(access_token)

    print("Step-3")
    job_id = hda_api.post_datarequest(access_token, datarequest)

    print("Step-4")
    hda_api.wait_for_datarequest_to_complete(access_token, job_id)

    print("Step-5")
    return job_id, hda_api.get_datarequest_results(access_token, job_id)


def do_download(access_token, job_id, uri, product_path):
    order_id = hda_api.post_dataorder(access_token, job_id, uri)
    hda_api.wait_for_dataorder_to_complete(access_token, order_id)
    hda_api.dataorder_download(access_token, order_id, product_path)
