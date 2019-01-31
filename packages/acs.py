#! /usr/bin/env python
# -*- coding: utf-8 -*-

import ipywidgets as widgets

from IPython.display import display
from packages.MyProductc import MyProduct
from packages.display_fun import display_band_with_flag, display_rgb_with_flag
from snappy import ProductUtils, jpy, GPF
import re
from datetime import datetime
import os
from packages.eawag_mapping import plot_pic, plot_map
RES = 60 # Resample resolution for MSI


def get_ingestion_date(productname):
    temp = re.findall('_(\d{8})', productname)
    return temp[0]


def interactive_processing(myproduct, params, dir_dict):
    b1 = widgets.Button(description='Polymer')
    b2 = widgets.Button(description='C2RCC')
    uibutton = widgets.HBox([b1, b2])
    
    oriproduct = MyProduct(myproduct.products, myproduct.params, myproduct.path)
    # First Resample product if sensor is MSI
    if params['sensor'].upper() == 'MSI':
        oriproduct.resample(res=RES)
    
    # First subset the original product
    regions = oriproduct.get_regions()
    print('starting subsets...')
    oriproduct.subset(regions=regions)
    print('starting Idepix...')
    # Apply idepix
    oriproduct.idepix()
    print('Done. Displaying...')
    # Display rgb and false color with flags
    widget_display_myproduct_3bands_3flags(oriproduct)
    print('\nYou can now play with the dropdown options')
    print('\nSelect an atmospheric correction processor:')
    display(uibutton)
    
    def button1_clicked(b):
        # Start Polymer processing
        print('\n\033[1mPolymer\033[0m processing (wait until the end of the processing before clicking another button)...')
        c = 0
        dates = []
        for dt, i in oriproduct.product_dict.items():
            dates.append(dt)
        dates = [dt for dt, d in myproduct.product_dict.items() if dt in dates]
        products = [p for p in myproduct.products if any(dt in p.getName() for dt in dates)]
        print('polymer input products')
        print(products)
        polyproduct = MyProduct(products, myproduct.params, myproduct.path)
        # Apply Polymer and get the ROI
        polyproduct.polymer(myproductmask=oriproduct)
        if params['pmode'] == '2':
            print('Writing L2POLY product to disk...')
            polyproduct.write(dir_dict['polymer dir'])
            print('Writing completed.')
        print('Displaying products...')
        # Display product
        widget_display_myproduct_band(polyproduct)
        print('Processing complete.')
        print('\nYou can now play with the dropdown options, or start a new atmospheric correction using the button above.')
    def button2_clicked(b):
        print('\n\033[1mC2RCC\033[0m processing (wait until the end of the processing before clicking another button)...')
        c2rccproduct = MyProduct(oriproduct.products, oriproduct.params, oriproduct.path)
        c2rccproduct.c2rcc()
        if myproduct.params['pmode'] == '2':
            print('Saving products... ')
            polyproduct.write(dir_dict['c2rcc'])
        print('Displaying products...')
        widget_display_myproduct_band(c2rccproduct)
        print('Processing complete.')
        if params['pmode'] == '2':
            print('Writing L2C2R product to disk...')
            c2rccproduct.write(dir_dict['c2rcc dir'])
            print('Writing completed.')
        print('\nYou can now play with the dropdown options, or start a new atmospheric correction using the button above.')
    b1.on_click(button1_clicked)
    b2.on_click(button2_clicked)
    

def widget_display_myproduct_band(myproduct):
    flags = myproduct.get_flags('')
    band_names = myproduct.get_band_names('')
    band_names = [bn for bn in band_names if (('latitude' not in bn) and ('longitude' not in bn) and \
                 ('bitmask' not in bn) and ('quality_flags' not in bn) and \
                 ('pixel_classif_flags' not in bn) and ('c2rcc_flags' not in bn) and \
                 ('rtoa' not in bn))]
    flag_names = [f for f, val in flags[0].items()]
    w = widgets.Dropdown(options=myproduct.date_str, description='Scene date-time:', 
                         style={'description_width': 'initial'}, disabled=False)
    we = widgets.FloatLogSlider(value=0.00001, base=10, min=-5, max=2, step=0.1, 
                                readout_format='.4f')
    wb = widgets.Dropdown(options=band_names, description='Display band:', 
                          style={'description_width': 'initial'}, disabled=False)
    ui = widgets.HBox([w, wb])
    uii = widgets.HBox([widgets.Label('colorbar max stretch value (except 0 which is the 99th percentile):'), we])
    def f(x1, x2, x3):
        print('Displaying {} Band {}...'.format(x1, x2))
        products = myproduct.products
        band = x2
        if 'log' in x2:
            log = True
        else:
            log = False
        display_band_with_flag(products[myproduct.product_dict[x1]], band, vmax=x3, log=log)
    out = widgets.interactive_output(f, {'x1': w, 'x2': wb, 'x3': we})
    display(ui, uii, out)
    

