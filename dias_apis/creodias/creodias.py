#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
EO data access - CREODIAS API
"""

import os
import subprocess
from dias_apis import odata

# Documentation
# https://creodias.docs.cloudferro.com/en/latest/eodata/EOData-Catalogue-API-Manual-on-Creodias.html

api_name = "CREODIAS"

server_name = "CREODIAS"

search_address = "https://datahub.creodias.eu/odata/v1/Products{}"

download_address = "https://zipper.creodias.eu/download/{}?token={}"

token_address = 'https://identity.cloudferro.com/auth/realms/Creodias-new/protocol/openid-connect/token'

bucket_address = "https://eodata.cloudferro.com"

cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")


def get_download_requests(auth, start_date, end_date, sensor, resolution, wkt, env):
    return odata.get_download_requests(start_date, end_date, sensor, resolution, wkt, env, api_name, search_address,
                                       cache_path)


def do_download(auth, product, env, max_attempts=5, wait_time=30, bucket_name="eodata"):
    return odata.do_download(product, env, api_name, download_address, bucket_address,
                             get_token=lambda: server_authenticate(auth, env), token_in_url=True,
                             max_attempts=max_attempts, wait_time=wait_time, bucket_name=bucket_name)


def authenticate(env):
    return [env['username'], env['password'], env['totp_key']]


def server_authenticate(auth, env, max_attempts=5, wait_time=35):
    username, password, totp_key = auth
    return odata.server_authenticate(lambda: get_token(username, password, get_totp(totp_key)), env, server_name,
                                     max_attempts=max_attempts, wait_time=wait_time)


def get_totp(totp_key):
    totp = subprocess.check_output(["oathtool", "-b", "--totp", totp_key]).strip().decode('utf-8')
    return totp


def get_token(username, password, totp):
    token_data = {
        'client_id': 'CLOUDFERRO_PUBLIC',
        'username': username,
        'password': password,
        'grant_type': 'password',
        'totp': totp
    }
    return odata.request_token(token_address, token_data)
