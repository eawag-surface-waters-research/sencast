#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
EO data access - CREODIAS API
"""

import os
import time
import boto3
import shutil
import requests
import subprocess
from tqdm import tqdm
from pathlib import Path
from zipfile import ZipFile
from requests.status_codes import codes
import requests_cache
from utils.auxil import log
from utils.product_fun import get_satellite_name_from_product_name

# Documentation
# https://creodias.docs.cloudferro.com/en/latest/eodata/EOData-Catalogue-API-Manual-on-Creodias.html

search_address = "https://datahub.creodias.eu/odata/v1/Products{}"

download_address = "https://zipper.creodias.eu/download/{}?token={}"

token_address = 'https://identity.cloudferro.com/auth/realms/Creodias-new/protocol/openid-connect/token'


def get_download_requests(auth, start_date, completion_date, sensor, resolution, wkt, env):
    query = "?$filter=((ContentDate/Start ge {} and ContentDate/Start le {}) and (Online eq true) and (OData.CSC.Intersects(Footprint=geography'SRID=4326;{}')) and (((((((Attributes/OData.CSC.StringAttribute/any(i0:i0/Name eq 'productType' and i0/Value eq '{}')))) and (Collection/Name eq '{}'))))))&$expand=Attributes&$top={}"
    max_records = 1000
    geometry = wkt.replace(" ", "", 1).strip()
    satellite, product_type = get_dataset_id(sensor, resolution)
    query = query.format(start_date, completion_date, geometry, product_type, satellite, max_records)
    products = search(satellite, query, env)
    products = timeliness_filter(products)
    return products


def search(satellite, query, env):
    log(env["General"]["log"], "Search for products: {}".format(query))
    requests_cache.install_cache(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache"),
                                 backend='sqlite', expire_after=3600, allowable_methods=('GET', 'POST'))
    products = []
    url = search_address.format(query)
    while True:
        log(env["General"]["log"], "Calling: {}".format(url), indent=1)
        response = requests.get(url)
        if response.status_code == codes.OK:
            root = response.json()
            for feature in root['value']:
                timeliness = ""
                if "_NR_" in feature['Name']:
                    timeliness = "NR"
                if "_ST_" in feature['Name']:
                    timeliness = "ST"
                if "_NT_" in feature['Name']:
                    timeliness = "NT"
                product_creation = ""
                if satellite == "SENTINEL-3":
                    product_creation = feature['Name'].split("_")[9]
                products.append({
                    "uuid": feature['Id'],
                    "s3": feature['S3Path'],
                    "name": feature['Name'],
                    "sensing_start": feature['ContentDate']['Start'],
                    "sensing_end": feature['ContentDate']['End'],
                    "timeliness": timeliness,
                    "product_creation": product_creation,
                    "satellite": get_satellite_name_from_product_name(feature['Name'])
                })
            if "@odata.nextLink" in root:
                log(env["General"]["log"], "Number of products exceeded max records, requesting addition records", indent=1)
                url = root["@odata.nextLink"]
            else:
                return products
        else:
            raise RuntimeError("Unexpected response: {}".format(response.text))


def timeliness_filter(products):
    products_filtered, positions = [], []
    for i in range(len(products)):
        curr_pos = (products[i]["sensing_start"], products[i]["sensing_end"])
        if curr_pos in positions:
            curr_proj_idx = positions.index(curr_pos)
            if ((products[i]["timeliness"] == 'Non Time Critical' and products_filtered[curr_proj_idx]["timeliness"] == 'Near Real Time')
                    or (products[i]["timeliness"] == 'T1' and products_filtered[curr_proj_idx]["timeliness"] == 'RT')):
                products_filtered[curr_proj_idx] = products[i]
                positions[curr_proj_idx] = (products[i]["sensing_start"], products[i]["sensing_end"])
            elif (products[i]["timeliness"] == 'Near Real Time' and products_filtered[curr_proj_idx]["timeliness"] == 'Non Time Critical') or (products[i]["timeliness"] == 'RT' and products_filtered[curr_proj_idx]["timeliness"] == 'T1'):
                continue
            else:
                products_filtered.append(products[i])
                positions.append((products[i]["sensing_start"], products[i]["sensing_end"]))
        else:
            products_filtered.append(products[i])
            positions.append((products[i]["sensing_start"], products[i]["sensing_end"]))
    return products_filtered


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
        return 'LANDSAT-8-ESA', 'L1TP'
    else:
        raise RuntimeError("CREODIAS API is not yet implemented for sensor: {}".format(sensor))


def do_download(auth, product, env, max_attempts=4, wait_time=30, bucket_name="DIAS"):
    uuid = product["uuid"]
    product_path = product["l1_product_path"]
    s3_key = product["s3"]
    os.makedirs(os.path.dirname(product_path), exist_ok=True)
    for attempt in range(max_attempts):
        if "s3" in env["CREODIAS"] and env["CREODIAS"]["s3"].lower() == "true":
            log(env["General"]["log"], "Starting S3 download attempt {} of {}".format(attempt + 1, max_attempts), indent=1)
            folder_temp = "{}.incomplete".format(product_path)
            try:
                s3 = boto3.resource('s3',
                                    aws_access_key_id=env["CREODIAS"]["access_key"],
                                    aws_secret_access_key=env["CREODIAS"]["secret_key"],
                                    endpoint_url=env["CREODIAS"]["host"], )
                bucket = s3.Bucket(bucket_name)
                prefix = s3_key.replace("/eodata/", "")
                objects = [o.key for o in bucket.objects.filter(Prefix=prefix) if not o.key.endswith("/")]
                for i in range(len(objects)):
                    print("Downloading sub-file {} ({}/{})".format(os.path.basename(objects[i]), i + 1, len(objects)))
                    local_path = folder_temp + objects[i].replace(prefix, "")
                    os.makedirs(os.path.dirname(local_path), exist_ok=True)
                    bucket.download_file(objects[i], local_path)
                shutil.move(folder_temp, product_path)
                log(env["General"]["log"], "Download complete", indent=1)
                return
            except Exception as e:
                log(env["General"]["log"],
                    "Failed S3 download attempt {} of {}: {}".format(attempt + 1, max_attempts, e), indent=1)
                try:
                    if os.path.exists(product_path):
                        shutil.rmtree(product_path)
                    if os.path.exists(folder_temp):
                        Path(folder_temp).unlink()
                except:
                    pass
                time.sleep(wait_time)
        else:
            log(env["General"]["log"], "Starting API download attempt {} of {}".format(attempt + 1, max_attempts), indent=1)
            file_temp = "{}.incomplete".format(product_path)
            try:
                token = server_authenticate(auth, env)
                url = download_address.format(uuid, token)
                downloaded_bytes = 0
                with requests.get(url, stream=True, timeout=600) as req:
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
                Path(file_temp).unlink()
                return
            except Exception as e:
                log(env["General"]["log"], "Failed download attempt {} of {}: {}".format(attempt + 1, max_attempts, e), indent=1)
                try:
                    if os.path.exists(product_path):
                        shutil.rmtree(product_path)
                    if os.path.exists(file_temp):
                        Path(file_temp).unlink()
                except:
                    pass
                time.sleep(wait_time)
    raise ValueError("Failed to download file after {} attempts".format(max_attempts))


def authenticate(env):
    return [env['username'], env['password'], env['totp_key']]


def server_authenticate(auth, env, max_attempts=5, wait_time=5):
    username, password, totp_key = auth
    for attempt in range(max_attempts):
        try:
            totp = get_totp(totp_key)
            token = get_token(username, password, totp)
            log(env["General"]["log"], "Authentication successful.", indent=2)
            return token
        except Exception as e:
            log(env["General"]["log"], "Failed to authenticate (Attempt {} of {}): {}".format(attempt + 1, max_attempts, e), indent=2)
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
