#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
EarthExplorer (EE) serves as a key data access portal for the USGS Earth Resources Observation and Science (EROS) data repository.
"""

import os
import json
import boto3
import time
import shutil
import tarfile
from tqdm import tqdm
from pathlib import Path
from datetime import datetime
import requests
import requests_cache
from requests.status_codes import codes
from utils.auxil import log
from utils.product_fun import get_satellite_name_from_product_name


service_url = "https://m2m.cr.usgs.gov/api/api/json/stable/{}"


def get_download_requests(auth, start_date, end_date, sensor, resolution, wkt, env):
    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date)
    if start > end:
        raise ValueError("Start date must be greater than end date")
    max_records = 50000
    acquisition_filter = {"start": start_date[:10],
                          "end": end_date[:10]}
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
    session = requests_cache.CachedSession(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache"),
                                           backend='sqlite', expire_after=3600, allowable_methods=('GET', 'POST'))
    products = []
    log(env["General"]["log"], "Calling: {}".format(url), indent=1)
    log(env["General"]["log"], "{}".format(payload), indent=1)
    response = session.post(url, json.dumps(payload))
    if response.status_code != codes.OK:
        token = server_authenticate(auth, env)
        response = session.post(url, json.dumps(payload), headers={'X-Auth-Token': token})
    else:
        log(env["General"]["log"], "Request has already been cached.", indent=2)
    if response.status_code == codes.OK and response.json()["data"] is not None:
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
    lat_min = float('inf')
    lat_max = -float('inf')
    lng_min = float('inf')
    lng_max = -float('inf')
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


def do_download(auth, product, env, max_attempts=4, wait_time=30):
    product_path = product["l1_product_path"]
    incomplete = "{}.incomplete".format(product_path)
    os.makedirs(os.path.dirname(product_path), exist_ok=True)
    payload = {'datasetName': product['dataset'], 'entityIds': [product["entityId"]]}
    for attempt in range(max_attempts):
        if "s3" in env["EROS"] and env["EROS"]["s3"].lower() == "true" and attempt < 1:
            log(env["General"]["log"], "Starting S3 download attempt {} of {}".format(attempt + 1, max_attempts),
                indent=1)
            try:
                if os.path.exists(incomplete):
                    Path(incomplete).unlink()
                bands = []
                if "bands" in env["EROS"]:
                    bands = [b.strip() for b in env["EROS"]["bands"].split(",")]
                parts = product["displayId"].split("_")
                prefix = ("collection02/level-2/standard/oli-tirs/{}/{}/{}/{}"
                       .format(parts[3][:4], parts[2][:3], parts[2][3:], product["displayId"]))
                s3 = boto3.client('s3',
                                    aws_access_key_id=env["AWS"]["aws_access_key_id"],
                                    aws_secret_access_key=env["AWS"]["aws_secret_access_key"],
                                    region_name="us-west-2")
                response = s3.list_objects_v2(Bucket="usgs-landsat", Prefix=prefix, RequestPayer='requester')
                if 'Contents' in response:
                    os.makedirs(incomplete)
                    for obj in response['Contents']:
                        if len(bands) > 0:
                            for band in bands:
                                if obj['Key'].split(".")[0].endswith(band):
                                    s3.download_file("usgs-landsat", obj['Key'],
                                                     os.path.join(incomplete, os.path.basename(obj['Key'])),
                                                     ExtraArgs={'RequestPayer': 'requester'})
                        else:
                            s3.download_file("usgs-landsat", obj['Key'],
                                             os.path.join(incomplete, os.path.basename(obj['Key'])),
                                             ExtraArgs={'RequestPayer': 'requester'})
                    os.rename(incomplete, product_path)
                    return
                else:
                    raise ValueError("Failed to list files")
            except Exception as e:
                log(env["General"]["log"], "Failed download attempt {} of {}: {}".format(attempt + 1, max_attempts, e), indent=1)
                try:
                    if os.path.exists(product_path):
                        shutil.rmtree(product_path)
                    if os.path.exists(incomplete):
                        shutil.rmtree(incomplete)
                except:
                    pass
                time.sleep(wait_time)
        else:
            log(env["General"]["log"], "Starting API download attempt {} of {}".format(attempt + 1, max_attempts),
                indent=1)
            try:
                if os.path.exists(incomplete):
                    shutil.rmtree(incomplete)
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
                        try:
                            error_msg = req.json()
                        except:
                            error_msg = req.text
                        raise ValueError("{} ERROR. {}".format(req.status_code, error_msg))
                    with tqdm(unit='B', unit_scale=True, disable=not True) as progress:
                        chunk_size = 2 ** 20  # download in 1 MB chunks
                        with open(incomplete, 'wb') as fout:
                            for chunk in req.iter_content(chunk_size=chunk_size):
                                if chunk:  # filter out keep-alive new chunks
                                    fout.write(chunk)
                                    progress.update(len(chunk))
                                    downloaded_bytes += len(chunk)
                os.makedirs(product_path, exist_ok=True)
                with tarfile.open(incomplete, 'r') as tar_file:
                    tar_file.extractall(product_path)
                Path(incomplete).unlink()
                return
            except Exception as e:
                log(env["General"]["log"], "Failed download attempt {} of {}: {}".format(attempt + 1, max_attempts, e), indent=1)
                try:
                    if os.path.exists(product_path):
                        shutil.rmtree(product_path)
                    if os.path.exists(incomplete):
                        Path(incomplete).unlink()
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