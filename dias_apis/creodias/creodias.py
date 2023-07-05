#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Sencast uses the CREODIAS API to query the image database in order to identify suitable images and also to download images.

Documentation for CREODIAS API can be found `here. <https://creodias.eu/eo-data-finder-api-manual>`_
"""

import os
import requests
import subprocess

from requests.status_codes import codes
from tqdm import tqdm
from zipfile import ZipFile
from pathlib import Path
from utils.auxil import log

# Documentation for CREODIAS API can be found here:
# https://creodias.docs.cloudferro.com/en/latest/eodata/EOData-Catalogue-API-Manual-on-Creodias.html

# search address
search_address = "https://datahub.creodias.eu/odata/v1/Products{}"

# download address
download_address = "https://zipper.creodias.eu/download/{}?token={}"

# token address
token_address = 'https://identity.cloudferro.com/auth/realms/Creodias-new/protocol/openid-connect/token'


def authenticate(env):
    return [env['username'], env['password'], env['totp_key']]


def get_download_requests(auth, startDate, completionDate, sensor, resolution, wkt, env):
    query = "?$filter=((ContentDate/Start ge {} and ContentDate/Start le {}) and (Online eq true) and (OData.CSC.Intersects(Footprint=geography'SRID=4326;{}')) and (((((((Attributes/OData.CSC.StringAttribute/any(i0:i0/Name eq 'productType' and i0/Value eq '{}')))) and (Collection/Name eq '{}'))))))&$expand=Attributes&$top={}"
    maxRecords = 1000
    geometry = wkt.replace(" ", "", 1)
    satellite, productType = get_dataset_id(sensor, resolution)
    query = query.format(startDate, completionDate, geometry, productType, satellite, maxRecords)
    uuids, product_names, timelinesss, beginpositions, endpositions = search(satellite, query, env)
    uuids, product_names = timeliness_filter(uuids, product_names, timelinesss, beginpositions, endpositions)
    return [{'uuid': uuid} for uuid in uuids], product_names


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


def do_download(auth, download_request, product_path, env):
    username, password, totp_key = auth
    totp = get_totp(totp_key)
    token = get_token(username, password, totp)
    os.makedirs(os.path.dirname(product_path), exist_ok=True)
    url = download_address.format(download_request['uuid'], token)
    file_temp = "{}.incomplete".format(product_path)
    try:
        downloaded_bytes = 0
        with requests.get(url, stream=True, timeout=100) as req:
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


def parse_filename(filename):
    if "S3" in filename:
        satellite = "Sentinel-3"
        sensor = "OLCI"
        product = filename.split("____")[0].split("S3A_")[1]
        year, month, day = parse_date(filename.split("_")[7])
    elif "S2" in filename:
        satellite = "Sentinel-2"
        sensor = "MSI"
        product = "L1C"
        year, month, day = parse_date(filename.split("_")[2])
    else:
        return False
    return satellite, sensor, product, year, month, day


def parse_date(date):
    year = date[0:4]
    month = date[4:6]
    day = date[6:8]
    return year, month, day

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
        raise RuntimeError(f'Unable to get token. Response was {response}')
