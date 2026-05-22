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
    root = get_input_root(env, sensor=sensor, start=start)
    products = []

    log(env["General"]["log"], "Searching local products in {}".format(root), indent=1)
    if not os.path.isdir(root):
        log(
            env["General"]["log"],
            "Local input root does not exist: {}. Check DIAS l1_path: {}".format(root, env["DIAS"]["l1_path"]),
            indent=2,
        )
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


def get_input_root(env, sensor=None, start=None):
    l1_path = env["DIAS"]["l1_path"]
    replacements = {
        "sensor": sensor,
    }
    if start is not None:
        replacements.update({
            "year": start.strftime("%Y"),
            "month": start.strftime("%m"),
            "day": start.strftime("%d"),
        })

    for key, value in replacements.items():
        if value is not None:
            l1_path = l1_path.replace("{{{}}}".format(key), str(value))

    marker = "{product_name}"
    if marker in l1_path:
        product_root = l1_path.split(marker)[0].rstrip("/\\")
        if "{" not in product_root:
            return product_root
        return root_before_first_placeholder(product_root)
    return root_before_first_placeholder(l1_path)


def iter_product_paths(root):
    for current_root, dirs, _ in os.walk(root):
        product_dirs = []
        for name in dirs:
            path = os.path.join(current_root, name)
            if is_landsat_product(name, path) or is_sentinel_product(name, path):
                product_dirs.append(name)
                yield path
        if product_dirs:
            dirs[:] = [name for name in dirs if name not in product_dirs]


def root_before_first_placeholder(path_template):
    first_placeholder = path_template.find("{")
    if first_placeholder == -1:
        return os.path.dirname(path_template)

    root = path_template[:first_placeholder].rstrip("/\\")
    if not root or root == os.sep:
        raise ValueError(
            "LOCAL DIAS l1_path needs a stable directory before the first placeholder: {}".format(path_template)
        )
    return root or os.sep


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
