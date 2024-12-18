#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
EarthExplorer (EE) serves as a key data access portal for the USGS Earth Resources Observation and Science (EROS) data repository.
"""

import os
import json
import time
import shutil
import requests
from datetime import datetime
from numpy.core.numeric import Infinity

from requests.status_codes import codes
import tarfile
from tqdm import tqdm
from pathlib import Path
from utils.auxil import log
from utils.product_fun import get_satellite_name_from_product_name


service_url = "https://m2m.cr.usgs.gov/api/api/json/stable/{}"


def get_download_requests(auth, start_date, completion_date, sensor, resolution, wkt, env):
    max_records = 1000
    acquisition_filter = {"end": start_date[:10],
                         "start": completion_date[:10]}
    lat_max, lat_min, lng_max, lng_min = bounds(wkt)
    spatial_filter = {'filterType' : "mbr",
                      'lowerLeft' : {'latitude' : lat_min, 'longitude' : lng_min},
                      'upperRight' : { 'latitude' : lat_max, 'longitude' : lng_max}}
    payload = {'datasetName': sensor,
               'maxResults': max_records,
               'startingNumber': 1,
               'sceneFilter': {
                   'spatialFilter': spatial_filter,
                   'acquisitionFilter': acquisition_filter}
               }
    products = search(service_url.format("scene-search"), payload, env, auth)
    return products


def search(url, payload, env, auth):
    log(env["General"]["log"], "Searching for scenes: {}".format(payload["datasetName"]))
    products = []
    while True:
        log(env["General"]["log"], "Calling: {}".format(url), indent=1)
        token = server_authenticate(auth, env)
        headers = {'X-Auth-Token': token}
        response = requests.post(url, json.dumps(payload), headers=headers)
        if response.status_code == codes.OK:
            root = response.json()
            for scene in root['data']['results']:
                products.append({
                    "entityId": scene['entityId'],
                    "displayId": scene['displayId'],
                    "name": scene['displayId'],
                    "dataset": payload["datasetName"],
                    "sensing_start": scene['temporalCoverage']['startDate'],
                    "sensing_end": scene['temporalCoverage']['endDate'],
                    "product_creation": scene['publishDate'],
                    "satellite": get_satellite_name_from_product_name(scene['displayId'])
                })
            return products
        else:
            raise RuntimeError("Unexpected response: {}".format(response.text))


def bounds(wkt):
    points = wkt.replace(" ", "", 1).strip().replace("POLYGON((", "").replace("))", "").split(",")
    lat_min = Infinity
    lat_max = -Infinity
    lng_min = Infinity
    lng_max = -Infinity
    for point in points:
        p = point.strip().split(" ")
        if float(p[0]) > lng_max:
            lng_max = float(p[0])
        if float(p[1]) > lat_max:
            lat_max = float(p[1])
        if float(p[0]) < lng_min:
            lng_min = float(p[0])
        if float(p[1]) < lat_min:
            lat_min = float(p[1])
    return lat_max, lat_min, lng_max, lng_min


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


def do_download(auth, product, env, max_attempts=4, wait_time=30):
    product_path = product["l1_product_path"]
    file_temp = "{}.incomplete".format(product_path)
    os.makedirs(os.path.dirname(product_path), exist_ok=True)
    payload = {'datasetName': product['dataset'], 'entityIds': [product["entityId"]]}
    for attempt in range(max_attempts):
        try:
            log(env["General"]["log"], "Starting download attempt {} of {}".format(attempt + 1, max_attempts), indent=1)
            token = server_authenticate(auth, env)
            headers = {'X-Auth-Token': token}
            response = requests.post(service_url.format("download-options"), json.dumps(payload), headers=headers)
            if response.status_code != codes.OK:
                raise ValueError("Failed to access {}".format(service_url.format("download_options")))
            downloads = []
            for product in response.json()["data"]:
                if product['available'] == True:
                    downloads.append({'entityId': product['entityId'],
                                      'productId': product['id']})
            label = datetime.now().strftime("%Y%m%d_%H%M%S")  # Customized label using date time
            payload = {'downloads': downloads,
                       'label': label}
            response = requests.post(service_url.format("download-request"), json.dumps(payload), headers=headers)
            if response.status_code != codes.OK:
                raise ValueError("Failed to collect download link")
            url = response.json()["data"]["availableDownloads"][0]["url"]
            session = requests.Session()
            session.headers.update({'X-Auth-Token': f'{token}'})
            downloaded_bytes = 0
            with session.get(url, stream=True, timeout=600) as req:
                if req.status_code != codes.OK:
                    raise ValueError("{} ERROR.".format(req.status_code))
                with tqdm(unit='B', unit_scale=True, disable=not True) as progress:
                    chunk_size = 2 ** 20  # download in 1 MB chunks
                    with open(file_temp, 'wb') as fout:
                        for chunk in req.iter_content(chunk_size=chunk_size):
                            if chunk:  # filter out keep-alive new chunks
                                fout.write(chunk)
                                progress.update(len(chunk))
                                downloaded_bytes += len(chunk)
            os.makedirs(product_path, exist_ok=True)
            with tarfile.open(file_temp, 'r') as tar_file:
                tar_file.extractall(product_path)
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
    return [env['username'], env['application_token']]


def server_authenticate(auth, env, max_attempts=5, wait_time=5):
    username, password = auth
    for attempt in range(max_attempts):
        try:
            token = get_token(username, password)
            log(env["General"]["log"], "Authentication successful.", indent=2)
            return token
        except Exception as e:
            log(env["General"]["log"], "Failed to authenticate (Attempt {} of {}): {}".format(attempt + 1, max_attempts, e), indent=2)
            time.sleep(wait_time)
    raise RuntimeError(f'Unable to authenticate with the Copernicus Dataspace server.')


def get_token(username, password):
    token_data = {
        "username": username,
        "token": password
    }
    response = requests.post(service_url.format("login-token"), json.dumps(token_data)).json()
    if isinstance(response["data"], str) and len(response["data"]) > 10:
        return response["data"]
    else:
        raise ValueError("Failed")