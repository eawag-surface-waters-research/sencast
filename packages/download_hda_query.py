#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import concurrent.futures

from packages.auxil import list_xml_scene_dir
from packages import hda_api


def query_dl_hda(params, outdir, max_parallel_downloads=2):
    job_id, uris, filenames = find_products_to_download(params)

    if not uris:
        print("No products found.")
        return

    # Only download files which have not been downloaded yet
    uris_to_download, filenames_to_download = [], []
    for uri, filename in zip(uris, filenames):
        if filename not in os.listdir(outdir):
            uris_to_download.append(uri)
            filenames_to_download.append(filename)

    if not uris_to_download:
        print("All products already downloaded, skipping...")
        return

    # Spawn threads for downloads
    print("Downloading {} product(s)...".format(len(uris_to_download)))
    access_token = hda_api.get_access_token(params['username'], params['password'])
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel_downloads) as ex:
        for uri, filename in zip(uris_to_download, filenames_to_download):
            ex.submit(do_download, access_token, job_id, uri, os.path.join(outdir, filename))

    # Check if products were actually dowloaded:
    dirs_of_outdir = os.listdir(outdir)
    for filename in filenames_to_download:
        if filename not in dirs_of_outdir:
            print("\nDownload(s) failed, another user might be using COAH services with the same credentials. " +
                  "Either wait for the other user to finish their job or change the credentials in the parameter file.")
            return
    print("\nDownload(s) complete!")

    # Read products
    return list_xml_scene_dir(outdir, sensor=params['sensor'], file_list=filenames)


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
    uris, filenames = hda_api.get_datarequest_results(access_token, job_id)

    return job_id, uris, filenames


def do_download(access_token, job_id, uri, filename):
    order_id = hda_api.post_dataorder(access_token, job_id, uri)
    hda_api.wait_for_dataorder_to_complete(access_token, order_id)
    hda_api.dataorder_download(access_token, order_id, filename)
