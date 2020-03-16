#! /usr/bin/env python
# -*- coding: utf-8 -*-

import concurrent.futures
import os
from packages.auxil import list_xml_scene_dir
from packages import hda_api


def query_dl_hda(params, outdir, max_threads=2):
    job_id, uris, filenames, numberOfResults = find_products_to_download(params)

    if numberOfResults == 0:
        print("No products found.")
        return

    # Check if one of the files already downloaded
    uris_to_process = []
    filenames_to_process = []
    for i in range(len(filenames)):
        filename = filenames[i]
        if filename.split('.')[0] not in os.listdir(outdir):
            uris_to_process.append(uris[i])
            filenames_to_process.append(filename)

    if len(uris_to_process) == 0:
        print("All products already downloaded, skipping...")
        return

    # Spawn threads for downloads
    print("Downloading {} product(s)...".format(len(uris_to_process)))
    access_token = hda_api.get_access_token(params['username'], params['password'])
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as ex:
        for i in range(len(uris_to_process)):
            uri = uris_to_process[i]
            filename = filenames_to_process[i]
            ex.submit(do_download, access_token, job_id, uri, filename)
    print("Download complete.")

    # Read products
    xmlf = list_xml_scene_dir(outdir, sensor=params['sensor'], file_list=filenames)
    return xmlf


def find_products_to_download(params):
    if params["sensor"].upper() == "OLCI":
        dataset_id = "EO:EUM:DAT:SENTINEL-3:OL_1_EFR___"
        datarequest = {
            "datasetId": dataset_id,
            "boundingBoxValues": [
                {
                    "name": "bbox",
                    "bbox": [5.5, 48, 11, 45]
                 }
            ],
            "dateRangeSelectValues": [
                {
                    "name": "dtrange",
                    "start": params["start"],
                    "end": params["end"]
                }
            ],
            "stringChoiceValues": []
        }
    elif params["sensor"].upper() == "MSI":
        datarequest = "tofill"
    else:
        raise RuntimeError("Unknown sensor: " + params['sensor'])

    print("Step-1")
    access_token = hda_api.get_access_token(params['username'], params['password'])

    print("Step-2")
    hda_api.accept_tc_if_required(access_token)

    print("Step-3")
    job_id = hda_api.post_datarequest(access_token, datarequest)

    print("Step-4")
    hda_api.wait_for_datarequest_to_complete(access_token, job_id)

    print("Step-5")
    filenames, uris, numberOfResults = hda_api.get_datarequest_results(access_token, job_id)

    return job_id, uris, filenames, numberOfResults


def do_download(access_token, job_id, uri, filename):
    order_id = hda_api.post_dataorder(access_token, job_id, uri)
    hda_api.wait_for_dataorder_to_complete(access_token, order_id)
    hda_api.dataorder_download(access_token, order_id, filename)
