#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
EO data access - CREODIAS API
"""

import os
import time
import requests
import subprocess
from tqdm import tqdm
from pathlib import Path
from zipfile import ZipFile
from requests.status_codes import codes

from utils.auxil import log

# Documentation
# https://creodias.docs.cloudferro.com/en/latest/eodata/EOData-Catalogue-API-Manual-on-Creodias.html

search_address = "https://datahub.creodias.eu/odata/v1/Products{}"

download_address = "https://zipper.creodias.eu/download/{}?token={}"

token_address = 'https://identity.cloudferro.com/auth/realms/Creodias-new/protocol/openid-connect/token'


def get_download_requests(auth, startDate, completionDate, sensor, resolution, wkt, env):
    query = "?$filter=((ContentDate/Start ge {} and ContentDate/Start le {}) and (Online eq true) and (OData.CSC.Intersects(Footprint=geography'SRID=4326;{}')) and (((((((Attributes/OData.CSC.StringAttribute/any(i0:i0/Name eq 'productType' and i0/Value eq '{}')))) and (Collection/Name eq '{}'))))))&$expand=Attributes&$top={}"
    maxRecords = 1000
    geometry = wkt.replace(" ", "", 1)
    satellite, productType = get_dataset_id(sensor, resolution)
    query = query.format(startDate, completionDate, geometry, productType, satellite, maxRecords)
    uuids, product_names, timelinesss, beginpositions, endpositions = search(satellite, query, env)
    uuids, product_names = timeliness_filter(uuids, product_names, timelinesss, beginpositions, endpositions)
    return [{'uuid': uuid} for uuid in uuids], product_names


def search(satellite, query, env):
    log(env["General"]["log"], "Search for products: {}".format(query))
    uuids, filenames = [], []
    timelinesss, beginpositions, endpositions = [], [], []
    log(env["General"]["log"], "Calling: {}".format(search_address.format(query)), indent=1)
    while True:
        response = requests.get(search_address.format(query))
        if response.status_code == codes.OK:
            root = response.json()
            for feature in root['value']:
                uuids.append(feature['Id'])
                filenames.append(feature['Name'])
                beginpositions.append(feature['ContentDate']['Start'])
                endpositions.append(feature['ContentDate']['End'])
                timeliness = ""
                if "_NR_" in feature['Name']:
                    timeliness = "NR"
                if "_ST_" in feature['Name']:
                    timeliness = "ST"
                if "_NT_" in feature['Name']:
                    timeliness = "NT"
                timelinesss.append(timeliness)
            return uuids, filenames, timelinesss, beginpositions, endpositions
        else:
            raise RuntimeError("Unexpected response: {}".format(response.text))


def timeliness_filter(uuids, product_names, timelinesss, beginpositions, endpositions):
    num_products = len(uuids)
    uuids_filtered, product_names_filtered, positions, timelinesss_filtered = [], [], [], []
    for i in range(num_products):
        curr_pos = (beginpositions[i], endpositions[i])
        if curr_pos in positions:
            curr_proj_idx = positions.index(curr_pos)
            if (timelinesss[i] == 'Non Time Critical' and timelinesss_filtered[curr_proj_idx] == 'Near Real Time') or (timelinesss[i] == 'T1' and timelinesss_filtered[curr_proj_idx] == 'RT'):
                timelinesss_filtered[curr_proj_idx] = timelinesss[i]
                uuids_filtered[curr_proj_idx] = uuids[i]
                product_names_filtered[curr_proj_idx] = product_names[i]
                positions[curr_proj_idx] = (beginpositions[i], endpositions[i])
            elif (timelinesss[i] == 'Near Real Time' and timelinesss_filtered[curr_proj_idx] == 'Non Time Critical') or (timelinesss[i] == 'RT' and timelinesss_filtered[curr_proj_idx] == 'T1'):
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


def get_dataset_id(sensor, resolution):
    if sensor == 'OLCI' and int(resolution) < 1000:
        return 'SENTINEL-3', 'OL_1_EFR___'
    elif sensor == 'OLCI' and int(resolution) >= 1000:
        return 'SENTINEL-3', 'OL_1_ERR___'
    elif sensor == 'MSI':
        return 'SENTINEL-2', 'S2MSI1C'
    elif sensor == 'MSI-L2A':
        return 'SENTINEL-2', 'S2MSI2A'
    elif sensor == 'OLI_TIRS':
        return 'LANDSAT-8', 'L1TP'
    else:
        raise RuntimeError("CREODIAS API is not yet implemented for sensor: {}".format(sensor))


def do_download(auth, download_request, product_path, env):
    token = server_authenticate(auth, env)
    os.makedirs(os.path.dirname(product_path), exist_ok=True)
    url = download_address.format(download_request['uuid'], token)
    file_temp = "{}.incomplete".format(product_path)
    try:
        downloaded_bytes = 0
        with requests.get(url, stream=True, timeout=100) as req:
            if int(req.status_code) > 400:
                raise ValueError("{} ERROR. {}".format(req.status_code, req.json()))
            with tqdm(unit='B', unit_scale=True, disable=not True) as progress:
                chunk_size = 2 ** 20  # download in 1 MB chunks
                with open(file_temp, 'wb') as fout:
                    for chunk in req.iter_content(chunk_size=chunk_size):
                        if chunk:  # filter out keep-alive new chunks
                            fout.write(chunk)
                            progress.update(len(chunk))
                            downloaded_bytes += len(chunk)
        with ZipFile(file_temp, 'r') as zip_file:
            zip_file.extractall(os.path.dirname(product_path))
    finally:
        try:
            Path(file_temp).unlink()
        except OSError:
            pass


def authenticate(env):
    return [env['username'], env['password'], env['totp_key']]


def server_authenticate(auth, env, max_attempts=5, wait_time=5):
    username, password, totp_key = auth
    for attempt in range(max_attempts):
        try:
            totp = get_totp(totp_key)
            token = get_token(username, password, totp)
            return token
        except Exception as e:
            log(env["General"]["log"], "Failed to authenticate (Attempt {} of {}): {}".format(attempt + 1, max_attempts, e), indent=1)
            time.sleep(wait_time)
    raise RuntimeError(f'Unable to authenticate with the CREODIAS server.')


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
    response = requests.post(token_address, data=token_data).json()
    try:
        return response['access_token']
    except KeyError:
        raise RuntimeError(response)
