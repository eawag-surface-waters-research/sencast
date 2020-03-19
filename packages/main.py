#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time
from packages.auxil import read_parameters_file
from packages.background_processing import start_processing_threads
from packages.download_hda_query import query_dl_hda
from packages.download_coah_query import start_download_threads
from packages import path_config


def hindcast(params_filename):

    # *********************************************************
    # Check paths
    # *********************************************************
    params_path = os.path.join(path_config.params_path, params_filename)
    if not os.path.isfile(params_path):
        print('Parameter file {} not found.'.format(params_path))
        return
    params = read_parameters_file(params_path, wkt_dir=path_config.wkt_dir, verbose=True)
    l1_dir = os.path.join(path_config.cwd, 'input_data')
    if not os.path.isdir(l1_dir):
        print('"input_data" directory not found in {} home folder'.format(path_config.user))
        return
    l2_dir = os.path.join(path_config.cwd, 'output_data')
    if not os.path.isdir(l2_dir):
        print('"output_data" directory not found in {} home folder'.format(path_config.user))
        return
    params['gpt_path'] = path_config.gpt_path

    # *********************************************************
    # Initialisation of input folders
    # *********************************************************
    dir_dict = {'L1 dir': os.path.join(l1_dir, params['sensor'].upper() + '_L1')}
    if not os.path.isdir(dir_dict['L1 dir']):
        os.mkdir(dir_dict['L1 dir'])
    wktfn = os.path.basename(params['wkt file']).split('.')[0]
    print('WKT file: {}'.format(params['wkt file']))

    # *********************************************************
    # Initialisation of output folders
    # *********************************************************
    L2_dir_sensor = os.path.join(l2_dir, params['sensor'].upper() + '_L2')
    if not os.path.isdir(L2_dir_sensor):
        os.mkdir(L2_dir_sensor)
    dir_dict['proj dir'] = os.path.join(L2_dir_sensor, params['name'] + '_' + wktfn + '_' + params['start'][:10] + '_' + params['end'][:10])
    if not os.path.isdir(dir_dict['proj dir']):
        os.mkdir(dir_dict['proj dir'])
    dir_dict['qlrgb dir'] = os.path.join(dir_dict['proj dir'], 'L1P-rgb-quicklooks')
    if not os.path.isdir(dir_dict['qlrgb dir']):
        os.mkdir(dir_dict['qlrgb dir'])
    dir_dict['qlfc dir'] = os.path.join(dir_dict['proj dir'], 'L1P-falsecolor-quicklooks')
    if not os.path.isdir(dir_dict['qlfc dir']):
        os.mkdir(dir_dict['qlfc dir'])

    # Idepix
    dir_dict['L1P dir'] = os.path.join(dir_dict['proj dir'], 'L1P_' +
                                       str(os.path.basename(params['wkt file']).split('.')[0]))
    if not os.path.isdir(dir_dict['L1P dir']):
        os.mkdir(dir_dict['L1P dir'])

    # C2RCC
    if '1' in params['pcombo']:
        print('Creating C2RCC map directories')
        for c2rb in params['c2rcc bands']:
            c2name = os.path.join(dir_dict['proj dir'], 'L2C2R-' + c2rb)
            if not os.path.isdir(c2name):
                os.mkdir(c2name)
            dir_dict[c2rb] = c2name
        print('Creating C2RCC L2 directory')
        c2rcc_dir = os.path.join(dir_dict['proj dir'], 'L2C2R')
        if not os.path.isdir(c2rcc_dir):
            os.mkdir(c2rcc_dir)
        dir_dict['c2rcc dir'] = c2rcc_dir

    # Polymer
    if '2' in params['pcombo']:
        print('Creating Polymer map directories')
        for polyb in params['polymer bands']:
            polyname = os.path.join(dir_dict['proj dir'], 'L2POLY-' + polyb)
            if not os.path.isdir(polyname):
                os.mkdir(polyname)
            dir_dict[polyb] = polyname
        print('Creating Polymer L2 directory')
        polymer_dir = os.path.join(dir_dict['proj dir'], 'L2POLY')
        if not os.path.isdir(polymer_dir):
            os.mkdir(polymer_dir)
        dir_dict['polymer dir'] = polymer_dir

    # MPH
    if '3' in params['pcombo'] and params['sensor'].upper() == 'OLCI':
        print('Creating MPH map directories')
        for mphb in params['mph bands']:
            mphname = os.path.join(dir_dict['proj dir'], 'L2MPH-' + mphb)
            if not os.path.isdir(mphname):
                os.mkdir(mphname)
            dir_dict[mphb] = mphname
        print('Creating MPH L2 directory')
        mph_dir = os.path.join(dir_dict['proj dir'], 'L2MPH')
        if not os.path.isdir(mph_dir):
            os.mkdir(mph_dir)
        dir_dict['mph dir'] = mph_dir

    # *********************************************************
    # Download products
    # *********************************************************
    print("Starting download threads using {}".format(params['API']))
    if params['API'] == "HDA":
        product_paths_available, product_paths_to_download, download_threads = query_dl_hda(params, dir_dict['L1 dir'])
    elif params['API'] == "COAH":
        product_paths_available, product_paths_to_download, download_threads = start_download_threads(params, dir_dict['L1 dir'])
    else:
        raise RuntimeError("Unknown API: {} (possible options are 'HDA' or 'COAH').".format(params['API']))
    print("{} products are already available.".format(len(product_paths_available)))
    print("{} products are being downloaded by individual threads.".format(len(product_paths_to_download)))

    # *********************************************************
    # Processing
    # *********************************************************
    starttime = time.time()
    processing_threads = start_processing_threads(params, dir_dict, product_paths_available, product_paths_to_download, download_threads)
    print("Started processing of the products by indivitual threads. Some products may still be downloading.")
    for processing_thread in processing_threads:
        processing_thread.join()
    print("Processing complete in {0:.1f} seconds.".format(time.time() - starttime))
