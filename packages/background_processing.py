import numpy
import os
import subprocess
import sys

from threading import Semaphore, Thread
from haversine import haversine

from packages.MyProductc import MyProduct
from packages.product_fun import get_corner_pixels_ROI
from packages import path_config
from snappy import jpy, GPF, WKTReader, ProductIO

from packages.ql_mapping import plot_pic, plot_map
from packages.product_fun import get_UL_LR_geo_ROI
from packages.ancillary import Ancillary_NASA
from packages.auxil import gpt_xml

from polymer.main import run_atm_corr
from polymer.main import Level1, Level2
from polymer.level1_msi import Level1_MSI
from polymer.gsw import GSW
from polymer.level2 import default_datasets


def start_processing_threads(params, dir_dict, product_paths_available, product_paths_to_download, download_threads, max_parallel_processing=1):
    processing_threads = []
    semaphore = Semaphore(max_parallel_processing)

    for product_path in product_paths_available:
        processing_threads.append(Thread(target=do_processing, args=(params, dir_dict, product_path, semaphore)))
        processing_threads[-1].start()

    for product_path, download_thread in zip(product_paths_to_download, download_threads):
        processing_threads.append(Thread(target=do_processing, args=(params, dir_dict, product_path, semaphore, download_thread)))
        processing_threads[-1].start()

    return processing_threads


