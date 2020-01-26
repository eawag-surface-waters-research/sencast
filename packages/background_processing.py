import numpy
import os
import subprocess
import sys

from haversine import haversine

from packages.MyProductc import MyProduct
from packages.product_fun import get_corner_pixels_ROI
from packages import path_config
from snappy import jpy, GPF, WKTReader, ProductIO

from packages.ql_mapping import plot_pic, plot_map
from packages.product_fun import get_UL_LR_geo_ROI
from packages.ancillary import Ancillary_NASA
from packages.auxil import gpt_xml

sys.path.append(path_config.polymer_path)

from polymer.main import run_atm_corr
from polymer.main import Level1, Level2
from polymer.level1_msi import Level1_MSI
from polymer.gsw import GSW
from polymer.level2 import default_datasets



def background_processing(myproduct, params, dir_dict):
    FileReader = jpy.get_type('java.io.FileReader')
    GPF.getDefaultInstance().getOperatorSpiRegistry().loadOperatorSpis()
    oriproduct = MyProduct(myproduct.products, myproduct.params, myproduct.path)

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
    for product in oriproduct.products:
        l1name = product.getName()
        l1rname = 'reproj_' + l1name + '.nc'
        l1pname = 'L1P_' + l1rname
        l1mname = 'merged_' + l1pname
        l1_path = dir_dict['L1 dir'] + '/' + l1name.split('.')[0] + '/' + l1name
        l1r_path = './' + l1rname
        l1p_path = dir_dict['L1P dir'] + '/' + l1pname
        l1m_path = './' + l1mname
        run_process = [False, False, False, False]
        if os.path.isfile(l1p_path):
            print('\nSkipping Idepix: ' + l1pname + ' already exists.')
        else:
            run_process[0] = True
        if '1' in params['pcombo']:
            l2c2rname = 'L2C2R_' + l1pname
            l2c2r_path = dir_dict['c2rcc dir'] + '/' + l2c2rname
            if os.path.isfile(l2c2r_path):
                print('\nSkipping C2RCC: ' + l2c2rname + ' already exists.')
            else:
                run_process[1] = True
        if '2' in params['pcombo']:
            polytempname = 'L2POLY_' + l1name + '.nc'
            polyname = 'L2POLY_' + l1pname
            polytemp_path = path_config.cwd + '/' + polytempname
            poly_path = dir_dict['polymer dir'] + '/' + polyname
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

        # ---------------- Reprojecting ------------------#
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
            gpt_xml(operator=op_str, product_parameters=parameters, xml_path=xml_path)
            print()
            print('Reprojecting L1 product...')
            subprocess.call([path_config.gpt_path, xml_path, '-SsourceProduct=' + l1_path, '-PtargetProduct=' + l1r_path])
            os.remove('./reproj_temp.xml')

    # ---------------------- Idepix ----------------------#
        if run_process[0]:
            if params['sensor'].lower() == 'olci':
                op_str = 'Idepix.Sentinel3.Olci'
            elif params['sensor'].lower() == 'msi':
                op_str = 'Idepix.Sentinel2'
            xml_path = './idepix_temp.xml'
            parameters = MyProduct.HashMap()
            gpt_xml(operator=op_str, product_parameters=parameters, xml_path=xml_path)
            wktfn = os.path.basename(params['wkt file']).split('.')[0]
            print()
            print('Writing L1P_{} product to disk...'.format(wktfn))
            subprocess.call([path_config.gpt_path, xml_path, '-SsourceProduct=' + l1r_path, '-PtargetProduct=' + l1p_path])
            os.remove('./idepix_temp.xml')

    # --------------------- Quicklooks --------------------#
            print()
            print('Saving quicklooks to disk...')
            if params['sensor'].upper() == 'MSI':
                rgb_bands = params['True color']
                fc_bands = params['False color']
            if params['sensor'].upper() == 'OLCI':
                rgb_bands = [bn.replace('radiance', 'reflectance') for bn in params['True color']]
                fc_bands = [bn.replace('radiance', 'reflectance') for bn in params['False color']]
            l1p_product = ProductIO.readProduct(l1p_path)
            pname = l1p_product.getName()
            tcname = os.path.join(dir_dict['qlrgb dir'], pname.split('.')[0] + '_rgb.png')
            fcname = os.path.join(dir_dict['qlfc dir'],pname.split('.')[0] + '_falsecolor.png')
            plot_pic(l1p_product, tcname, rgb_layers=rgb_bands, grid=True, max_val=0.16,
                     perimeter_file=params['wkt file'])
            plot_pic(l1p_product, fcname, rgb_layers=fc_bands, grid=True, max_val=0.3,
                     perimeter_file=params['wkt file'])

    # -------------------- C2RCC --------------------------#
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
                    bname = os.path.join(dir_dict[bn], pname.split('.')[0] + '_' + bn + '.png')
                    plot_map(l2c2r_product, bname, bn, basemap='srtm_hillshade', grid=True,
                             perimeter_file=params['wkt file'], param_range=param_range)
                    print('Plot for band {} finished.\n'.format(bn))
        if os.path.isfile(l1r_path):
            os.remove(l1r_path)
        if os.path.isfile(l1m_path):
            os.remove(l1m_path)

        # ------------------ Polymer ------------------#
        if run_process[2]:
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
                                 datasets=default_datasets + ['sza']))



                    masterProduct = None
                    resultpoly = ''
                    pname = product.getName().split('.')[0]
                    if masterProduct is not None:
                        newname = 'L2POLY_reproj_L1P_' + pname
                        coll_parameters = MyProduct.HashMap()
                        sourceProducts = MyProduct.HashMap()
                        sourceProducts.put('master', masterProduct)
                        sourceProducts.put('slave', resultpoly)
                        coll_parameters.put('renameMasterComponents', False)
                        coll_parameters.put('renameSlaveComponents', False)
                        mergedProduct = GPF.createProduct('Collocate', coll_parameters, sourceProducts)

                        subs_parameters = MyProduct.HashMap()
                        subs_parameters.put('bandNames', 'OAA,OZA,SAA,SZA,Rw400,Rw412,Rw443,Rw490,Rw510,' +
                                            'Rw560,Rw620,Rw665,Rw681,Rw709,Rw754,Rw779,Rw865,Rw1020,' +
                                            'Rnir,Rgli,logchl,bbs,bitmask,quality_flags,pixel_classif_flags')
                        subs_parameters.put('copyMetadata', True)
                        bandsetProduct = GPF.createProduct('Subset', subs_parameters, mergedProduct)
                    else:
                        newname = 'L2POLY_' + pname

                    bandsetProduct.setName(newname)


                    os.chdir(cwd)






    deriproduct = oriproduct
    pmode = 3
    #------------------ MPH ------------------------#
    if '3' in params['pcombo'] and params['sensor'].upper() == 'OLCI':
        if os.path.isfile(os.path.join(dir_dict['mph dir'], 'L2MPH_' + deriproduct.products[0].getName().split('.')[0] + '.nc'))\
                or os.path.isfile(os.path.join(dir_dict['mph dir'], 'L2MPH_reproj_' + deriproduct.products[0].getName().split('.')[0] + '.nc')):
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