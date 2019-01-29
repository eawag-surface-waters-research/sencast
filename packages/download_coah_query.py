#! /usr/bin/env python
# coding: utf8

import os
from snappy import ProductIO
from subprocess import check_output
import re
from packages.auxil import list_xml_scene_dir
from zipfile import ZipFile
import getpass


def write_url_list(filename, urls):
    with open(filename, 'w') as f:
        for url in urls:
            f.write(url+'\n')


def read_products_urls(fname):
    temp = []
    with open(fname, 'r') as f:
        for l in f:
            temp.append(l)
    purls = []
    for pn in temp:
        purls.append(re.findall('(?<=,).*$', pn)[0])
    return purls 


def read_products_list(fname):
    temp = []
    with open(fname, 'r') as f:
        for l in f:
            temp.append(l)
    pnames = []
    for pn in temp:
        pnames.append(re.match('^(.*)(,http)', pn).group(1))
    return pnames 

    
def wc(filename):
    return int(check_output(["wc", "-l", filename]).split()[0])

    
def query_dl_coah(dhusget_fullname, params, outdir):
    xmlf = []
    wd = os.getcwd()
    if params['sensor'].upper() == 'OLCI':
        datatype = 'OL_1_EFR___'
    elif params['sensor'].upper() == 'MSI':
        datatype = 'S2MSI1C'
    print('\nQuery...')
    # Get geometry
    wkt = params['wkt']
    corners = re.findall("[-]?\d+\.\d+", wkt)
    geometry = corners[0] + ',' + corners[1] + ':' + corners[4] + ',' + corners[5]
#     output = check_output('bash ' + dhusget_fullname + ' -u ' + params['username'] + \
#                           ' -p ' + params['password'] + ' -i ' + params['sensor'].lower() + ' -S ' + \
#                           params['start'] + ' -E ' + params['end'] + ' -c ' + geometry + \
#                           ' -T ' + datatype + ' -l 50 -W 1 -w 5 -o product -O ' + outdir, shell=True)
    output = check_output('bash ' + dhusget_fullname + ' -u ' + params['username'] + \
                          ' -p ' + params['password'] + ' -i ' + params['sensor'].lower() + ' -S ' + \
                          params['start'] + ' -E ' + params['end'] + ' -c ' + geometry + \
                          ' -T ' + datatype + ' -l 100 -W 1 -w 5', shell=True)
    print(output)
    nb_product = wc(os.path.join(wd, 'products-list.csv'))
    print('\nQuery completed: {} product(s) found.'.format(nb_product))
    
    purls = read_products_urls(os.path.join(wd, 'products-list.csv'))
    all_pnames = read_products_list(os.path.join(wd, 'products-list.csv'))
    
    urls, pnames = [], []
    c = 0
    for pn in all_pnames:
        if pn.split('.')[0] not in os.listdir(outdir):
            urls.append('"'+purls[c]+'/$value"')
            pnames.append(pn)
        c += 1
        
    if urls:
        user = getpass.getuser()
        url_list  = os.path.join(outdir,'urls_list_'+user+'.txt')
        write_url_list(url_list, urls)
        max_threads = min(2, len(urls))
        print('\nDownloading {} product(s)...'.format(len(urls)))
        # Go to saving directory (the --content-disposition option save the file with the proper filename
        # but in the current directory)
        os.chdir(outdir)
        os.system('cat ' + url_list +' | xargs -n 1 -P ' + str(max_threads) + \
                  ' wget --content-disposition --continue --user='+params['username']+\
                  ' --password='+params['password'])
        # Go back to working directory
        os.chdir(wd)
        
        # Check if products were actually dowloaded:
        lsdir = [lsd.split('.')[0] for lsd in os.listdir(outdir)]
        c = 0
        for pn in pnames:
            if pn in lsdir:
                c += 1
        if c != len(pnames):
            print('Download(s) failed, another user might be using COAH services with the same credentials.' +\
                  ' Either wait for the other user to finish their job or change the credentials in the parameter file.')
            os.remove(url_list)
            return
        else:
            print('\nDownload complete.')
            
        os.remove(url_list)
        for pn in pnames:
            zf = [os.path.join(outdir, zf) for zf in os.listdir(outdir) if pn.split('.')[0] in zf]
            tempdir = os.path.join(outdir, zf[0].split('.')[0])
            os.mkdir(tempdir)
            with ZipFile(zf[0], 'r') as zipf:
                zipf.extractall(tempdir)
            os.remove(os.path.join(outdir, zf[0]))
    else:
        print('\nAll products already downloaded, skipping...')
    
    os.system('rm -f ' + os.path.join(wd, 'OSquery-result.xml') + ' ' + \
              os.path.join(wd, 'product_list') +  ' ' + os.path.join(wd, 'failed_MD5_check_list.txt') + \
              ' ' + os.path.join(wd, 'products-list.csv'))
    if nb_product > 0:
       # Read products
        xmlf = list_xml_scene_dir(outdir, sensor=params['sensor'], file_list=all_pnames)
    return xmlf
