#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Sencast uses the COAH API to query the image database in order to identify suitable images and also to download images.

Documentation for COAH API can be found `here. <https://scihub.copernicus.eu/twiki/do/view/SciHubUserGuide/BatchScripting?redirectedfrom=SciHubUserGuide.8BatchScripting>`_
"""

import os
import requests
from requests.auth import HTTPBasicAuth

from requests.status_codes import codes
from xml.etree import ElementTree
from zipfile import ZipFile
from utils.auxil import log

# Documentation for COAH API can be found here:
# https://scihub.copernicus.eu/twiki/do/view/SciHubUserGuide/BatchScripting?redirectedfrom=SciHubUserGuide.8BatchScripting

# HDA-API endpoint address
api_endpoint = "https://scihub.copernicus.eu/dhus"
# search address
search_address = api_endpoint + "/search?q={}&start={}&rows={}"
# download address
download_address = api_endpoint + "/odata/v1/Products('{}')/$value"


def authenticate(env):
    return HTTPBasicAuth(env['username'], env['password'])


def get_download_requests(auth, start, end, sensor, resolution, wkt, env):
    query = "instrumentshortname:{}+AND+producttype:{}+AND+beginPosition:[{}+TO+{}]+AND+footprint:\"Intersects({})\""
    datatype = get_dataset_id(sensor, resolution)
    query = query.format(sensor.lower(), datatype, start, end, wkt)
    uuids, product_names, timelinesss, beginpositions, endpositions = search(auth, query, env)
    uuids, product_names = timeliness_filter(uuids, product_names, timelinesss, beginpositions, endpositions)
    return [{'uuid': uuid} for uuid in uuids], product_names


def do_download(auth, download_request, product_path, env):
    download(auth, download_request['uuid'], product_path, env)


def get_dataset_id(sensor, resolution):
    if sensor == 'OLCI' and int(resolution) < 1000:
        return 'OL_1_EFR___'
    elif sensor == 'OLCI' and int(resolution) >= 1000:
        return 'OL_1_ERR___'
    elif sensor == 'MSI':
        return 'S2MSI1C'
    else:
        raise RuntimeError("COAH API is not yet implemented for sensor: {}".format(sensor))


def timeliness_filter(uuids, product_names, timelinesss, beginpositions, endpositions):
    num_products = len(uuids)
    uuids_filtered, product_names_filtered, positions, timelinesss_filtered = [], [], [], []
    if len(timelinesss) == num_products:
        for i in range(num_products):
            curr_pos = (beginpositions[i], endpositions[i])
            if curr_pos in positions:
                curr_proj_idx = positions.index(curr_pos)
                if timelinesss[i] == 'Non Time Critical' and timelinesss_filtered[curr_proj_idx] == 'Near Real Time':
                    timelinesss_filtered[curr_proj_idx] = timelinesss[i]
                    uuids_filtered[curr_proj_idx] = uuids[i]
                    product_names_filtered[curr_proj_idx] = product_names[i]
                    positions[curr_proj_idx] = (beginpositions[i], endpositions[i])
                elif timelinesss[i] == 'Near Real Time' and timelinesss_filtered[curr_proj_idx] == 'Non Time Critical':
                    continue
                else:
                    timelinesss_filtered.append(timelinesss[i])
                    uuids_filtered.append(uuids[i])
                    product_names_filtered.append(product_names[i])
                    positions.append((beginpositions[i], endpositions[i]))
            else:
                timelinesss_filtered.append(timelinesss[i])
                uuids_filtered.append(uuids[i])
                product_names_filtered.append(product_names[i])
                positions.append((beginpositions[i], endpositions[i]))
        return uuids_filtered, product_names_filtered
    else:
        return uuids, product_names


def search(auth, query, env):
    log(env["General"]["log"], "Search for products: {}".format(query))
    uuids, filenames = [], []
    timelinesss, beginpositions, endpositions = [], [], []
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
                    elif str_property.attrib['name'] == "timeliness":
                        timelinesss.append(str_property.text)
                for date_property in entry.findall(prepend_ns("date")):
                    if date_property.attrib['name'] == "beginposition":
                        beginpositions.append(date_property.text)
                    elif date_property.attrib['name'] == "endposition":
                        endpositions.append(date_property.text)
            has_next_page = False
            for link in root.findall(prepend_ns('link')):
                if link.attrib['rel'] == "next":
                    start = start + rows
                    has_next_page = True
            if not has_next_page:
                return uuids, filenames, timelinesss, beginpositions, endpositions
        else:
            raise RuntimeError("Unexpeted response: {}".format(response.text))


def download(auth, uuid, filename, env):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    log(env["General"]["log"], ("Downloading file from {}.".format(download_address.format(uuid)))
    response = requests.get(download_address.format(uuid), auth=auth, stream=True)
    if response.status_code == codes.OK:
        with open(filename + '.zip', 'wb') as down_stream:
            for chunk in response.iter_content(chunk_size=2**20):
                down_stream.write(chunk)
        with ZipFile(filename + '.zip', 'r') as zip_file:
            zip_file.extractall(os.path.dirname(filename))
        os.remove(filename + '.zip')
    else:
        log(env["General"]["log"], ("Unexpected response (HTTP {}) on download request: {}".format(response.status_code, response.text))


def prepend_ns(s):
    return '{http://www.w3.org/2005/Atom}' + s


def prepend_os(s):
    return '{http://a9.com/-/spec/opensearch/1.1/}' + s
