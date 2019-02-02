#! /usr/bin/env python
# -*- coding: utf-8 -*-

import queue
from threading import Thread
import requests, time
import urllib.parse
import sys
import re
import json
import logging
from zipfile import ZipFile
from io import BytesIO
import os
from snappy import ProductIO
from packages.auxil import list_xml_scene_dir
import urllib3
import getpass
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CONST_HTTP_SUCCESS_CODE = 200
MAX_THREADS = 8

def write_url_list(filename, urls):
    with open(filename, 'w') as f:
        for url in urls:
            f.write(url+'\n')
        

def query_dl_hda(params, outdir, max_threads=2):
    products = []
    query = query_HDA_API(params)
    if query['number_of_results'] > 0:
        # Check if one of the files already downloaded
        urls = []
        fnames = []
        all_fn = query['filenames']
        c = 0
        for fn in query['filenames']:
            if fn.split('.')[0] not in os.listdir(outdir):
                urls.append(query['urls'][c])
                fnames.append(fn)
            c += 1
        query['urls'] = urls
        query['filenames'] = fnames
        if query['urls']:
            user = getpass.getuser()
            url_list  = os.path.join(outdir,'urls_list_'+user+'.txt')
            write_url_list(url_list, query['urls'])
            max_threads = min(MAX_THREADS, len(query['urls']))
            print('\nDownloading {} product(s)...'.format(len(query['urls'])))
            os.system('cat ' + url_list +' | xargs -n 1 -P ' + str(max_threads) + \
                      ' wget --content-disposition -q -P ' + outdir)
            print('\nDownload complete.')
            os.remove(url_list)
            for fn in fnames:
                zf = [os.path.join(outdir, zf) for zf in os.listdir(outdir) if fn.split('.')[0] in zf]
                tempdir = os.path.join(outdir, zf[0].split('.')[0])
                os.mkdir(tempdir)
                with ZipFile(zf[0], 'r') as zipf:
                    zipf.extractall(tempdir)
                os.remove(os.path.join(outdir, zf[0]))
#             responses = download_response_url(query['urls'], query['headers'], max_threads=max_threads)
#             print('\nAll products downloaded.')
#             for response in responses:
#                 print('Start writing to disk...')
#                 fname = re.findall('"([^"]*)"', response.headers['content-disposition'])
#                 fname = os.path.splitext(fname[0])[0]
#                 # Check if file already downloaded
#                 new_outdir = os.path.join(outdir, fname)
#                 if not os.path.isdir(new_outdir):
#                     os.mkdir(new_outdir)
#                     print('Extracting to {}'.format(new_outdir))
#                     zf = ZipFile(BytesIO(response.content))
#                     zf.extractall(new_outdir)
        else:
            print('\nAll products already downloaded, skipping...')
        
        # Read products
        xmlf = list_xml_scene_dir(outdir, sensor=params['sensor'], file_list=all_fn)
    return xmlf


def dl_url(q, result):
    while not q.empty():
        work = q.get()
        count = 0
        while (count <=3):
            try:
                print('dl {}\n'.format(work[1]))
                response = requests.get(work[1], headers=work[2])
#                 logging.info("Requested..." + work[1])
                print('done {} with status code: {}\n'.format(work[1], response.status_code))
                if response.status_code == 200:
                    result[work[0]] = response 
                    break
                else:
                    print('\nStatus code is {}... {} retry for {}\n'.format(response.status_code, count+1, work[1]))
                    time.sleep(10)
                    if count == 3:
                        result[work[0]] = {}
                    count += 1
            except:
                print('Error with URL check!')
                logging.error('Error with URL check!')
                print('{} retry...\n'.format(count+1))
                if count == 3:
                    result[work[0]] = {}
                    raise
                count += 1
        q.task_done()
    return True


def download_response_url(urls, headers, max_threads=4):
    # Setup the queue for dl Threads
    q = queue.Queue(maxsize=0)
    # Use manu threads (one for each url with a maximum)
    num_threads = min(max_threads, len(urls))
    #Populating Queue with tasks
    results = [{} for x in urls];
    # Get a list of urls and fill the queue\
    for i in range(len(urls)):
        q.put((i, urls[i], headers))

    # Create a list of threads
    threads = []
    print('Populating queue...')
    for i in range(num_threads):
        # Start one thread per url
        worker = Thread(target=dl_url, args=[q, results])
        worker.setDaemon(True) # Allow main program to exit if anything is wrong
        worker.start()
    print('\nWaiting for download(s) to complete...')
    q.join()
    print('Completed.')
    return results


