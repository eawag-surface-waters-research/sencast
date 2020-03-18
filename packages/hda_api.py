#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
from zipfile import ZipFile
import requests
from requests.auth import HTTPBasicAuth
from requests.status_codes import codes
from requests.utils import requote_uri
import json
import time


# HDA-API endpoint address
api_endpoint = "https://wekeo-broker.apps.mercator.dpi.wekeo.eu"
# Access-token address
access_token_address = api_endpoint + "/databroker/gettoken"
# Terms and conditions
accept_tc_address = api_endpoint + "/databroker/termsaccepted/Copernicus_General_License"
# Metadata address
metadata_address = api_endpoint + "/databroker/querymetadata/{}"
# Data request address
datarequest_address = api_endpoint + "/databroker/datarequest"
# Data request status address
datarequest_status_address = api_endpoint + "/databroker/datarequest/status/{}"
# Data request data address
datarequest_result_address = api_endpoint + "/databroker/datarequest/jobs/{}/result"
# Data order address
dataorder_address = api_endpoint + "/databroker/dataorder"
# Data order status address
dataorder_status_address = api_endpoint + "/databroker/dataorder/status/{}"
# Data order download address
dataorder_download_address = api_endpoint + "/databroker/dataorder/download/{}"


def get_access_token(username, password):
    print("Getting an access token for user {}. This token is valid for one hour only. URL: {}"
          .format(username, access_token_address))
    auth = HTTPBasicAuth(username, password)
    response = requests.get(access_token_address, auth=auth)
    if response.status_code == codes.OK:
        access_token = json.loads(response.text)['access_token']
        print("Success: Access token is {}".format(access_token))
        return access_token
    else:
        raise RuntimeError("Unexpected response {} with header {}".format(response.text, response.headers))


def accept_tc_if_required(access_token):
    print("Checking if Terms and Conditions are already accepted: {}".format(accept_tc_address))
    headers = {'authorization': access_token}
    response = requests.get(accept_tc_address, headers=headers)
    isTandCAccepted = json.loads(response.text)['accepted']
    if isTandCAccepted is 'False':
        print("Accepting Terms and Conditions of Copernicus_General_License: {}".format(accept_tc_address))
        response = requests.put(accept_tc_address, headers=headers)
        if response.status_code == codes.OK:
            print("Successfully accepted Copernicus_General_License Terms and Conditions.")
        else:
            raise RuntimeError("Unexpected response {} with header {}".format(response.text, response.headers))
    else:
        print("Copernicus_General_License Terms and Conditions already accepted.")


def query_metadata(access_token, dataset_id):
    encoded_dataset_id = requote_uri(dataset_id)
    print("Getting query metadata from {}".format(metadata_address.format(encoded_dataset_id)))
    headers = {'authorization': access_token}
    response = requests.get(metadata_address.format(encoded_dataset_id), headers=headers)
    if response.status_code == codes.OK:
        return json.loads(response.text)
    else:
        raise RuntimeError("Unexpected response {}".format(response.text))


def post_datarequest(access_token, datarequest):
    print("Posting datarequest to {}".format(datarequest_address))
    headers = {'authorization': access_token}
    response = requests.post(datarequest_address, headers=headers, json=datarequest)
    if response.status_code == codes.OK:
        job_id = json.loads(response.text)["jobId"]
        print("Query successfully submitted. Job ID is " + job_id)
        return job_id
    else:
        raise RuntimeError("Unexpected response {}".format(response.text))


def wait_for_datarequest_to_complete(access_token, job_id):
    print("Waiting for data request to complete...")
    headers = {'authorization': access_token}
    while True:
        response = requests.get(datarequest_status_address.format(job_id), headers=headers)
        if response.status_code == codes.OK:
            if json.loads(response.text)["status"] == "completed":
                print("Job {} completed!".format(job_id))
                return
            else:
                print("Job {} not yet completed. Wait 10 seconds before checking again...".format(job_id))
                time.sleep(10)
        else:
            raise RuntimeError("Unexpected response {}".format(response.text))


def get_datarequest_results(access_token, job_id):
    print("Getting data request results from {}".format(datarequest_result_address.format(job_id)))
    uris = []
    filenames = []
    headers = {'authorization': access_token}
    datarequest_result_address_paged = datarequest_result_address.format(job_id)
    while True:
        response = requests.get(datarequest_result_address_paged, headers=headers)
        if response.status_code == codes.OK:
            response_dict = json.loads(response.text)
            for result in response_dict['content']:
                uris.append(result['url'])
                filenames.append(result['filename'])
            if not response_dict['nextPage']:
                break
            datarequest_result_address_paged = response_dict['nextPage']
        else:
            raise RuntimeError("Unexpected response {}".format(response.text))
    return uris, filenames


def post_dataorder(access_token, job_id, uri):
    print("Posting dataorder to {}".format(dataorder_address))
    headers = {'authorization': access_token}
    dataorder = {
        'jobId': job_id,
        'uri': uri
    }
    response = requests.post(dataorder_address, headers=headers, json=dataorder)
    if response.status_code == codes.OK:
        order_id = json.loads(response.text)["orderId"]
        print("Dataorder submitted. Order ID is " + order_id)
        return order_id
    else:
        raise RuntimeError("Unexpected response {}".format(response.text))


def wait_for_dataorder_to_complete(access_token, order_id):
    print("Waiting for dataorder {} to complete...".format(order_id))
    headers = {'authorization': access_token}
    while True:
        response = requests.get(dataorder_status_address.format(order_id), headers=headers)
        if response.status_code == codes.OK:
            if json.loads(response.text)["status"] == "completed":
                print("Dataorder {} completed!".format(order_id))
                return
            else:
                print("Dataorder {} not yet completed. Wait 10 seconds before checking again...".format(order_id))
                time.sleep(10)
        else:
            raise RuntimeError("Unexpected response {}".format(response.text))


def dataorder_download(access_token, order_id, filename):
    print("Downloading data from {}".format(dataorder_download_address.format(order_id)))
    headers = {'authorization': access_token}
    response = requests.get(dataorder_download_address.format(order_id), headers=headers, stream=True)
    with open(filename + '.zip', 'wb') as down_stream:
        for chunk in response.iter_content(chunk_size=65536):
            down_stream.write(chunk)
    with ZipFile(filename + '.zip', 'r') as zip_file:
        prod_name = zip_file.namelist()[0]
        zip_file.extractall(prod_name.split('.')[0])
    os.remove(filename + '.zip')
