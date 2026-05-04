#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Local product discovery for already-mounted input products."""

import os
from datetime import datetime, timezone

from utils.auxil import log
from utils.product_fun import get_satellite_name_from_product_name, get_sensing_date_from_product_name


def authenticate(env):
    return None


def get_download_requests(auth, start_date, end_date, sensor, resolution, wkt, env):
    start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
    end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
    root = get_input_root(env)
    products = []

    log(env["General"]["log"], "Searching local products in {}".format(root), indent=1)
    if not os.path.isdir(root):
        log(env["General"]["log"], "Local input root does not exist: {}".format(root), indent=2)
        return products

    for product_path in iter_product_paths(root):
        product_name = os.path.basename(product_path.rstrip(os.sep))
        if not matches_sensor(product_name, sensor):
            continue
        sensing_date = datetime.strptime(get_sensing_date_from_product_name(product_name), "%Y%m%d")
        sensing_start = sensing_date.replace(tzinfo=timezone.utc)
        sensing_end = sensing_start.replace(hour=23, minute=59, second=59)
        if sensing_end < start or sensing_start > end:
            continue
        products.append({
            "name": product_name,
            "id": product_name,
            "uuid": product_name,
            "displayId": product_name,
            "dataset": sensor,
            "sensing_start": sensing_start.isoformat().replace("+00:00", "Z"),
            "sensing_end": sensing_end.isoformat().replace("+00:00", "Z"),
            "product_creation": sensing_start.isoformat().replace("+00:00", "Z"),
            "satellite": get_satellite_name_from_product_name(product_name),
        })

    log(env["General"]["log"], "{} local products match the requested date and sensor.".format(len(products)), indent=1)
    return products


def do_download(auth, product, env, max_attempts=1, wait_time=0):
    log(env["General"]["log"], "Skipping download for local product: {}".format(product["name"]), indent=1)


def get_input_root(env):
    l1_path = env["DIAS"]["l1_path"]
    marker = "{product_name}"
    if marker in l1_path:
        return l1_path.split(marker)[0].rstrip(os.sep)
    return os.path.dirname(l1_path)


def iter_product_paths(root):
    for name in os.listdir(root):
        path = os.path.join(root, name)
        if is_landsat_product(name, path) or is_sentinel_product(name, path):
            yield path


def matches_sensor(product_name, sensor):
    requested = [s.strip() for s in sensor.split(",")]
    if sensor == "OLI_TIRS":
        requested = ["LC08", "LC09"]
    return any(product_name.startswith(s) for s in requested)


def is_landsat_product(name, path):
    return (
        os.path.isdir(path)
        and (name.startswith("LC08") or name.startswith("LC09"))
        and any(f.endswith("_MTL.txt") for f in os.listdir(path))
    )


def is_sentinel_product(name, path):
    return os.path.isdir(path) and (
        name.startswith("S2A") or name.startswith("S2B") or name.startswith("S2C")
        or name.startswith("S3A") or name.startswith("S3B")
    )