def widget_display_myproduct_3bands_3flags(myproduct):
    flags = myproduct.get_flags('')
    flag_names = [f for f, val in flags[0].items()]
    w = widgets.Dropdown(options=myproduct.date_str, description='Scene date-time:', 
                         style={'description_width': 'initial'}, disabled=False)
    wfc = widgets.Dropdown(options=['True color', 'False color'], description='Display:', 
                         style={'description_width': 'initial'}, disabled=False)
    wf1 = widgets.Dropdown(options=flag_names, description='Flag #1:', 
                          style={'description_width': 'initial'}, disabled=False)
    wf2 = widgets.Dropdown(options=flag_names, description='Flag #2:', 
                          style={'description_width': 'initial'}, disabled=False)
    wf3 = widgets.Dropdown(options=flag_names, description='Flag #3:', 
                          style={'description_width': 'initial'}, disabled=False)
    ui = widgets.HBox([w, wfc])
    uii = widgets.HBox([wf1, wf2])
    uiii = widgets.HBox([wf3])
    def f(x1, x2, x3, x4, x5):
        print('Displaying {}...'.format(x1))
        products = myproduct.products
        flag1 = flags[myproduct.product_dict[x1]][x3]
        flag2 = flags[myproduct.product_dict[x1]][x4]
        flag3 = flags[myproduct.product_dict[x1]][x5]
        display_rgb_with_flag(products[myproduct.product_dict[x1]], myproduct.params[x2], flag1=flag1, flag2=flag2, flag3=flag3)
    out = widgets.interactive_output(f, {'x1': w, 'x2': wfc, 'x3': wf1, 'x4': wf2, 'x5': wf3})
    display(ui, uii, uiii, out)
    
    
def background_processing(myproduct, params, dir_dict, save_out): 
    HashMap = jpy.get_type('java.util.HashMap')
    GPF.getDefaultInstance().getOperatorSpiRegistry().loadOperatorSpis()

    oriproduct = MyProduct(myproduct.products, myproduct.params, myproduct.path) 
    #------------------ S3 Quicklooks ------------------#
    # If the sensor is OLCI, the RGB and false color quicklooks must be done on the original, reprojected products
    if params['sensor'].upper() == 'OLCI':
        print('\nEntering quicklooks processing for S3 OLCI\n')
        # Change radiance band names 
        rgb_bands = [bn.replace('radiance', 'reflectance') for bn in params['True color']]
        fc_bands = [bn.replace('radiance', 'reflectance') for bn in params['False color']]
        # Initialise a quicklooks product
        qlproduct = MyProduct(myproduct.products, myproduct.params, myproduct.path) 
        products = []
        # Radiance to Reflectance 
        for product in qlproduct.products:
            # Convert Radiance to reflectance
            parameters = HashMap()
            parameters.put("sensor", "OLCI")
            parameters.put("conversionMode", "RAD_TO_REFL")
            parameters.put("copyNonSpectralBands", "false")
            reflProduct = GPF.createProduct("Rad2Refl", parameters, product)
            products.append(reflProduct)
        qlproduct.products = products
        qlproduct.update() 
        
        # Reproject (UTM)
        products = []
        for product in qlproduct.products:
            parameters = HashMap()
            parameters.put('crs', 'EPSG:32662')
            reprProduct = GPF.createProduct("Reproject", parameters, product)
            products.append(reprProduct)
        qlproduct.products = products
        qlproduct.update()
        # Subset
        qlproduct.subset()
        if not qlproduct.products:
            return
        # Display
        for product in qlproduct.products:
            pname = product.getName()
#             ingestday = get_ingestion_date(pname)
#             ingestday = datetime.strptime(ingestday, '%Y%m%d').strftime('%Y-%m-%d')
            tcname = os.path.join(dir_dict['qlrgb dir'], pname.split('.')[0] + '_rgb.png')
            fcname = os.path.join(dir_dict['qlfc dir'],pname.split('.')[0] + '_falsecolor.png')
            plot_pic(product, tcname, rgb_layers=rgb_bands, grid=True, max_val=0.25, 
                     perimeter_file=params['wkt file'])
            plot_pic(product, fcname, rgb_layers=fc_bands, grid=True, max_val=0.5,
                     perimeter_file=params['wkt file'])
        qlproduct.close()
        print('Done, resuming processing\n')
    #------------------ Start processing ------------------#        
    # First Resample product if sensor is MSI
    if params['sensor'].upper() == 'MSI':
        oriproduct.resample(res=RES)
    # First subset the original product
    regions = oriproduct.get_regions()
    polyproduct = MyProduct(myproduct.products, myproduct.params, myproduct.path)
    # myproduct = []
    #------------------ Subset ------------------#
    print('starting subsets...')
    oriproduct.subset(regions=regions)
    if not oriproduct.products:
        return
    #------------------ IdePix -----------------------#
    print('\nstarting Idepix...')
    oriproduct.idepix()
    print('Done. ')
    #---------------- Save Idepix --------------------#
    if save_out:
        wktfn = os.path.basename(params['wkt file']).split('.')[0]
        print('\nWriting L1P_{} product to disk...'.format(wktfn))
        oriproduct.write(dir_dict['L1P dir'])
        print('Writing completed.')
    #-------------------------------------------------#
