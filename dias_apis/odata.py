#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
EO data access - shared OData helpers

COAH (Copernicus Dataspace) and CREODIAS expose the same OData catalogue and the same
S3 bucket layout, so the search, filtering and download logic lives here. The API
modules only declare their addresses and their authentication chain, which is where
they genuinely differ.
"""

import os
import time
import random
import boto3
import shutil
import threading
import requests
import requests_cache
from requests.status_codes import codes
from datetime import datetime
from zipfile import ZipFile, BadZipFile
from tqdm import tqdm
from pathlib import Path
from utils.auxil import log
from utils.product_fun import get_satellite_name_from_product_name

search_query = "?$filter=((ContentDate/Start ge {} and ContentDate/Start le {}) and (Online eq true) and (OData.CSC.Intersects(Footprint=geography'SRID=4326;{}')) and (((((((Attributes/OData.CSC.StringAttribute/any(i0:i0/Name eq 'productType' and i0/Value eq '{}')))) and (Collection/Name eq '{}'))))))&$expand=Attributes&$top={}"

# Sentinel-3 timeliness, ranked worst to best. A later entry supersedes an earlier one for
# the same scene.
timeliness_rank = {"": 0, "NR": 1, "ST": 2, "NT": 3}

# Access tokens are valid for 10 minutes on CDSE, so reuse one for 8. Requesting a fresh
# one per download is a token request storm, and on CREODIAS it also burns a TOTP code
# that is only valid for 30 seconds and only usable once.
token_ttl = 480
_token_cache = {}
_token_lock = threading.Lock()

# Longest we will ever wait between attempts, even if the server asks for more.
max_backoff = 900


class FatalDownloadError(Exception):
    """The product cannot be downloaded from this API however many times we ask."""


class ThrottledResponse(Exception):
    """The server told us to slow down."""

    def __init__(self, status, retry_after=None):
        super().__init__("HTTP {}".format(status))
        self.status = status
        self.retry_after = retry_after


def get_download_requests(start_date, end_date, sensor, resolution, wkt, env, api_name, search_address, cache_path):
    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date)
    if start > end:
        raise ValueError("Start date must be greater than end date")
    max_records = 1000
    geometry = wkt.replace(" ", "", 1).strip()
    satellite, product_type = get_dataset_id(sensor, resolution, api_name)
    query = search_query.format(start_date, end_date, geometry, product_type, satellite, max_records)
    products = search(satellite, query, env, search_address, cache_path)
    products = timeliness_filter(products)
    return products


def search(satellite, query, env, search_address, cache_path):
    log(env["General"]["log"], "Search for products: {}".format(query))
    session = requests_cache.CachedSession(cache_path, backend='sqlite', expire_after=3600,
                                           allowable_methods=('GET', 'POST'))
    products = []
    url = search_address.format(query)
    while True:
        log(env["General"]["log"], "Calling: {}".format(url), indent=1)
        response = session.get(url)
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
    """Keep one Sentinel-3 product per scene, preferring better timeliness then newer processing.

    Only Sentinel-3 is deduplicated. Timeliness tags exist nowhere else, and the key a
    scene is identified by here - the sensing window - is shared by every Sentinel-2 tile
    of a datatake, so applying this to MSI would silently discard most of the tiles.
    """
    best, order, passthrough = {}, [], []
    for product in products:
        if not product["satellite"].startswith("S3"):
            passthrough.append(product)
            continue
        key = (product["satellite"], product["sensing_start"], product["sensing_end"])
        current = best.get(key)
        if current is None:
            best[key] = product
            order.append(key)
            continue
        mine = (timeliness_rank.get(product["timeliness"], 0), product["product_creation"])
        theirs = (timeliness_rank.get(current["timeliness"], 0), current["product_creation"])
        if mine > theirs:
            best[key] = product
    return [best[key] for key in order] + passthrough


def get_dataset_id(sensor, resolution, api_name):
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
        raise RuntimeError("{} API is not yet implemented for sensor: {}".format(api_name, sensor))


def cached_token(api_name, get_token, force_refresh=False):
    """Return an access token for api_name, reusing a recent one where possible."""
    with _token_lock:
        entry = _token_cache.get(api_name)
        if not force_refresh and entry is not None and time.monotonic() < entry[1]:
            return entry[0]
        token = get_token()
        _token_cache[api_name] = (token, time.monotonic() + token_ttl)
        return token


def invalidate_token(api_name):
    with _token_lock:
        _token_cache.pop(api_name, None)


def backoff_seconds(attempt, base, retry_after=None):
    """Exponential backoff with jitter, unless the server named its own delay.

    The cap is applied after the jitter, not before, so it really is a ceiling.
    """
    if retry_after is not None:
        return min(retry_after, max_backoff)
    return min(base * (2 ** attempt) * (0.5 + random.random()), max_backoff)


def throughput(nbytes, seconds):
    return nbytes / max(seconds, 1e-6) / (1024.0 * 1024.0)


def stream_product(session, url, headers, file_temp, api_name, log_file, read_timeout=600):
    """Fetch the product zip into file_temp, resuming from a partial file when there is one.

    Returns (bytes_on_disk, expected_total) where expected_total is None if the server did
    not say how big the product is.
    """
    resume_from = os.path.getsize(file_temp) if os.path.exists(file_temp) else 0
    if resume_from:
        headers = dict(headers, **{"Range": "bytes={}-".format(resume_from)})

    with session.get(url, headers=headers, stream=True, timeout=(30, read_timeout)) as req:
        status = int(req.status_code)

        if status == 416:
            # Our range starts past the end of the product: either we already have all of
            # it, or the partial file is stale and larger than the real thing. The zip
            # check downstream decides which.
            log(log_file, "Server reports nothing further to send, verifying what we have", indent=2)
            return resume_from, None
        if status in (401, 403):
            invalidate_token(api_name)
            raise ValueError("{} unauthorised: {}".format(status, req.text[:200]))
        if status == 404:
            raise FatalDownloadError("404 not found")
        if status == 429 or status >= 500:
            retry_after = req.headers.get("Retry-After")
            raise ThrottledResponse(status, float(retry_after) if retry_after and retry_after.isdigit() else None)
        if status >= 400:
            try:
                error_msg = req.json()
            except ValueError:
                error_msg = req.text[:200]
            raise ValueError("{} ERROR. {}".format(status, error_msg))

        if status == 206:
            mode, written = "ab", resume_from
            content_range = req.headers.get("Content-Range", "")
            expected = int(content_range.split("/")[-1]) if "/" in content_range else None
            log(log_file, "Resuming from {:.1f} MB (HTTP 206)".format(resume_from / 1024 / 1024), indent=2)
        else:
            if resume_from:
                log(log_file, "Server ignored the range request, restarting from zero", indent=2)
            mode, written = "wb", 0
            length = req.headers.get("Content-Length")
            expected = int(length) if length else None

        with tqdm(unit='B', unit_scale=True, initial=written, total=expected) as progress:
            chunk_size = 2 ** 20  # download in 1 MB chunks
            with open(file_temp, mode) as fout:
                for chunk in req.iter_content(chunk_size=chunk_size):
                    if chunk:  # filter out keep-alive new chunks
                        fout.write(chunk)
                        progress.update(len(chunk))
                        written += len(chunk)

    return written, expected


def extract_product(file_temp, product_path, log_file):
    """Verify the zip, then extract via a staging directory so a crash mid-extract can
    never leave something that looks like a finished product."""
    staging = "{}.extracting".format(product_path)
    if os.path.exists(staging):
        shutil.rmtree(staging, ignore_errors=True)

    with ZipFile(file_temp, 'r') as zip_file:
        broken = zip_file.testzip()
        if broken is not None:
            raise BadZipFile("corrupt member: {}".format(broken))
        zip_file.extractall(staging)

    entries = os.listdir(staging)
    if len(entries) == 1 and os.path.isdir(os.path.join(staging, entries[0])):
        source = os.path.join(staging, entries[0])
    else:
        source = staging

    if os.path.exists(product_path):
        shutil.rmtree(product_path, ignore_errors=True)
    shutil.move(source, product_path)
    shutil.rmtree(staging, ignore_errors=True)


def do_download(product, env, api_name, download_address, bucket_address, get_token, token_in_url=False,
                max_attempts=5, wait_time=30, bucket_name="eodata"):
    """Download a product, either from the S3 bucket or through the zipper API.

    get_token must return a valid access token. It is only consulted when the cached token
    for this API has expired, so a long run authenticates every few minutes rather than
    once per product. token_in_url selects how that token reaches the zipper: as a query
    parameter (CREODIAS) or as an Authorization header (COAH).

    Partial transfers are kept between attempts and resumed with a range request, and a
    download is only extracted once its size and its zip structure both check out.
    """
    uuid = product["uuid"]
    product_path = product["l1_product_path"]
    s3_key = product["s3"]
    log_file = env["General"]["log"]
    os.makedirs(os.path.dirname(product_path), exist_ok=True)
    for attempt in range(max_attempts):
        if "s3" in env[api_name] and env[api_name]["s3"].lower() == "true":
            log(log_file, "Starting S3 download attempt {} of {}".format(attempt + 1, max_attempts), indent=1)
            folder_temp = "{}.incomplete".format(product_path)
            started, downloaded_bytes = time.monotonic(), 0
            try:
                s3 = boto3.resource('s3',
                                    aws_access_key_id=env[api_name]["access_key"],
                                    aws_secret_access_key=env[api_name]["secret_key"],
                                    endpoint_url=bucket_address, )
                bucket = s3.Bucket(bucket_name)
                prefix = s3_key.replace("/eodata/", "")
                objects = [o for o in bucket.objects.filter(Prefix=prefix) if not o.key.endswith("/")]
                for i in range(len(objects)):
                    print("Downloading sub-file {} ({}/{})".format(os.path.basename(objects[i].key), i + 1,
                                                                   len(objects)))
                    local_path = folder_temp + objects[i].key.replace(prefix, "")
                    os.makedirs(os.path.dirname(local_path), exist_ok=True)
                    bucket.download_file(objects[i].key, local_path)
                    downloaded_bytes += objects[i].size
                if os.path.exists(product_path):
                    shutil.rmtree(product_path, ignore_errors=True)
                shutil.move(folder_temp, product_path)
                elapsed = time.monotonic() - started
                log(log_file, "Download complete: {:.1f} MB in {:.0f} s ({:.2f} MB/s) from {}".format(
                    downloaded_bytes / 1024 / 1024, elapsed, throughput(downloaded_bytes, elapsed), api_name), indent=1)
                return
            except Exception as e:
                log(log_file, "Failed S3 download attempt {} of {}: {}".format(attempt + 1, max_attempts, e), indent=1)
                # The temp path is a directory here, so it needs rmtree rather than unlink.
                # Leaving it behind would let the next attempt merge two partial downloads.
                shutil.rmtree(folder_temp, ignore_errors=True)
                if attempt + 1 < max_attempts:
                    wait = backoff_seconds(attempt, wait_time)
                    log(log_file, "Waiting {:.0f} s before retrying".format(wait), indent=2)
                    time.sleep(wait)
        else:
            log(log_file, "Starting API download attempt {} of {}".format(attempt + 1, max_attempts), indent=1)
            file_temp = "{}.incomplete".format(product_path)
            started = time.monotonic()
            try:
                token = cached_token(api_name, get_token)
                with requests.Session() as session:
                    if token_in_url:
                        url = download_address.format(uuid, token)
                    else:
                        url = download_address.format(uuid)
                        session.headers.update({'Authorization': 'Bearer {}'.format(token)})
                    downloaded_bytes, expected = stream_product(session, url, {}, file_temp, api_name, log_file)

                if expected is not None and downloaded_bytes != expected:
                    raise BadZipFile("size mismatch: got {} bytes, expected {}".format(downloaded_bytes, expected))

                extract_product(file_temp, product_path, log_file)
                Path(file_temp).unlink()
                elapsed = time.monotonic() - started
                log(log_file, "Download complete: {:.1f} MB in {:.0f} s ({:.2f} MB/s) from {}".format(
                    downloaded_bytes / 1024 / 1024, elapsed, throughput(downloaded_bytes, elapsed), api_name), indent=1)
                return
            except FatalDownloadError as e:
                # Retrying will not help; let the caller move on to the next API.
                log(log_file, "{} cannot serve this product: {}".format(api_name, e), indent=1)
                discard_partial(file_temp, product_path)
                raise
            except BadZipFile as e:
                # Whatever is on disk cannot be trusted, so do not resume onto it.
                log(log_file, "Failed download attempt {} of {}: {}".format(attempt + 1, max_attempts, e), indent=1)
                log(log_file, "Discarding the partial file and restarting from zero", indent=2)
                discard_partial(file_temp, product_path)
                if attempt + 1 < max_attempts:
                    time.sleep(backoff_seconds(attempt, wait_time))
            except ThrottledResponse as e:
                # Keep the partial file: this is exactly the case resuming is for.
                wait = backoff_seconds(attempt, wait_time, e.retry_after)
                log(log_file, "Throttled by {} ({}), waiting {:.0f} s".format(api_name, e, wait), indent=1)
                if attempt + 1 < max_attempts:
                    time.sleep(wait)
            except Exception as e:
                log(log_file, "Failed download attempt {} of {}: {}".format(attempt + 1, max_attempts, e), indent=1)
                shutil.rmtree("{}.extracting".format(product_path), ignore_errors=True)
                if attempt + 1 < max_attempts:
                    wait = backoff_seconds(attempt, wait_time)
                    log(log_file, "Waiting {:.0f} s before retrying".format(wait), indent=2)
                    time.sleep(wait)
    raise ValueError("Failed to download file after {} attempts".format(max_attempts))


def discard_partial(file_temp, product_path):
    """Remove the partial download and any half finished extraction, leaving product_path alone."""
    if os.path.exists(file_temp):
        try:
            Path(file_temp).unlink()
        except OSError:
            shutil.rmtree(file_temp, ignore_errors=True)
    shutil.rmtree("{}.extracting".format(product_path), ignore_errors=True)


def server_authenticate(get_token, env, server_name, max_attempts=5, wait_time=35):
    """Retry get_token, a callable returning an access token, until it succeeds.

    wait_time has to exceed the 30 second TOTP window: CREODIAS codes are single use, so
    retrying inside the same window just resubmits a code the server has already consumed.
    """
    for attempt in range(max_attempts):
        try:
            token = get_token()
            log(env["General"]["log"], "Authentication successful.", indent=2)
            return token
        except Exception as e:
            log(env["General"]["log"], "Failed to authenticate (Attempt {} of {}): {}".format(attempt + 1, max_attempts, e), indent=2)
            time.sleep(wait_time)
    raise RuntimeError("Unable to authenticate with the {} server.".format(server_name))


def request_token(token_address, token_data):
    response = requests.post(token_address, data=token_data).json()
    try:
        return response['access_token']
    except KeyError:
        raise RuntimeError(response)
