#! /usr/bin/env python
# -*- coding: utf-8 -*-

import sys
sys.path.append('/home/odermatt/.snap/snap-python')
from packages.MyProductc import MyProduct
from snappy import ProductIO
from packages.auxil import read_parameters_file
from packages.acs import interactive_processing, background_processing
from packages.download_hda_query import query_dl_hda
from packages.download_coah_query import query_dl_coah
import os, time
import getpass
import socket

            
def eawag_hindcast(params_filename):
    user = getpass.getuser()
    hostname = socket.gethostname()
    if hostname in ['daniels-macbook-pro.home', 'Daniels-MacBook-Pro.local']:
        os.chdir(os.path.join('/Users', user, 'Dropbox', 'Wrk Eawag', 'DIAS'))
        cwd = os.getcwd()
        wkt_dir = os.path.join(cwd, 'wkt')
        params_path = os.path.join('/Users', user, 'PycharmProjects', 'sentinel_hindcast', 'parameters', params_filename)
    elif hostname == 'SUR-ODERMADA-MC.local':
        os.chdir(os.path.join('/Volumes', 'DIAS-drive', 'DIAS'))
        cwd = os.getcwd()
        wkt_dir = os.path.join(cwd, 'wkt')
        params_path = os.path.join('/Users', user, 'PycharmProjects', 'sentinel_hindcast', 'parameters', params_filename)
    else:
        os.chdir(os.path.join('/home/', user))
        cwd = os.getcwd()
        wkt_dir = os.path.join(cwd, 'wkt')
        params_path = os.path.join(cwd, 'jupyter', 'sentinel_hindcast', 'parameters', params_filename)
    if not os.path.isfile(params_path):
        print('Parameter file {} not found.'.format(params_path))
        return
    params = read_parameters_file(params_path, wkt_dir=wkt_dir, verbose=True)
    L1_dir = os.path.join(cwd, 'input_data')
    if not os.path.isdir(L1_dir):
        print('"input_data" directory not found in {} home folder'.format(user))
        return
    L2_dir = os.path.join(cwd, 'output_data')
    if not os.path.isdir(L2_dir):
        print('"output_data" directory not found in {} home folder'.format(user))
        return
    #*********************************************************
    # Initialisation
    L1_dir_sensor = os.path.join(L1_dir, params['sensor'].upper() + '_L1')
    L2_dir_sensor = os.path.join(L2_dir, params['sensor'].upper() + '_L2')
    if not os.path.isdir(L1_dir_sensor):
        os.mkdir(L1_dir_sensor)
    if not os.path.isdir(L2_dir_sensor):
        os.mkdir(L2_dir_sensor)
    wktfn = os.path.basename(params['wkt file']).split('.')[0]
    print('WKT file: {}'.format(params['wkt file']))
    project_dir = os.path.join(L2_dir_sensor, params['name']+'_'+wktfn+'_'+params['start'][:10]+'_'+params['end'][:10])