#     print('Getting flags.')
#     flags = oriproduct.get_flags(match='pixel_classif_flags.IDEPIX_CLOUD')
#     print('Done. ')
    
#     c = 0
    #------------------ S2 Quicklooks ------------------#
    if params['sensor'].upper() == 'MSI':
        print('Quicklooks for S2 MSI\n')
        for product in oriproduct.products:
    #         flag1 = flags[c]['pixel_classif_flags.IDEPIX_CLOUD']
    #         c += 1
            pname = product.getName()
            ingestday = get_ingestion_date(pname)
            ingestday = datetime.strptime(ingestday, '%Y%m%d').strftime('%Y-%m-%d')
            tcname = os.path.join(dir_dict['qlrgb dir'], pname.split('.')[0] + '_rgb.png')
            fcname = os.path.join(dir_dict['qlfc dir'], pname.split('.')[0] + '_falsecolor.png')
            plot_pic(product, tcname, rgb_layers=params['True color'], grid=True, max_val=0.14, 
                    perimeter_file=params['wkt file'])
            plot_pic(product, fcname, rgb_layers=params['False color'], grid=True, max_val=0.3, 
                    perimeter_file=params['wkt file'])
        print('Done.')
    #------------------ C2RCC ------------------------#
    if '1' in params['pcombo']:
        print('\nC2RCC...')
        c2rccproduct = MyProduct(oriproduct.products, oriproduct.params, oriproduct.path)
        c2rccproduct.c2rcc()
        for product in c2rccproduct.products:
            pname = product.getName()
#             ingestday = get_ingestion_date(pname)
#             ingestday = datetime.strptime(ingestday, '%Y%m%d').strftime('%Y-%m-%d')
            print('\nCreating quicklooks for bands: {}\n'.format(params['c2rcc bands']))
            # Check if parameter range is provided
            params_range = params['c2rcc max']
            c = 0
            for bn in params['c2rcc bands']:
                if params_range[c] == 0:
                    param_range = False
                else:
                    param_range = [0, params_range[c]]
                c += 1
                # plot
                bname = os.path.join(dir_dict[bn], pname.split('.')[0] + '_' + bn + '.png')
                plot_map(product, bname, bn, basemap='srtm_hillshade', grid=True, 
                         perimeter_file=params['wkt file'], param_range=param_range)
                print('Plot for band {} finished.\n'.format(bn))
#             product.closeIO()
        if save_out:
            print('\nWriting L2C2R product to disk...')
            c2rccproduct.write(dir_dict['c2rcc dir'])
            print('Writing completed.')
        c2rccproduct.close()
    #------------------ MPH ------------------------#
    if '3' in params['pcombo'] and params['sensor'].upper() == 'OLCI':
        print('\nMPH...')
        mphproduct = MyProduct(oriproduct.products, oriproduct.params, oriproduct.path)
        mphproduct.mph()
        for product in mphproduct.products:
            pname = product.getName()
#             ingestday = get_ingestion_date(pname)
#             ingestday = datetime.strptime(ingestday, '%Y%m%d').strftime('%Y-%m-%d')
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
#             product.closeIO()
        if save_out:
            print('\nWriting L2MPH product to disk...')
            mphproduct.write(dir_dict['mph dir'])
            print('Writing completed.')
        mphproduct.close()
    #------------------ Polymer ------------------#
    if '2' in params['pcombo']:
        try:
            print('\nPolymer...')
            polyproduct.polymer(myproductmask=oriproduct)
            print('Done.')
            # Create bands image of polymer
            for product in polyproduct.products:
                pname = product.getName()
        #             ingestday = get_ingestion_date(pname)
        #             ingestday = datetime.strptime(ingestday, '%Y%m%d').strftime('%Y-%m-%d')
                print('\nCreating quicklooks for bands: {}\n'.format(params['polymer bands']))
                # Check if parameter range is provided
                params_range = params['polymer max']
                c = 0
                for bn in params['polymer bands']:
                    if params_range[c] == 0:
                        param_range = False
                    else:
                        param_range = [0, params_range[c]]
                    c += 1
                    bname = os.path.join(dir_dict[bn], pname.split('.')[0] + '_' + bn + '.png')
                    plot_map(product, bname, bn, basemap='srtm_hillshade', grid=True, 
                             perimeter_file=params['wkt file'], param_range=param_range)
                    print('Plot for band {} finished.\n'.format(bn))
        #             product.closeIO()
            # Write product
            if save_out:
                print('\nWriting L2POLY product to disk...')
                polyproduct.write(dir_dict['polymer dir'])
                print('Writing completed.')
            polyproduct.close()
        except OSError:
            print('\nPolymer processing failed because of "mv" command!\n')
    oriproduct.close()
    
