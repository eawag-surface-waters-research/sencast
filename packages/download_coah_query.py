#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import concurrent.futures
import requests
from requests.auth import HTTPBasicAuth

from packages.auxil import list_xml_scene_dir
from packages import coah_api
from zipfile import ZipFile


def download(url, usr, pwd, count):
    sys.stdout.write("\033[K")
    dl_name = url.split("'")[1]

    response = requests.get(url, auth=HTTPBasicAuth(usr, pwd), stream=True)
    with open(dl_name + '.zip', 'wb') as down_stream:
        for chunk in response.iter_content(chunk_size=65536):
            down_stream.write(chunk)
    with ZipFile(dl_name + '.zip', 'r') as zip_file:
        prod_name = zip_file.namelist()[0]
        zip_file.extractall(prod_name.split('.')[0])
    os.remove(dl_name + '.zip')
    print("Product no. {} downloaded".format(count), end="\r")


def query_dl_coah(params, outdir, max_parallel_downloads=2):
    uuids, filenames = find_products_to_download(params)

    if not uuids:
        print("No products found.")
        return

    # Only download files which have not been downloaded yet
    uuids_to_download, filenames_to_download = [], []
    for uuid, filename in zip(uuids, filenames):
        if filename.split('.')[0] not in os.listdir(outdir):
            uuids_to_download.append(uuid)
            filenames_to_download.append(filename)

    if not uuids_to_download:
        print("All products already downloaded, skipping...")
        return

    # Spawn threads for downloads
    print("Downloading {} product(s)...".format(len(uuids_to_download)))
    basic_auth = coah_api.get_auth(params['username'], params['password'])
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel_downloads) as ex:
        for uuid, filename in zip(uuids_to_download, filenames_to_download):
            ex.submit(do_download, basic_auth, uuid, filename)

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


def do_download(basic_auth, uuid, filename):
    coah_api.download(basic_auth, uuid, filename)
