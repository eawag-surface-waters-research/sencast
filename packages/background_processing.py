import numpy
import os
import subprocess
import sys

from threading import Semaphore, Thread
from haversine import haversine

from packages.MyProductc import MyProduct
from packages.product_fun import get_corner_pixels_ROI
from snappy import WKTReader, ProductIO

from packages.ql_mapping import plot_pic, plot_map
from packages.product_fun import get_UL_LR_geo_ROI
from packages.ancillary import Ancillary_NASA
from packages import auxil
from packages.auxil import IDEPIX_NAME, IDEPIX_QL_NAME, C2RCC_NAME, C2RCC_QL_NAME, POLY_NAME, POLY_QL_NAME, MPH_NAME, MPH_QL_NAME

from polymer.main import run_atm_corr
from polymer.main import Level1, Level2
from polymer.level1_msi import Level1_MSI
from polymer.gsw import GSW
from polymer.level2 import default_datasets


def start_processing_threads(env, params, product_paths_available, product_paths_to_download, download_threads, max_parallel_processing=1):
    # initialize output paths, create them if they do not exist yet
    out_paths = auxil.init_out_paths(os.path.join(env['DIAS']['l2_path'].format(params['General']['sensor'])), params)

    processing_threads = []
    semaphore = Semaphore(max_parallel_processing)

    # creating and starting processes to process already available products
    for product_path in product_paths_available:
        processing_threads.append(Thread(target=do_processing, args=(env, params, product_path, out_paths, semaphore)))
        processing_threads[-1].start()

    # creating and starting threads to process after products which are being downloaded
    for product_path, download_thread in zip(product_paths_to_download, download_threads):
        processing_threads.append(Thread(target=do_processing, args=(env, params, product_path, out_paths, semaphore, download_thread)))
        processing_threads[-1].start()

    return processing_threads


