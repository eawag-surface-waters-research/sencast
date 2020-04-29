#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import requests

from requests.status_codes import codes
from xml.etree import ElementTree
from zipfile import ZipFile


# HDA-API endpoint address
api_endpoint = "https://scihub.copernicus.eu/dhus"
# search address
search_address = api_endpoint + "/search?q={}&start={}&rows={}"
# download address
download_address = api_endpoint + "/odata/v1/Products('{}')/$value"


def get_download_requests(auth, start, end, sensor, resolution, wkt):
    query = "instrumentshortname:{}+AND+producttype:{}+AND+beginPosition:[{}+TO+{}]+AND+footprint:\"Intersects({})\""
    datatype = get_dataset_id(sensor, resolution)
    query = query.format(sensor.lower(), datatype, start, end, wkt)
    uuids, product_names = search(auth, query)
    return [{'uuid': uuid} for uuid in uuids], product_names


def do_download(auth, download_request, product_path):
    download(auth, download_request['uuid'], product_path)


def get_dataset_id(sensor, resolution):
    if sensor == 'OLCI' and int(resolution) < 1000:
        return 'OL_1_EFR___'
    elif sensor == 'OLCI' and int(resolution) >= 1000:
        return 'OL_1_ERR___'
    elif sensor == 'MSI':
        return 'S2MSI1C'
    else:
        raise RuntimeError("COAH API is not yet implemented for sensor: {}".format(sensor))


def search(auth, query):
    print("Search for products: {}".format(query))
    uuids, filenames = [], []
    start, rows = 0, 100
    while True:
        response = requests.get(search_address.format(query, start, rows), auth=auth)
        if response.status_code == codes.OK:
            root = ElementTree.fromstring(response.text)
            for entry in root.findall(prepend_ns("entry")):
                for str_property in entry.findall(prepend_ns("str")):
                    if str_property.attrib['name'] == "uuid":
                        uuids.append(str_property.text)
                    elif str_property.attrib['name'] == "filename":
                        filenames.append(str_property.text)
            has_next_page = False
            for link in root.findall(prepend_ns('link')):
                if link.attrib['rel'] == "next":
                    start = start + rows
                    has_next_page = True
            if not has_next_page:
                return uuids, filenames
        else:
            raise RuntimeError("Unexpeted response: {}".format(response.text))


def download(auth, uuid, filename):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    response = requests.get(download_address.format(uuid), auth=auth, stream=True)
    if response.status_code == codes.OK:
        with open(filename + '.zip', 'wb') as down_stream:
            for chunk in response.iter_content(chunk_size=65536):
                down_stream.write(chunk)
        with ZipFile(filename + '.zip', 'r') as zip_file:
            zip_file.extractall(os.path.dirname(filename))
        os.remove(filename + '.zip')
    else:
        print("Unexpected response on download request: {}".format(response.text))


def prepend_ns(s):
    return '{http://www.w3.org/2005/Atom}' + s


def prepend_os(s):
    return '{http://a9.com/-/spec/opensearch/1.1/}' + s
