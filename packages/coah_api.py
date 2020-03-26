#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
from zipfile import ZipFile
import requests
from requests.auth import HTTPBasicAuth
from requests.status_codes import codes
import xml.etree.ElementTree as ElementTree


# HDA-API endpoint address
api_endpoint = "https://scihub.copernicus.eu/dhus"
# search address
search_address = api_endpoint + "/search?q={}&start={}&rows={}"
# download address
download_address = api_endpoint + "/odata/v1/Products('{}')/$value"


def get_auth(username, password):
    return HTTPBasicAuth(username, password)


def search(basic_auth, query):
    print("Search for products: {}".format(query))
    uuids, filenames = [], []
    start, rows = 0, 100
    while True:
        response = requests.get(search_address.format(query, start, rows), auth=basic_auth)
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


def download(basic_auth, uuid, filename):
    response = requests.get(download_address.format(uuid), auth=basic_auth, stream=True)
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