def query_HDA_API(params):
    if params['sensor'].upper() == 'OLCI':
        dataset_id = "EO:EUM:DAT:SENTINEL-3:OL_1_EFR___"
        encoded_dataset_id = urllib.parse.quote(dataset_id)
        
        #querymetadata = '/querymetadata/EO%3AEUM%3ADAT%3ASENTINEL-3%3AOL_1_EFR___'
        datarequest = {
            "datasetId": dataset_id,
            "stringChoiceValues": [
                {
                    "name": "sat",
                    "value": "Sentinel-3A"
                }
            ],
            "dateRangeSelectValues": [
                {
                    "name": "dtrange",
                    "start": params['start'],
                    "end": params['end']
                }
            ],
            "equi7GridSelectValues": [
                {
                    "name": "zone",
                    "zone": params['region'],
                    "tiles": params['tile']
                }
            ]
        }
    elif params['sensor'].upper() == 'MSI':
        datarequest = 'tofill'
    
    # HDA-API endpoint
    apis_endpoint="https://apis.wekeo.eu"
    #Data broker address
    broker_address = apis_endpoint + "/databroker/0.1.0"
    # Terms and conditions
    acceptTandC_address = apis_endpoint + "/dcsi-tac/0.1.0/termsaccepted/Copernicus_General_License"
    # Access-token address
    accessToken_address = apis_endpoint + '/token'
    #The following is the default key which will be removed once the user gets the ability to generate the key via WEkEO portal  
    api_key = "aTMzOHdPZUViZFQ0UmtBWnZ4Zjl1VV9XX1JjYTpmVzJSUW92d09NZHBXN3BDZzlCcjI1MFVMS3Nh"
    
    # 1. Get access token. Please replace the "API-KEY-PLACEHOLDER" with the actual key. See instructions at the top of this notebook
    headers = {'Authorization': 'Basic ' + api_key}
    data = [('grant_type', 'client_credentials')]
    
    print("Step-1: Getting an access token. This token is valid for one hour only.")
    response = requests.post(accessToken_address, headers=headers, data=data, verify=False)
    # If the HTTP response code is 200 (i.e. success), then retrive the token from the response
    if (response.status_code == CONST_HTTP_SUCCESS_CODE):
        access_token = json.loads(response.text)['access_token']
        print("Success: Access token is " + access_token)
    else:
        print("Error: Unexpected response {}".format(response))
        print(response.headers)
        
    
    # 2. GET querymetadata
    headers = {'Authorization': 'Bearer ' + access_token}
    response = requests.get(broker_address + '/querymetadata/' + encoded_dataset_id, 
                            headers=headers)

    print('Step 2: Getting query metadata, URL Is ' + broker_address + '/querymetadata/' +\
          encoded_dataset_id +"?access_token="+access_token)

    if (response.status_code == CONST_HTTP_SUCCESS_CODE):
        parsedResponse = json.loads(response.text)
    else:
        print("Error: Unexpected response {}".format(response))
    
    # 3. Accept Terms and Conditions for the dataset (if not already)
    response = requests.get(acceptTandC_address, headers=headers)

    isTandCAccepted = json.loads(response.text)['accepted']
    if isTandCAccepted is 'False':
        print("Accepting Terms and Conditions of Copernicus_General_License")
        response = requests.put(acceptTandC_address, headers=headers)
    else:
        print("Copernicus_General_License Terms and Conditions already accepted")
    
    # 4. POST datarequest
    print('Step 3: Posting datarequest')
    response = requests.post(broker_address + '/datarequest', headers=headers, 
                             json=datarequest, verify=False)
    if (response.status_code == CONST_HTTP_SUCCESS_CODE):    
        job_id = json.loads(response.text)['jobId']
        print ("Query successfully submitted. Job ID is " + job_id)
    else:
        print("Error: Unexpected response {}".format(response))

    # 5. Query your Dataset products
    print('Step 4: Query your Dataset products')
    isComplete = False
    while not isComplete:
        response = requests.get(broker_address + '/datarequest/status/' + \
                                job_id, headers=headers)
        results = json.loads(response.text)['resultNumber']
        isComplete = json.loads(response.text)['complete']
        print("Has the Job " + job_id + " completed ?  " + str(isComplete))
        # sleep for 2 seconds before checking the job status again
        if not isComplete:
            time.sleep(2)

    numberOfResults = results
#     print("Has the Job " + job_id + " completed ?  " + str(isComplete))
    print ("Total number of results : {}".format(numberOfResults))
    urls = []
    filenames = []
    if numberOfResults > 0:
        # Get Results list
        response = requests.get(broker_address + '/datarequest/jobs/' + job_id + \
                                '/result', headers=headers, params={'page': '0', 
                                                                    'size': str(numberOfResults)})
        results = json.loads(response.text)
    #     print("************** Results  *******************************")
    #     print(json.dumps(results, indent=4, sort_keys=True))
    #     print("*********************************************")

        # Get a list of urls
        for result in results['content']:
            externalUri = result['externalUri']
            product_size = result['fileSize']/(1024*1024)
            product_name = result['fileName']
            filenames.append(product_name)
            print("Product: {}".format(product_name))
            print("size: {0:.2f} MB\n".format(product_size))

            dl_url = broker_address + '/datarequest/result/' + job_id + \
            '?externalUri=' + urllib.parse.quote(externalUri) + '&access_token=' + access_token
            urls.append(dl_url)

    query_out = {'results': results, 'urls': urls, 'filenames': filenames, 'headers': headers, 
                 'access_token': access_token, 'broker_address': broker_address, 
                 'number_of_results': numberOfResults, 'response': response}
    return query_out
