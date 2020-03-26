#! /usr/bin/env python
# -*- coding: utf-8 -*-

import re
import os

import numpy as np

from snappy import jpy, GPF, ProductIO, ProductUtils
from datetime import datetime


class MyProduct(object):
    """This class is used to process a snappy Product. It contains a list of product that should all be the same
    kind (OLCI or MSI)."""
    
    HashMap = jpy.get_type('java.util.HashMap')
    GPF.getDefaultInstance().getOperatorSpiRegistry().loadOperatorSpis()
    BandDescriptor = jpy.get_type('org.esa.snap.core.gpf.common.BandMathsOp$BandDescriptor')

    def __init__(self, productslist, params, productspath):
        self.date = []
        self.date_str = []
        self.products = productslist
        self.path = productspath
        self.product_dict = {}  # If you have a date, gives you the idx for the class lists
        self.params = params
        self.band_names = []
        self.band_names_str = ''
        self.state = []
        self.valid_pixels = []  # percentage of valid pixels
        self.masks = []
        self.update()

    def __repr__(self):
        dispstr = 'Product List:'
        c = 0
        for product in self.products:
            dispstr += '\n'+product.getName()
            if self.valid_pixels:
                dispstr += '\n{} % of valid pixels'.format(self.valid_pixels[c])
            c += 1
        return dispstr

    def update_date(self):
        """ Update field date with a list of datetime for each product"""
        dtlist = []
        dtstrlist = []
        for product in self.products:
            name = product.getName()
            name = re.search(r'\d{8}T\d{6}', name).group(0)
            dt = datetime.strptime(name, '%Y%m%dT%H%M%S')
            dtlist.append(dt)
            dtstrlist.append(dt.strftime('%Y%m%dT%H%M'))
        self.date = dtlist
        self.date_str = dtstrlist

    def update_dict(self):
        """ Update product dictionary.
        - the key is the date of the product (YYYYMMDD)
        - the value is the corresponding product"""

        dicttemp = {}
        # If self.date and self.products have different size update the dates
        if len(self.products) != len(self.date):
            self.update_date()

        for c in range(len(self.products)):
            dicttemp[self.date_str[c]] = c

        self.product_dict = dicttemp

    def update_band_names(self):
        """ Update product band names """
        bnames = []
        for bn in self.products[0].getBandNames():
            bnames.append(bn)
        bnstr = bnames[0]
        for bn in bnames[1:]:
            bnstr += ','+bn
        self.band_names = bnames
        self.band_names_str = bnstr

    def update(self):
        self.update_date()
        self.update_dict()
        self.update_band_names()

    def get_band_names(self, pattern=''):
        return [bn for bn in self.products[0].getBandNames() if pattern in bn]

    def resample(self, res=20):
        parameters = MyProduct.HashMap()
        parameters.put('targetResolution', res)
        results = []
        for product in self.products:
            result = GPF.createProduct('Resample', parameters, product)
            pname = result.getName()
            result.setName(pname+'_'+str(res)+'m')
            results.append(result)
        self.products = results
        self.state.append('Resample')
        self.update()

    def subset(self, wkt, regions=None):
        # Update MyProduct
        self.update()
        subsets = []
        c = 0
        for product in self.products:
            h = product.getSceneRasterHeight()
            w = product.getSceneRasterWidth()
            print('    Subsetting {}...'.format(product.getName()))
            print('    Size before subset: {}, {}'.format(h, w))
            # Initialisation
            parameters = MyProduct.HashMap()
            if regions is None:
                parameters.put('geoRegion', wkt)
            else:
                parameters.put('region', regions[c])
            
            parameters.put('sourceBands', self.band_names_str)
            parameters.put('copyMetadata', 'True')
            try:
                result = GPF.createProduct('Subset', parameters, product)
            except RuntimeError:
                print('    Failed. ROI probably outside the frame, or bad wkt.')
                # result = product
            else:
                # Append subset if not empty
                if 'Subset' in result.getName():
                    h = result.getSceneRasterHeight()
                    w = result.getSceneRasterWidth()
                    print('    Size after subset: {}, {}'.format(h, w))
                    subsets.append(result)
                    print('    Subsetting completed\n')
                else:
                    print('    ROI outside the frame')
            c += 1
        if not subsets:
            print('\n    No products passed the subsetting... exiting\n')
            self.products = []
            return
            
        self.products = subsets
        self.state.append('Subset')
        self.update()

    def copy_masks(self, sourcemyproduct):
        count = 0
        products = []
        for product in self.products:
            sourceproduct = sourcemyproduct.products[count]
            ProductUtils.copy_masks(sourceproduct, product)
            ProductUtils.copyOverlayMasks(sourceproduct, product)
            ProductUtils.copyFlagCodings(sourceproduct, product)
            ProductUtils.copyFlagBands(sourceproduct, product, True)
            products.append(product)
            count += 1
        self.products = products
        self.state.append('Mask')
        self.update()

    def get_flags(self, pattern=None, match=None):
        """ This function returns a flag list with one field per product. each element of the list is a dictionnary 
        with the key corresponding to the flag name and the value is a numpy array (uint32) with the corresponding
        flag"""
        if pattern is None:
            pattern = []
        if match is None:
            match = []
        flags = []
        for product in self.products:
            h = product.getSceneRasterHeight()
            w = product.getSceneRasterWidth()
            flagNames = product.getAllFlagNames()
            if pattern and not match:
                flagNames = [fn for fn in flagNames if pattern in fn]
            elif match:
                flagNames = [fn for fn in flagNames if fn == match]
            flag = {'no flag': np.zeros((h, w), dtype=np.uint32)}
            for i in range(len(flagNames)):
                params = MyProduct.HashMap()
                targetBand = MyProduct.BandDescriptor()
                targetBand.name = flagNames[i]
                targetBand.type = 'uint32'
                targetBand.expression = flagNames[i]
                targetBands = jpy.array('org.esa.snap.core.gpf.common.BandMathsOp$BandDescriptor', 1)
                targetBands[0] = targetBand
                params.put('targetBands', targetBands)
                
                flagProduct = GPF.createProduct('BandMaths', params, product)
                band = flagProduct.getBand(targetBand.name)
                bandnp = np.zeros(h*w, dtype=np.uint32)
                band.readPixels(0, 0, w, h, bandnp)
                bandnp.shape = h, w
                flag[targetBand.name] = bandnp
                flagProduct.closeIO()
            flags.append(flag)
        return flags

    def mph(self):
        if self.params['General']['sensor'] == 'OLCI':
            parameters = MyProduct.HashMap()
            parameters.put('validPixelExpression', self.params['MPH']['validexpression'])
            parameters.put('exportMph', True)
            parametersrepr = MyProduct.HashMap()
            parametersrepr.put('crs', 'EPSG:32662')
            results = []
            for product in self.products:
                print('apply MPH...')
                resultmph = GPF.createProduct('MphChl', parameters, product)
                print('Done.')
                pname = product.getName().split('.')[0]
                # Reproject
                print('Reprojecting MPH output...')
                reprProduct = GPF.createProduct("Reproject", parametersrepr, resultmph)
                newname = 'L2MPH_reproj_'+pname
                reprProduct.setName(newname)
                results.append(reprProduct)
                print('Done.')
            self.products = results
            self.state.append('MPH')
            self.update()

    def write(self, writedir):
        writer = ProductIO.getProductWriter('NetCDF-BEAM')  # -CF writer does not add wavelength attributes
        for product in self.products:
            # If file already exist remove it 
            fname = os.path.join(writedir, product.getName()+'.nc')
            if os.path.isfile(fname):
                os.remove(fname)
            product.setProductWriter(writer)
            product.writeHeader(fname)
            ProductIO.writeProduct(product, fname, 'NetCDF-BEAM')  # -CF writer does not add wavelength attributes

    def close(self):
        for product in self.products:
            product.closeIO()