def do_processing(params, dir_dict, product_path, semaphore, download_thread=None):
    if download_thread:
        download_thread.join()

    with semaphore:
        product = ProductIO.readProduct(os.path.join(product_path))

        # FOR S3 MAKE SURE THE NON-DEFAULT S3TBX SETTING IS SELECTED IN THE SNAP PREFERENCES!
        if params['sensor'] == 'OLCI' and 'PixelGeoCoding2' not in str(product.getSceneGeoCoding()):
            sys.exit('The S3 product was read without pixelwise geocoding, please check the preference settings of the S3TBX!')

        FileReader = jpy.get_type('java.io.FileReader')
        GPF.getDefaultInstance().getOperatorSpiRegistry().loadOperatorSpis()
        oriproduct = MyProduct([product], params, dir_dict['L1 dir'])

        # ------ Initializing the output raster ---------#
        perimeter = WKTReader().read(FileReader(params['wkt file']))
        lats = []
        lons = []
        for coordinate in perimeter.getCoordinates():
            lats.append(coordinate.y)
            lons.append(coordinate.x)
        x_dist = haversine((min(lats), min(lons)), (min(lats), max(lons)))
        y_dist = haversine((min(lats), min(lons)), (max(lats), min(lons)))
        x_pix = int(round(x_dist / (int(params['resolution'])/1000)))
        y_pix = int(round(y_dist / (int(params['resolution'])/1000)))
        x_pixsize = (max(lons) - min(lons)) / x_pix
        y_pixsize = (max(lats) - min(lats)) / y_pix

        # ---------------- Initialising ------------------#
        l1name = product.getName()
        if params['sensor'].lower() == 'msi':
            l1name = l1name + '.SAFE'
        l1rname = 'reproj_' + l1name + '.nc'
        l1pname = 'L1P_' + l1rname
        l1mname = 'merged_' + l1pname
        l1_path = os.path.join(dir_dict['L1 dir'], l1name.split('.')[0], l1name)
        l1r_path = './' + l1rname
        l1p_path = os.path.join(dir_dict['L1P dir'], l1pname)
        l1m_path = './' + l1mname
        run_process = [False, False, False, False]
        if os.path.isfile(l1p_path):
            print('\nSkipping Idepix: ' + l1pname + ' already exists.')
        else:
            run_process[0] = True
        if '1' in params['pcombo']:
            l2c2rname = 'L2C2R_' + l1pname
            l2c2r_path = os.path.join(dir_dict['c2rcc dir'], l2c2rname)
            if os.path.isfile(l2c2r_path):
                print('\nSkipping C2RCC: ' + l2c2rname + ' already exists.')
            else:
                run_process[1] = True
        if '2' in params['pcombo']:
            polytempname = 'L2POLY_' + l1name + '.nc'
            polyname = 'L2POLY_' + l1pname
            # Somehow polymer doesn't seem to write to other places than the package location
            polytemp_path = os.path.join(path_config.polymer_path, polytempname)
            poly_path = os.path.join(dir_dict['polymer dir'], polyname)
            if os.path.isfile(poly_path):
                print('\nSkipping Polymer: ' + polyname + ' already exists.')
            else:
                run_process[2] = True
        if '3' in params['pcombo']:
            mphname = ''
            mph_path = ''
            if os.path.isfile(mph_path):
                print('\nSkipping MPH: ' + mphname + ' already exists.')
            else:
                run_process[3] = True

        # ----------------- Reprojecting ----------------- #
        # This creates always the same raster for a given set of wkt, sensor and resolution
        if any(run_process):
            op_str = 'Reproject'
            xml_path = './reproj_temp.xml'
            parameters = MyProduct.HashMap()
            parameters.put('referencePixelX', '0')
            parameters.put('referencePixelY', '0')
            parameters.put('easting', str(min(lons)))
            parameters.put('northing', str(max(lats)))
            parameters.put('pixelSizeX', str(x_pixsize))
            parameters.put('pixelSizeY', str(y_pixsize))
            parameters.put('width', str(x_pix))
            parameters.put('height', str(y_pix))
            parameters.put('sensor', params['sensor'].lower())
            gpt_xml(operator=op_str, product_parameters=parameters, xml_path=xml_path)
            print()
            print('Reprojecting L1 product...')
            subprocess.call([path_config.gpt_path, xml_path, '-SsourceProduct=' + l1_path, '-PtargetProduct=' + l1r_path])
            os.remove('./reproj_temp.xml')

        # ---------------------- Idepix ---------------------- #
        if run_process[0]:
            if params['sensor'].lower() == 'olci':
                op_str = 'Idepix.Olci'
            elif params['sensor'].lower() == 'msi':
                op_str = 'Idepix.S2'
            else:
                raise RuntimeError("Unknown Sensor: {}".format(params['sensor']))
            xml_path = './idepix_temp.xml'
            parameters = MyProduct.HashMap()
            gpt_xml(operator=op_str, product_parameters=parameters, xml_path=xml_path)
            wktfn = os.path.basename(params['wkt file']).split('.')[0]
            print()
            print('Writing L1P_{} product to disk...'.format(wktfn))
            subprocess.call([path_config.gpt_path, xml_path, '-SsourceProduct=' + l1r_path, '-PtargetProduct=' + l1p_path])
            os.remove('./idepix_temp.xml')

            # --------------------- Quicklooks -------------------- #
            print()
            print('Saving quicklooks to disk...')
            if params['sensor'].upper() == 'MSI':
                rgb_bands = params['True color']
                fc_bands = params['False color']
            elif params['sensor'].upper() == 'OLCI':
                rgb_bands = [bn.replace('radiance', 'reflectance') for bn in params['True color']]
                fc_bands = [bn.replace('radiance', 'reflectance') for bn in params['False color']]
            else:
                raise RuntimeError("Unknown Sensor: {}".format(params['sensor']))
            l1p_product = ProductIO.readProduct(l1p_path)
            pname = l1p_product.getName()
            tcname = os.path.join(dir_dict['qlrgb dir'], pname.split('.')[0] + '_rgb.png')
            fcname = os.path.join(dir_dict['qlfc dir'], pname.split('.')[0] + '_falsecolor.png')
            plot_pic(l1p_product, tcname, rgb_layers=rgb_bands, grid=True, max_val=0.16,
                     perimeter_file=params['wkt file'])
            plot_pic(l1p_product, fcname, rgb_layers=fc_bands, grid=True, max_val=0.3,
                     perimeter_file=params['wkt file'])

        # -------------------- C2RCC -------------------------- #
        # Idepix and Reproj output must be merged first
        if run_process[1]:
            print()
            print('Merging Reprojected L1 and Idepix products...')
            subprocess.call([path_config.gpt_path, 'Merge', '-SmasterProduct=' + l1r_path, '-Ssource=' + l1p_path, '-t', l1m_path])
            if os.path.isfile(l2c2r_path):
                print('\nSkipping C2RCC: ' + l2c2rname + ' already exists.')
            else:
                print()
                print('\nProcessing with the C2RCC algorithm...')
                op_str = 'c2rcc.' + params['sensor'].lower()
                xml_path = './c2rcc_temp.xml'
                parameters = MyProduct.HashMap()
                parameters.put('validPixelExpression', params['validexpression'])
                if params['sensor'].upper() == 'MSI':
                    cwd = os.getcwd()
                    os.chdir(path_config.polymer_path)
                    ancillary = Ancillary_NASA()
                    os.chdir(cwd)
                    lat, lon = get_UL_LR_geo_ROI(product, params)
                    lat = numpy.nanmean(lat)
                    lon = numpy.nanmean(lon)
                    coords = lat, lon
                    try:
                        ozone = ancillary.get('ozone', oriproduct.date[0])
                        ozone = numpy.round(ozone[coords])
                    except:
                        ozone = 300.
                        print('Retrieving estimated ozone did not work; using default value 300')
                        pass
                    try:
                        surfpress = ancillary.get('surf_press', oriproduct.date[0])
                        surfpress = numpy.round(surfpress[coords])
                    except:
                        surfpress = 1000.
                        print('Retrieving estimated atm. pressure did not work; using default value 1000')
                    parameters.put('ozone', ozone)
                    parameters.put('press', surfpress)
                    parameters.put('salinity', 0.05)
                    print('Default salinity is 0.05 PSU for freshwater')
                else:
                    parameters.put('useEcmwfAuxData', True)
                if params['c2rcc altnn'] != '':
                    print('Using alternative NN specified in param file...')
                    parameters.put('alternativeNNPath', params['c2rcc altnn'])
                else:
                    print('Using default NN...')
                gpt_xml(operator=op_str, product_parameters=parameters, xml_path=xml_path)
                subprocess.call([path_config.gpt_path, xml_path, '-SsourceProduct=' + l1m_path, '-PtargetProduct=' + l2c2r_path])
                os.remove('./c2rcc_temp.xml')
                l2c2r_product = ProductIO.readProduct(l2c2r_path)
                print('\nCreating quicklooks for bands: {}\n'.format(params['c2rcc bands']))
                params_range = params['c2rcc max']
                c = 0
                for bn in params['c2rcc bands']:
                    if params_range[c] == 0:
                        param_range = False
                    else:
                        param_range = [0, params_range[c]]
                    c += 1
                    ql_path = os.path.join(dir_dict[bn], l2c2rname.split('.')[0] + '_' + bn + '.png')
                    plot_map(l2c2r_product, ql_path, bn, basemap='srtm_hillshade', grid=True,
                             perimeter_file=params['wkt file'], param_range=param_range)
                    print('Plot for band {} finished.\n'.format(bn))
        if os.path.isfile(l1r_path):
            os.remove(l1r_path)
        if os.path.isfile(l1m_path):
            os.remove(l1m_path)

        # ------------------ Polymer ------------------#
        if run_process[2]:
            colloc_xml = os.path.join(path_config.cwd, 'xml', 'poly-colloc.xml')
            if not os.path.isdir('data_landmask_gsw'):
                os.mkdir('data_landmask_gsw')
            if os.path.isfile(os.path.join(dir_dict['polymer dir'], polyname)):
                print('Skipping Polymer: ' + polyname + ' already exists.')
            else:
                print('\nApplying Polymer...')
                cwd = os.getcwd()
                os.chdir(path_config.polymer_path)
                UL, UR, LR, LL = get_corner_pixels_ROI(product, params)
                sline = min(UL[0], UR[0])
                eline = max(LL[0], LR[0])
                scol = min(UL[1], UR[1])
                ecol = max(LL[1], LR[1])
                if params['sensor'].upper() == 'MSI':
                    run_atm_corr(Level1_MSI(l1_path, sline=sline, scol=scol, eline=eline, ecol=ecol, landmask=GSW(),
                                 resolution=params['res']), Level2(filename=polytemp_path, fmt='netcdf4', overwrite=True,
                                 datasets=default_datasets + ['sza']))
                elif params['sensor'].upper() == 'OLCI':
                    run_atm_corr(Level1(l1_path, sline=sline, scol=scol, eline=eline, ecol=ecol, landmask=GSW(agg=8)),
                                 Level2(filename=polytemp_path, fmt='netcdf4', overwrite=True,
                                 datasets=default_datasets + ['vaa', 'vza', 'saa', 'sza']))
                subprocess.call([path_config.gpt_path, colloc_xml, '-SmasterProduct=' + l1p_path,
                                 '-SslaveProduct=' + polytemp_path, '-PtargetProduct=' + poly_path])
                poly_product = ProductIO.readProduct(poly_path)
                print('\nCreating quicklooks for bands: {}\n'.format(params['polymer bands']))
                params_range = params['polymer max']
                c = 0
                for bn in params['polymer bands']:
                    if params_range[c] == 0:
                        param_range = False
                    else:
                        param_range = [0, params_range[c]]
                    c += 1
                    ql_path = os.path.join(dir_dict[bn], polyname.split('.')[0] + '_' + bn + '.png')
                    plot_map(poly_product, ql_path, bn, basemap='srtm_hillshade', grid=True,
                             perimeter_file=params['wkt file'], param_range=param_range)
                    print('Plot for band {} finished.\n'.format(bn))
                os.remove(polytemp_path)
                os.chdir(cwd)

        deriproduct = oriproduct
        pmode = 3

        # ------------------ MPH ------------------------ #
        if '3' in params['pcombo'] and params['sensor'].upper() == 'OLCI':
            if os.path.isfile(os.path.join(dir_dict['mph dir'], 'L2MPH_' + deriproduct.products[0].getName() + '.nc'))\
                    or os.path.isfile(os.path.join(dir_dict['mph dir'], 'L2MPH_reproj_' + deriproduct.products[0].getName() + '.nc')):
                print('Skipping MPH: L2MPH_L1P_' + deriproduct.products[0].getName() + '.nc' + ' already exists.')
            else:
                print('\nMPH...')
                mphproduct = MyProduct(deriproduct.products, deriproduct.params, deriproduct.path)
                mphproduct.mph()
                for product in mphproduct.products:
                    pname = product.getName()
                    print('\nCreating quicklooks for bands: {}\n'.format(params['mph bands']))
                    # Check if parameter range is provided
                    params_range = params['mph max']
                    c = 0
                    for bn in params['mph bands']:
                        if params_range[c] == 0:
                            param_range = False
                        else:
                            param_range = [0, params_range[c]]
                        c += 1
                        bname = os.path.join(dir_dict[bn], pname.split('.')[0] + '_' + bn + '.png')
                        plot_map(product, bname, bn, basemap='srtm_hillshade', grid=True,
                                 perimeter_file=params['wkt file'], param_range=param_range)
                        print('Plot for band {} finished.\n'.format(bn))
                if pmode in ['2', '3']:
                    print('\nWriting L2MPH product to disk...')
                    mphproduct.write(dir_dict['mph dir'])
                    print('Writing completed.')
                mphproduct.close()

        oriproduct.close()


def do_reproject():
    print()


def do_idepix():
    print()


def do_c2rcc():
    print()


def do_polymer():
    print()


def do_mph():
    print()
