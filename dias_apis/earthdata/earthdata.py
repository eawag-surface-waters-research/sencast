#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
EarthData CMR API
https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html
"""

import os
import time
import requests
import requests_cache
from requests.status_codes import codes
import xml.etree.ElementTree as ET
from datetime import datetime
from tqdm import tqdm
from pathlib import Path
from utils.auxil import log

search_address = "https://cmr.earthdata.nasa.gov/search/granules?collection_concept_id={}&bounding_box={}&temporal={},{}&downloadable=true"

def get_download_requests(auth, start_date, end_date, sensor, resolution, wkt, env):
    if sensor == "PACE_OCI_1B":
        collection_concept_id = "C3026581092-OB_CLOUD"
        satellite = "PACE"
    else:
        raise ValueError("No id defined for sensor: {}".format(sensor))
    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date)
    if start > end:
        raise ValueError("Start date must be greater than end date")
    bounds = wkt_to_bounds(wkt)
    url = search_address.format(collection_concept_id, bounds, start_date, end_date)
    products = search(url, satellite, env)
    return products

def search(url, satellite, env):
    log(env["General"]["log"], "Searching for granules")
    session = requests_cache.CachedSession(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache"),
                                           backend='sqlite', expire_after=3600, allowable_methods=('GET', 'POST'))
    products = []
    while True:
        log(env["General"]["log"], "Calling: {}".format(url), indent=1)
        response = session.get(url)
        if response.status_code == codes.OK:
            root = ET.fromstring(response.content)
            for reference in root.find("references").findall("reference"):
                sub_response = requests.get(reference.find("location").text)
                if sub_response.status_code == codes.OK:
                    data = sub_response.json()
                    name = data["DataGranule"]["Identifiers"][0]["Identifier"]
                    download = [u for u in data["RelatedUrls"] if u["Type"] == "GET DATA"][0]["URL"]
                    products.append({
                        "name": name,
                        "id": reference.find("id").text,
                        "download": download,
                        "satellite": satellite,
                        "sensing_start": data["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"],
                        "sensing_end": data["TemporalExtent"]["RangeDateTime"]["EndingDateTime"]
                    })
            return products
        else:
            raise RuntimeError("Unexpected response: {}".format(response.text))

def wkt_to_bounds(wkt):
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
    return "{},{},{},{}".format(lng_min, lat_min, lng_max, lat_max)

def do_download(auth, product, env, max_attempts=4, wait_time=30):
    product_path = product["l1_product_path"]
    os.makedirs(os.path.dirname(product_path), exist_ok=True)
    for attempt in range(max_attempts):
        log(env["General"]["log"], "Starting download attempt {} of {}".format(attempt + 1, max_attempts), indent=1)
        url = product["download"]
        file_temp = "{}.incomplete".format(product_path)
        session = requests.Session()
        try:
            downloaded_bytes = 0
            with session.get(url, stream=True, timeout=600) as req:
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

            os.rename(file_temp, product_path)
            return
        except Exception as e:
            log(env["General"]["log"], "Failed download attempt {} of {}: {}".format(attempt + 1, max_attempts, e), indent=1)
            log(env["General"]["log"], "Ensure you have provided EarthData credentials", indent=1)
            try:
                Path(file_temp).unlink()
            except:
                pass
            time.sleep(wait_time)

def authenticate(env):
    return