#     project_dir = os.path.join(temp_dir, params['name'])
    print('Output folder: {}\n'.format(project_dir))
    if not os.path.isdir(project_dir):
        os.mkdir(project_dir)
        
    # Download products
    xmlfs = []
    if params['API'] == 'HDA':
        print('HDA query...')
        xmlfs = query_dl_hda(params, L1_dir_sensor, max_threads=4)
        print('HDA query completed.')
    elif params['API'] == 'COAH':
        print('COAH query...')
        xmlfs = query_dl_coah(params, L1_dir_sensor)
        print('COAH query completed.')
    else:
        print('API unknown (possible options are ''HDA'' or ''COAH''), exiting.')
        sys.exit()
        
    if xmlfs:
        # S3 is sorted by date, independent of satellite A or B... cool! feature needed for S2, too...
        if params['sensor'] == 'OLCI':
            xmlfs.sort(key=lambda path: path.split('R___')[1])
        else:
            xmlfs.sort()

        # Create required folders
        dir_dict = {}
        # Check qmode    
        if params['qmode'] == '2':
            print('\nqmode = {}, quicklooks will be saved in the project directory'.format(params['qmode']))
            qlrgb_dir = os.path.join(project_dir,'L1P-rgb-quicklooks')
            if not os.path.isdir(qlrgb_dir):
                os.mkdir(qlrgb_dir)
            dir_dict['qlrgb dir'] = qlrgb_dir
            qlfc_dir = os.path.join(project_dir,'L1P-falsecolor-quicklooks')
            if not os.path.isdir(qlfc_dir):
                os.mkdir(qlfc_dir)
            dir_dict['qlfc dir'] = qlfc_dir
            if params['pmode'] in ['2', '3']:
                print('pmode = {}. Idepix subset will be saved to the project directory'.format(params['pmode']))
                L1P_dir = os.path.join(project_dir,'L1P_'+os.path.basename(params['wkt file']).split('.')[0])
                if not os.path.isdir(L1P_dir):
                    os.mkdir(L1P_dir)
                dir_dict['L1P dir'] = L1P_dir
            
            # Check pcombo
            if '1' in params['pcombo']:
                # Create c2rcc directories
                print('Creating C2RCC map directories')
                for c2rb in params['c2rcc bands']:
                    c2name = os.path.join(project_dir,'L2C2R-' + c2rb)
                    if not os.path.isdir(c2name):
                        os.mkdir(c2name)
                    dir_dict[c2rb] = c2name
                if params['pmode'] in ['2', '3']:
                    print('Creating C2RCC L2 directory')
                    c2rcc_dir = os.path.join(project_dir,'L2C2R')
                    if not os.path.isdir(c2rcc_dir):
                        os.mkdir(c2rcc_dir)
                    dir_dict['c2rcc dir'] = c2rcc_dir
            if '2' in params['pcombo']:
                # Create polymer bands directory
                print('Creating Polymer map directories')
                for polyb in params['polymer bands']:
                    polyname = os.path.join(project_dir,'L2POLY-' + polyb)
                    if not os.path.isdir(polyname):
                        os.mkdir(polyname)
                    dir_dict[polyb] = polyname
                if params['pmode'] in ['2', '3']:
                    print('Creating Polymer L2 directory')
                    polymer_dir = os.path.join(project_dir,'L2POLY')
                    if not os.path.isdir(polymer_dir):
                        os.mkdir(polymer_dir)
                    dir_dict['polymer dir'] = polymer_dir
            if '3' in params['pcombo'] and params['sensor'].upper() == 'OLCI':
                # Create polymer bands directory
                print('Creating MPH map directories')
                for mphb in params['mph bands']:
                    mphname = os.path.join(project_dir, 'L2MPH-' + mphb)
                    if not os.path.isdir(mphname):
                        os.mkdir(mphname)
                    dir_dict[mphb] = mphname
                if params['pmode'] in ['2', '3']:
                    print('Creating MPH L2 directory')
                    mph_dir = os.path.join(project_dir,'L2MPH')
                    if not os.path.isdir(mph_dir):
                        os.mkdir(mph_dir)
                    dir_dict['mph dir'] = mph_dir

        print('\nInitialization complete.')

        #*********************************************************
        # Start processing
        # Check quicklooks handling mode
        #--------------- Interactive mode -----------------------#
        if params['qmode'] == '1':
            print('\nInteractive quicklooks handling mode')
            products = []
            for xmlf in xmlfs:
                products.append(ProductIO.readProduct(xmlf))
            myproduct = MyProduct(products, params, L1_dir_sensor)
            interactive_processing(myproduct, params, dir_dict)
            print('Processing complete.')
        #--------------- Background mode -----------------------#    
        elif params['qmode'] == '2':
            print('\nBackground quicklooks handling mode')
            if params['pmode'] == '1':
                print("Output products won't be written to the disk\n")
            elif params['pmode'] == '2':
                print('L2 products will be written to the disk\n')
            starttime = time.time()
            nbtot = len(xmlfs)
            c = 1
            for xmlf in xmlfs:
                products = []
                products.append(ProductIO.readProduct(xmlf))
                myproduct = MyProduct(products, params, L1_dir_sensor)
                print('\033[1mProcessing product ({}/{}): {}...\033[0m\n'.format(c, nbtot, products[0].getName()))
                startt = time.time()
                background_processing(myproduct, params, dir_dict, params['pmode'])
                myproduct.close()
                print('\nProduct processed in {0:.1f} seconds.\n'.format(time.time() - startt))
                c += 1
            print('\nProcessing complete in {0:.1f} seconds.'.format(time.time() - starttime))
        else:
            print('\nQuicklooks handling unknown... exiting.')
            return
    else:
        print('No product found for this date range... Exiting.')
        return