def do_processing(env, params, product_path, out_paths, semaphore, download_thread=None):
    if download_thread:
        download_thread.join()

    with semaphore:
        product = ProductIO.readProduct(product_path)

        # FOR S3 MAKE SURE THE NON-DEFAULT S3TBX SETTING IS SELECTED IN THE SNAP PREFERENCES!
        if params['General']['sensor'] == 'OLCI' and 'PixelGeoCoding2' not in str(product.getSceneGeoCoding()):
            sys.exit('The S3 product was read without pixelwise geocoding, please check the preference settings of the S3TBX!')

        oriproduct = MyProduct([product], params, os.path.dirname(product_path))

        # ---------------- Initialising ------------------#
        product_name = os.path.basename(product_path)
        gpt = env['General']['gpt_path']
        wkt_file = os.path.join(env['DIAS']['wkt_path'], params['General']['wkt'])
        sensor = params['General']['sensor']

        if sensor == 'MSI':
            product_name = product_name + '.SAFE'

        l1r_name = 'reproj_{}.nc'.format(product_name)
        l1p_name = IDEPIX_NAME.format(product_name)
        l1m_name = 'merged_L1P_reproj_{}.nc'.format(product_name)
        l1r_path = os.path.join(out_paths['out_path'], l1r_name)
        l1p_path = os.path.join(out_paths['idepix_path'], l1p_name)
        l1m_path = os.path.join(out_paths['out_path'], l1m_name)

        run_process = [False, False, False, False]
        if os.path.isfile(l1p_path):
            print('\nSkipping Idepix: ' + l1p_name + ' already exists.')
        else:
            run_process[0] = True
        if '1' in params['General']['pcombo'].split(","):
            l2c2r_name = C2RCC_NAME.format(product_name)
            l2c2r_path = os.path.join(out_paths['c2rcc_path'], l2c2r_name)
            if os.path.isfile(l2c2r_path):
                print('\nSkipping C2RCC: ' + l2c2r_name + ' already exists.')
            else:
                run_process[1] = True
        if '2' in params['General']['pcombo'].split(","):
            poly_tmp_name = POLY_NAME.format(product_name) + ".tmp"
            poly_name = POLY_NAME.format(product_name)
            # Somehow polymer doesn't seem to write to other places than the package location
            poly_tmp_path = os.path.join(out_paths['poly_path'], poly_tmp_name)
            poly_path = os.path.join(out_paths['poly_path'], poly_name)
            if os.path.isfile(poly_path):
                print('\nSkipping Polymer: ' + poly_name + ' already exists.')
            else:
                run_process[2] = True
        if '3' in params['General']['pcombo'].split(","):
            mph_name = MPH_NAME.format(product_name)
            mph_path = os.path.join(out_paths['mph_path'], mph_name)
            if os.path.isfile(mph_path):
                print('\nSkipping MPH: ' + mph_name + ' already exists.')
            else:
                run_process[3] = True

        # ----------------- Reprojecting ----------------- #
        # This creates always the same raster for a given set of wkt and resolution
        if any(run_process):
            op_str = 'Reproject'
            xml_path = os.path.join(out_paths['out_path'], "reproj_temp.xml")
            parameters = create_reproject_parameters_from_wkt(wkt_file, params['General']['resolution'])
            auxil.gpt_xml(operator=op_str, product_parameters=parameters, xml_path=xml_path)
            print()
            print('Reprojecting L1 product...')
            subprocess.call([gpt, xml_path, '-SsourceProduct=' + product_path, '-PtargetProduct=' + l1r_path])

        # ---------------------- Idepix ---------------------- #
        if run_process[0]:
            if sensor == 'OLCI':
                op_str = 'Idepix.Olci'
            elif sensor == 'MSI':
                op_str = 'Idepix.S2'
            else:
                raise RuntimeError("Unknown Sensor: {}".format(sensor))
            xml_path = os.path.join(out_paths['out_path'], 'idepix_temp.xml')
            parameters = MyProduct.HashMap()
            auxil.gpt_xml(operator=op_str, product_parameters=parameters, xml_path=xml_path)
            print()
            print('Writing L1P product to disk...')
            subprocess.call([gpt, xml_path, '-SsourceProduct=' + l1r_path, '-PtargetProduct=' + l1p_path])
            create_l1p_quicklooks(wkt_file, params, out_paths, product_name)

        # -------------------- C2RCC -------------------------- #
        # Idepix and Reproj output must be merged first
        if run_process[1]:
            print()
            print('Merging Reprojected L1 and Idepix products...')
            subprocess.call([gpt, 'Merge', '-SmasterProduct=' + l1r_path, '-Ssource=' + l1p_path, '-t', l1m_path])
            if os.path.isfile(l2c2r_path):
                print('\nSkipping C2RCC: ' + l2c2r_name + ' already exists.')
            else:
                print()
                print('\nProcessing with the C2RCC algorithm...')
                op_str = 'c2rcc.' + sensor.lower()
                xml_path = os.path.join(out_paths['out_path'], 'c2rcc_temp.xml')
                parameters = MyProduct.HashMap()
                parameters.put('validPixelExpression', params['C2RCC']['validexpression'])
                if sensor == 'MSI':
                    cwd = os.getcwd()
                    os.chdir(env['General']['polymer_path'])
                    ancillary = Ancillary_NASA()
                    os.chdir(cwd)
                    lat, lon = get_UL_LR_geo_ROI(auxil.load_wkt(wkt_file))
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
                if params['C2RCC']['altnn'] != '':
                    print('Using alternative NN specified in param file...')
                    parameters.put('alternativeNNPath', params['C2RCC']['altnn'])
                else:
                    print('Using default NN...')
                auxil.gpt_xml(operator=op_str, product_parameters=parameters, xml_path=xml_path)
                subprocess.call([gpt, xml_path, '-SsourceProduct=' + l1m_path, '-PtargetProduct=' + l2c2r_path])
                create_c2rcc_quicklooks(wkt_file, params, out_paths, product_name)

        # ------------------ Polymer ------------------#
        if run_process[2]:
            os.makedirs(os.path.join(env['DIAS']['dias_path'], "data_landmask_gsw"), exist_ok=True)
            if os.path.isfile(os.path.join(out_paths['poly_path'], poly_name)):
                print('Skipping Polymer: ' + poly_name + ' already exists.')
            else:
                print('\nApplying Polymer...')
                cwd = os.getcwd()
                os.chdir(env['General']['polymer_path'])
                UL, UR, LR, LL = get_corner_pixels_ROI(product, wkt_file)
                sline = min(UL[0], UR[0])
                eline = max(LL[0], LR[0])
                scol = min(UL[1], UR[1])
                ecol = max(LL[1], LR[1])
                if sensor == 'MSI':
                    gsw = GSW(directory=os.path.join(env['DIAS']['dias_path'], "data_landmask_gsw"))
                    l1 = Level1_MSI(product_path, sline=sline, scol=scol, eline=eline, ecol=ecol, landmask=gsw, resolution=params['General']['resolution'])
                    l2 = Level2(filename=poly_tmp_path, fmt='netcdf4', overwrite=True, datasets=default_datasets + ['sza'])
                    run_atm_corr(l1, l2)
                elif sensor == 'OLCI':
                    gsw = GSW(directory=os.path.join(env['DIAS']['dias_path'], "data_landmask_gsw"), agg=8)
                    l1 = Level1(product_path, sline=sline, scol=scol, eline=eline, ecol=ecol, landmask=gsw)
                    l2 = Level2(filename=poly_tmp_path, fmt='netcdf4', overwrite=True, datasets=default_datasets + ['vaa', 'vza', 'saa', 'sza'])
                    run_atm_corr(l1, l2)
                colloc_xml = os.path.join(env['DIAS']['dias_path'], 'xml', 'poly-colloc.xml')
                subprocess.call([gpt, colloc_xml, '-SmasterProduct=' + l1p_path, '-SslaveProduct=' + poly_tmp_path, '-PtargetProduct=' + poly_path])
                create_poly_quicklooks(wkt_file, params, out_paths, product_name)
                os.remove(poly_tmp_path)
                os.chdir(cwd)

        deriproduct = oriproduct

        # ------------------ MPH ------------------------ #
        if '3' in params['General']['pcombo'].split(",") and sensor == 'OLCI':
            if os.path.isfile(os.path.join(out_paths['mph_path'], MPH_NAME.format(product_name))):
                print('Skipping MPH: L2MPH_L1P_' + deriproduct.products[0].getName() + '.nc' + ' already exists.')
            else:
                print('\nMPH...')
                mphproduct = MyProduct([ProductIO.readProduct(l1m_path)], params, os.path.dirname(l1m_path))
                mphproduct.mph()
                mphproduct.products[0].setName(MPH_NAME.format(product_name))
                print('\nWriting L2MPH product to disk...')
                mphproduct.write(out_paths['mph_path'])
                print('Writing completed.')
                mphproduct.close()
                create_mph_quicklooks(wkt_file, params, out_paths, product_name)

        oriproduct.close()

        if os.path.isfile(l1r_path):
            os.remove(l1r_path)
        if os.path.isfile(l1m_path):
            os.remove(l1m_path)


