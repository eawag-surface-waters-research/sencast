#! /usr/bin/env python
# -*- coding: utf-8 -*-

# sys.path.append('/home/odermatt/.snap/snap-python')

import sys
import os
import time
from packages.MyProductc import MyProduct
from snappy import ProductIO
from packages.auxil import read_parameters_file
from packages.background_processing import background_processing
from packages.download_hda_query import query_dl_hda
from packages.download_coah_query import query_dl_coah
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
    # Download products
    # *********************************************************
    if params['API'] == 'HDA':
        print('HDA query...')
        xmlfs = query_dl_hda(params, dir_dict['L1 dir'], max_threads=4)
        print('HDA query completed.')
    elif params['API'] == 'COAH':
        print('COAH query...')
        xmlfs = query_dl_coah(params, dir_dict['L1 dir'])
        print('COAH query completed.')
    else:
        print('API unknown (possible options are ''HDA'' or ''COAH''), exiting.')
        sys.exit()
    if xmlfs:
        if params['sensor'] == 'OLCI':
            xmlfs.sort(key=lambda path: path.split('R___')[1])
        elif params['sensor'] == 'MSI':
            xmlfs.sort(key=lambda path: path.split('_MSIL1C_')[1])
        else:
            xmlfs.sort()
        print()

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
    # Processing
    # *********************************************************
        starttime = time.time()
        nbtot = len(xmlfs)
        c = 1
        for xmlf in xmlfs:
            products = [ProductIO.readProduct(xmlf)]
            myproduct = MyProduct(products, params, dir_dict['L1 dir'])

        # FOR S3 MAKE SURE THE NON-DEFAULT S3TBX SETTING IS SELECTED IN THE SNAP PREFERENCES!
            if params['sensor'] == 'OLCI' and 'PixelGeoCoding2' not in str(myproduct.products[0].getSceneGeoCoding()):
                print()
                sys.exit('The S3 product was read without pixelwise geocoding, please check the preference settings of the S3TBX!')

            print('\033[1mProcessing product ({}/{}): {}...\033[0m\n'.format(c, nbtot, products[0].getName()))
            startt = time.time()
            background_processing(myproduct, params, dir_dict)
            myproduct.close()
            print('\nProduct processed in {0:.1f} seconds.\n'.format(time.time() - startt))
            c += 1
        print('\nProcessing complete in {0:.1f} seconds.'.format(time.time() - starttime))

    else:
        print('No product found for this date range... Exiting.')
        return
