#! /usr/bin/env python
# -*- coding: utf-8 -*-

import requests
from requests.auth import HTTPBasicAuth
from requests.status_codes import codes
from requests.utils import requote_uri
import json
import time


# HDA-API endpoint address
apis_endpoint = "https://wekeo-broker.apps.mercator.dpi.wekeo.eu"
# Access-token address
access_token_address = apis_endpoint + "/databroker/gettoken"
# Terms and conditions
accept_tc_address = apis_endpoint + "/databroker/termsaccepted/Copernicus_General_License"
# Metadata address
metadata_address = apis_endpoint + "/databroker/querymetadata/{}"
# Data request address
datarequest_address = apis_endpoint + "/databroker/datarequest"
# Data request status address
datarequest_status_address = apis_endpoint + "/databroker/datarequest/status/{}"
# Data request data address
datarequest_result_address = apis_endpoint + "/databroker/datarequest/jobs/{}/result"


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
                print("Job {} not yet completed. Waiting another 10 seconds before checking again...".format(job_id))
                time.sleep(10)
        else:
            raise RuntimeError("Unexpected response {}".format(response.text))


def get_datarequest_results(access_token, job_id):
    print("Getting data request results from {}".format(datarequest_result_address.format(job_id)))
    results = []
    headers = {'authorization': access_token}
    datarequest_result_address_paged = datarequest_result_address.format(job_id)
    while True:
        response = requests.get(datarequest_result_address_paged, headers=headers)
        if response.status_code == codes.OK:
            response_dict = json.loads(response.text)
            for result in response_dict['content']:
                results.append(result)
            if not response_dict['nextPage']:
                break
            datarequest_result_address_paged = response_dict['nextPage']
        else:
            raise RuntimeError("Unexpected response {}".format(response.text))
    numberOfResults = response_dict['totItems']
    return results, numberOfResults
