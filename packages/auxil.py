#! /usr/bin/env python
# coding: utf8


import sys
import os
import re
import requests
import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from snappy import ProductIO


def open_wkt(wkt):
    with open(wkt, 'r') as f:
        wkt = f.read()
    return wkt


def  list_xml_scene_dir(scenesdir, sensor='OLCI', file_list=[]):
    if sensor.upper() == 'OLCI':
        if not file_list:
            prod_paths = [os.path.join(scenesdir, prod_name) for prod_name in os.listdir(scenesdir) if 'S3' in prod_name]
        else:
            prod_paths = [os.path.join(scenesdir, prod_name) for prod_name in os.listdir(scenesdir) if prod_name in file_list]
        sd = []
        for d in prod_paths:
            temp = [os.path.join(d, cd) for cd in os.listdir(d) if 'S3' in cd]
            sd.append(temp[0])
        xmlfs = []
        for s in sd:
            temp = [os.path.join(s, cd) for cd in os.listdir(s) if 'xml' in cd]
            if temp == []:
                print('no xml found in ' + s)
            else:
                print(s)
                print(temp[0])
                xmlfs.append(temp[0])
    elif sensor.upper() == 'MSI':
        if not file_list:
            prod_paths = [os.path.join(scenesdir, nd) for nd in os.listdir(scenesdir) if 'S2' in nd]
        else:
            prod_paths = [os.path.join(scenesdir, nd) for nd in os.listdir(scenesdir) if nd in file_list]
        sd = []
        for d in prod_paths:
            temp = [os.path.join(d, cd) for cd in os.listdir(d) if 'SAFE' in cd]
            sd.append(temp[0])
        xmlfs = []
        for s in sd:
            temp = [os.path.join(s, cd) for cd in os.listdir(s) if 'MSI' in cd and 'xml' in cd]
            xmlfs.append(temp[0])
    return xmlfs


def open_products(product_directory):
    xmlfs = list_xml_scene_dir(product_directory)
    return [ProductIO.readProduct(xml) for xml in xmlfs]


def create_polymer_product(polymer_out, original_sentinel_file):
    product = ProductIO.readProduct(original_sentinel_file)
    w, h, b = polymer_out.Rw.shape
    print(w, h, b)
    

def get_S3_products_list(rootdir):
    product_dirs = [os.path.join(rootdir, f) for f in os.listdir(rootdir) if 'S3' in f]
    products = []
    for product_dir in product_dirs:
        scene_dir = [os.path.join(product_dir, f) for f in os.listdir(product_dir) if 'SEN3' in f]
        scene_date = re.search('\d{8}T\d{6}', scene_dir[0]).group(0)
        xml_file = [os.path.join(scene_dir[0], f) for f in os.listdir(scene_dir[0]) if 'xml' in f]
        # Read product
        product = ProductIO.readProduct(xml_file[0])
        products.append(product)
    return products


def read_parameters_file(filename, verbose=True, wkt_dir='/home/odermatt/wkt'):
    if verbose:
        print('Reading file: ' + filename)
        print()
    params_list = []
    with open(filename, 'r') as f:
        for line in f:
            params_list.append(line)
    
