#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
EO data access - COAH API
"""

import os
from dias_apis import odata

# Documentation
# https://documentation.dataspace.copernicus.eu/APIs/OData.html

api_name = "COAH"

server_name = "Copernicus Dataspace"

search_address = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products{}"

download_address = "https://zipper.dataspace.copernicus.eu/odata/v1/Products({})/$value"

token_address = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"

bucket_address = "https://eodata.dataspace.copernicus.eu"

cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")


def get_download_requests(auth, start_date, end_date, sensor, resolution, wkt, env):
    return odata.get_download_requests(start_date, end_date, sensor, resolution, wkt, env, api_name, search_address,
                                       cache_path)


def do_download(auth, product, env, max_attempts=5, wait_time=30, bucket_name="eodata"):
    return odata.do_download(product, env, api_name, download_address, bucket_address,
                             get_token=lambda: server_authenticate(auth, env), token_in_url=False,
                             max_attempts=max_attempts, wait_time=wait_time, bucket_name=bucket_name)


def authenticate(env):
    return [env['username'], env['password']]


def server_authenticate(auth, env, max_attempts=5, wait_time=5):
    username, password = auth
    return odata.server_authenticate(lambda: get_token(username, password), env, server_name,
                                     max_attempts=max_attempts, wait_time=wait_time)


def get_token(username, password):
    token_data = {
        'client_id': 'cdse-public',
        'username': username,
        'password': password,
        'grant_type': 'password',
    }
    return odata.request_token(token_address, token_data)
