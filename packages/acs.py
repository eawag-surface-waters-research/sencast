import copy
import os

from packages.MyProductc import MyProduct
from snappy import jpy, GPF

from packages.eawag_mapping import plot_pic, plot_map


def background_processing(myproduct, params, dir_dict, pmode):
    HashMap = jpy.get_type('java.util.HashMap')
    GPF.getDefaultInstance().getOperatorSpiRegistry().loadOperatorSpis()
    oriproduct = MyProduct(myproduct.products, myproduct.params, myproduct.path)
    deriproduct = MyProduct(myproduct.products, myproduct.params, myproduct.path)

    #------------------ Resampling ------------------#
    res = params['resolution']
    if res not in ['', '1000']:
        products = []
        for product in deriproduct.products:
            product.resample(res=int(res))
            products.append(product)
        deriproduct.products = products
        deriproduct.update()

    #---------------- Reprojecting ------------------#
    # Somehow the subset of S2 data fails to process with Idepix when doing the reprojection
    # see history of 14 Jan 2020, 19:30
    if params['sensor'].upper() == 'OLCI':
        products = []
        for product in oriproduct.products:
            parameters = HashMap()
            parameters.put('crs', 'EPSG:32662')
            reprProduct = GPF.createProduct('Reproject', parameters, product)
            products.append(reprProduct)
        deriproduct.products = products
        deriproduct.update()

    #------------------ Subsetting ------------------#
    regions = deriproduct.get_regions()
    UL = [0, 0]
    UL[1] = regions[0].split(',')[0]
    UL[0] = regions[0].split(',')[1]
    w = int(regions[0].split(',')[2])
    h = int(regions[0].split(',')[3])
    if params['sensor'].upper() == 'MSI':
        while not (w / (60 / int(res))).is_integer():
            w += 1
        while not (h / (60 / int(res))).is_integer():
            h += 1
        regions = [UL[1] + ',' + UL[0] + ',' + str(w) + ',' + str(h)]
    print('Subsetting region x,y,w,h=' + regions[0])
    deriproduct.subset(regions=regions)

    if not deriproduct.products:
        return

    #------------------- Quicklooks -------------------#
    # The RGB and false color quicklooks must be done on the original, reprojected products
    print('Creating quicklooks')
    reflproduct = copy.copy(deriproduct)

    # Convert Radiance to reflectance
    if params['sensor'].upper() == 'OLCI':
        rgb_bands = [bn.replace('radiance', 'reflectance') for bn in params['True color']]
        fc_bands = [bn.replace('radiance', 'reflectance') for bn in params['False color']]
        products = []
        for product in reflproduct.products:
            parameters = HashMap()
            parameters.put('sensor', 'OLCI')
            parameters.put('conversionMode', 'RAD_TO_REFL')
            parameters.put('copyNonSpectralBands', 'false')
            rad2refl = GPF.createProduct('Rad2Refl', parameters, product)
            products.append(rad2refl)
        reflproduct.products = products
        reflproduct.update()

    elif params['sensor'].upper() == 'MSI':
        rgb_bands = params['True color']
        fc_bands = params['False color']

    # Write pngs
    for product in reflproduct.products:
        pname = product.getName()
        tcname = os.path.join(dir_dict['qlrgb dir'], pname.split('.')[0] + '_rgb.png')
        fcname = os.path.join(dir_dict['qlfc dir'],pname.split('.')[0] + '_falsecolor.png')
        plot_pic(product, tcname, rgb_layers=rgb_bands, grid=True, max_val=0.16,
                 perimeter_file=params['wkt file'])
        plot_pic(product, fcname, rgb_layers=fc_bands, grid=True, max_val=0.3,
                 perimeter_file=params['wkt file'])
    print('Quicklooks completed.')
    print('')

    #------------------ IdePix -----------------------#
    print('Starting Idepix')
    if pmode in ['2', '3']:
        if not os.path.isfile(os.path.join(dir_dict['L1P dir'], deriproduct.products[0].getName() + '.nc')):
            deriproduct.idepix(pmode)
            wktfn = os.path.basename(params['wkt file']).split('.')[0]
            print('Writing L1P_{} product to disk...'.format(wktfn))
            deriproduct.write(dir_dict['L1P dir'])
            print('Done.')
        else:
            print('L1P_' + deriproduct.products[0].getName() + '.nc' + ' already exists.')
    else:
        deriproduct.idepix(pmode)

    #------------------ C2RCC ------------------------#
    if '1' in params['pcombo']:
        if os.path.isfile(os.path.join(dir_dict['c2rcc dir'], 'L2C2R_' + deriproduct.products[0].getName().split('.')[0] + '.nc')):
            print('\nSkipping C2RCC: L2C2R_' + deriproduct.products[0].getName() + '.nc' + ' already exists.')
        elif os.path.isfile(os.path.join(dir_dict['c2rcc dir'], 'L2C2R_reproj_' + deriproduct.products[0].getName().split('.')[0] + '.nc')):
            print('\nSkipping C2RCC: L2C2R_reproj_' + deriproduct.products[0].getName() + '.nc' + ' already exists.')
        else:
            print('\nProcessing with the C2RCC algorithm...')
            c2rccproduct = MyProduct(deriproduct.products, deriproduct.params, deriproduct.path)
            if pmode in ['1', '2']:
                c2rccproduct.c2rcc(pmode)
                if pmode == 2:
                    print('Writing C2RCC L2 to disk with snappy...')
                    c2rccproduct.write(dir_dict['c2rcc dir'])
                    print('Done.')
            elif pmode == '3':
                print('Writing C2RCC L2 to disk with gpt...')
                c2rccproduct.c2rcc(pmode, read_dir = dir_dict['L1P dir'], write_dir = dir_dict['c2rcc dir'])
                print('Done.')

            for product in c2rccproduct.products:
                pname = product.getName()
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
                    bname = os.path.join(dir_dict[bn], pname.split('.')[0] + '_' + bn + '.png')
                    plot_map(product, bname, bn, basemap='srtm_hillshade', grid=True,
                             perimeter_file=params['wkt file'], param_range=param_range)
                    print('Plot for band {} finished.\n'.format(bn))
            c2rccproduct.close()

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

    #------------------ Polymer ------------------#
    if '2' in params['pcombo']:
        if os.path.isfile(os.path.join(dir_dict['polymer dir'], 'L2POLY_L1P_' + myproduct.products[0].getName().split('.')[0] + '.nc'))\
                or os.path.isfile(os.path.join(dir_dict['polymer dir'], 'projected_L2POLY_L1P_' + myproduct.products[0].getName().split('.')[0] + '.nc')):
            print('Skipping Polymer: L2POLY_L1P_' + oriproduct.products[0].getName() + '.nc' + ' already exists.')
        else:
            try:
                print('\nPolymer...')
                polyproduct = MyProduct(myproduct.products, myproduct.params, myproduct.path)
                polyproduct.polymer(masterProduct=deriproduct.products[0], params=params)
                print('Done.')
                # Create bands image of polymer
                for product in polyproduct.products:
                    pname = product.getName()
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

                # Write product
                if pmode in ['2', '3']:
                    print('\nWriting L2POLY product to disk...')
                    polyproduct.write(dir_dict['polymer dir'])
                    print('Writing completed.')
                polyproduct.close()

            except ValueError:
                print('\nPolymer processing failed because of ValueError!\n')
            except OSError:
                print('\nPolymer processing failed because of "mv" command!\n')

    oriproduct.close()
    deriproduct.close()