def create_l1p_quicklooks(wkt_file, params, out_paths, product_name):
    print("Creating quicklooks for IDEPIX")
    if params['General']['sensor'] == "MSI":
        rgb_bands = params['General']['rgb_bands'].split(",")
        fc_bands = params['General']['fc_bands'].split(",")
    elif params['General']['sensor'] == "OLCI":
        rgb_bands = [bn.replace('radiance', 'reflectance') for bn in params['IDEPIX']['rgb_bands'].split(",")]
        fc_bands = [bn.replace('radiance', 'reflectance') for bn in params['IDEPIX']['fc_bands'].split(",")]
    else:
        raise RuntimeError("Unknown Sensor: {}".format(params['General']['sensor']))

    product = ProductIO.readProduct(os.path.join(out_paths['idepix_path'], IDEPIX_NAME.format(product_name)))

    ql_path = os.path.join(out_paths['qlrgb_path'], IDEPIX_QL_NAME.format(product_name, "rgb"))
    plot_pic(product, ql_path, rgb_layers=rgb_bands, grid=True, max_val=0.16, perimeter_file=wkt_file)
    ql_path = os.path.join(out_paths['qlfc_path'], IDEPIX_QL_NAME.format(product_name, "fc"))
    plot_pic(product, ql_path, rgb_layers=fc_bands, grid=True, max_val=0.3, perimeter_file=wkt_file)