#     name = [re.findall("'([^']*)'", x) for x in params_list if 'name' in x.lower()][0][0]
    name = os.path.basename(filename.split('.')[0])
    sensor = [re.findall("'([^']*)'", x) for x in params_list if 'sensor' in x.lower()][0][0]
    if 'MSI' in sensor.upper():
        if verbose:
            print('Sensor: MSI')
        satnumber = 2
        sensorname = '' # Used to call the Idepix operator
    elif 'OLCI' in sensor.upper():
        if verbose:
            print('Sensor: OLCI')
        satnumber = 3
        sensorname = '.Olci'  # Used to call the Idepix operator
    else:
        print('No valid sensor detected in the parameter file.' + \
              ' Valid options are either <MSI> or <OLCI>')
        sys.exit()
    region = [re.findall("'([^']*)'", x) for x in params_list if 'region=' in x.lower()][0][0]
    tile = [re.findall("'([^']*)'", x) for x in params_list if 'tile=' in x.lower()]
    tile = [e.strip() for e in tile[0][0].split(',')]
    start = [re.findall("'([^']*)'", x) for x in params_list if 'start=' in x][0][0]
    end = [re.findall("'([^']*)'", x) for x in params_list if 'end=' in x][0][0]
    rgb = [re.findall("'([^']*)'", x) for x in params_list if 'rgb_bands=' in x]
    rgb = [e.strip() for e in rgb[0][0].split(',')]
    falsecolor = [re.findall("'([^']*)'", x) for x in params_list if 'false_color_bands=' in x]
    falsecolor = [e.strip() for e in falsecolor[0][0].split(',')]
    wkt = [re.findall("'([^']*)'", x) for x in params_list if 'wkt=' in x.lower()][0][0]
    wkt_file = os.path.join(wkt_dir, wkt)
    wkt = open_wkt(os.path.join(wkt_dir, wkt))
    validexpression = [re.findall("'([^']*)'", x) for x in params_list if 'validexpression=' in x.lower()][0][0]
    pcombo = [re.findall("'([^']*)'", x) for x in params_list if 'pcombo=' in x]
    pcombo = [e.strip() for e in pcombo[0][0].split(',')]
    pmode = [re.findall("'([^']*)'", x) for x in params_list if 'pmode=' in x.lower()][0][0]
    qmode = [re.findall("'([^']*)'", x) for x in params_list if 'qmode=' in x.lower()][0][0]
    API = [re.findall("'([^']*)'", x) for x in params_list if 'api=' in x.lower()][0][0]
    username = [re.findall("'([^']*)'", x) for x in params_list if 'username=' in x.lower()][0][0]
    password = [re.findall("'([^']*)'", x) for x in params_list if 'password=' in x.lower()][0][0]
    c2rcc_bands = [re.findall("'([^']*)'", x) for x in params_list if 'c2rcc_bands=' in x.lower()]
    c2rcc_bands = [e.strip() for e in c2rcc_bands[0][0].split(',')]
    c2rcc_max = [re.findall("'([^']*)'", x) for x in params_list if 'c2rcc_maxbands=' in x.lower()]
    c2rcc_max = [float(e.strip()) for e in c2rcc_max[0][0].split(',')]
    polymer_bands = [re.findall("'([^']*)'", x) for x in params_list if 'polymer_bands=' in x.lower()]
    polymer_bands = [e.strip() for e in polymer_bands[0][0].split(',')]
    polymer_max = [re.findall("'([^']*)'", x) for x in params_list if 'polymer_maxbands=' in x.lower()]
    polymer_max = [float(e.strip()) for e in polymer_max[0][0].split(',')]
    mph_bands = [re.findall("'([^']*)'", x) for x in params_list if 'mph_bands=' in x.lower()]
    mph_bands = [e.strip() for e in mph_bands[0][0].split(',')]
    mph_max = [re.findall("'([^']*)'", x) for x in params_list if 'mph_maxbands=' in x.lower()]
    mph_max = [float(e.strip()) for e in mph_max[0][0].split(',')]
    if verbose:
        print('job name: ' + name)
        print('sensor: ' + sensor.upper())
        print('start: '+ start)
        print('end: '+ end)
    
    params = {'name': name, 'sensor': sensor.upper(), 'region': region.upper(), 'tile':
              tile, 'start': start, 'end': end, 'satnumber': satnumber, 
              'sensorname': sensorname, 'wkt': wkt, 'validexpression': validexpression,
              'True color': rgb, 'False color': falsecolor, 'qmode': qmode, 
              'pmode': pmode, 'API': API, 'username': username, 'password': password,
              'c2rcc bands': c2rcc_bands, 'polymer bands': polymer_bands, 'pcombo': pcombo,
              'wkt file': wkt_file, 'mph bands': mph_bands, 'c2rcc max': c2rcc_max, 
              'polymer max': polymer_max, 'mph max': mph_max}
    return params