def create_c2rcc_quicklooks(wkt_file, params, out_paths, product_name):
    print("Creating quicklooks for C2RCC for bands: {}".format(params['C2RCC']['bands']))
    product = ProductIO.readProduct(os.path.join(out_paths['c2rcc_path'], C2RCC_NAME.format(product_name)))
    for band, bandmax in zip(params['C2RCC']['bands'].split(","), params['C2RCC']['bandmaxs'].split(",")):
        if int(bandmax) == 0:
            bandmax = False
        else:
            bandmax = range(0, int(bandmax))
        ql_path = os.path.join(out_paths['c2rcc_band_paths'][band], C2RCC_QL_NAME.format(product_name, band))
        plot_map(product, ql_path, band, basemap="srtm_hillshade", grid=True, perimeter_file=wkt_file, param_range=bandmax)
        print("Plot for band {} finished.".format(band))


def create_poly_quicklooks(wkt_file, params, out_paths, product_name):
    print("Creating quicklooks for POLYMER for bands: {}".format(params['POLY']['bands']))
    product = ProductIO.readProduct(os.path.join(out_paths['poly_path'], POLY_NAME.format(product_name)))
    for band, bandmax in zip(params['POLY']['bands'].split(","), params['POLY']['bandmaxs'].split(",")):
        if int(bandmax) == 0:
            bandmax = False
        else:
            bandmax = range(0, int(bandmax))
        ql_path = os.path.join(out_paths['poly_band_paths'][band], POLY_QL_NAME.format(product_name, band))
        plot_map(product, ql_path, band, basemap='srtm_hillshade', grid=True, perimeter_file=wkt_file, param_range=bandmax)
        print("Plot for band {} finished.".format(band))


def create_mph_quicklooks(wkt_file, params, out_paths, product_name):
    print("Creating quicklooks for MPH for bands: {}".format(params['MPH']['bands']))
    product = ProductIO.readProduct(os.path.join(out_paths['mph_path'], MPH_NAME.format(product_name)))
    for band, bandmax in zip(params['MPH']['bands'].split(","), params['MPH']['bandmaxs'].split(",")):
        if int(bandmax) == 0:
            bandmax = False
        else:
            bandmax = range(0, int(bandmax))
        ql_path = os.path.join(out_paths['mph_band_paths'][band], MPH_QL_NAME.format(product_name, band))
        plot_map(product, ql_path, band, basemap="srtm_hillshade", grid=True, perimeter_file=wkt_file, param_range=bandmax)
        print("Plot for band {} finished.".format(band))


def create_reproject_parameters_from_wkt(wkt_file, resolution):
    perimeter = WKTReader().read(auxil.load_wkt(wkt_file))
    lats = [coordinate.y for coordinate in perimeter.getCoordinates()]
    lons = [coordinate.x for coordinate in perimeter.getCoordinates()]
    x_dist = haversine((min(lats), min(lons)), (min(lats), max(lons)))
    y_dist = haversine((min(lats), min(lons)), (max(lats), min(lons)))
    x_pix = int(round(x_dist / (int(resolution) / 1000)))
    y_pix = int(round(y_dist / (int(resolution) / 1000)))
    x_pixsize = (max(lons) - min(lons)) / x_pix
    y_pixsize = (max(lats) - min(lats)) / y_pix

    return {'easting': str(min(lons)), 'northing': str(max(lats)), 'pixelSizeX': str(x_pixsize),
            'pixelSizeY': str(y_pixsize), 'width': str(x_pix), 'height': str(y_pix)}
