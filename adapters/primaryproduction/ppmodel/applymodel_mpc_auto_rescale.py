# -*- coding: utf-8 -*-
"""
Created on Fri Oct 21 14:13:56 2016
"""
import re
import glob
import os
import math
import datetime, time
from netCDF4 import Dataset
import warnings
warnings.simplefilter("error", RuntimeWarning)

# 3rd party imports
from mpl_toolkits.basemap import Basemap
import numpy as np
from matplotlib import pyplot as plt
import matplotlib as mpl
from scipy.integrate import trapz
from matplotlib.patches import Polygon

# Primary productivity model
import ppmodel

#!-------------------------------------------------

# Haversine formula for distance
def distance(lon1,lat1, lon2, lat2):
    radlon1 = np.radians(lon1)
    radlat1 = np.radians(lat1)
    
    radlon2 = np.radians(lon2)
    radlat2 = np.radians(lat2)
    
    d_lon = radlon2-radlon1
    d_lat = radlat2-radlat1

    a = np.sin(d_lat/2)**2 \
        + np.cos(radlat1)*np.cos(radlat2)*np.sin(d_lon/2)**2
    return 6371*2*np.arcsin(np.sqrt(a))

    
def draw_screen_poly(lons, lats, m, color, ax):
     x, y = m( lons, lats )
     xy = zip(x,y)
     poly = Polygon( xy, facecolor=color, edgecolor=color, alpha=1, linewidth=0.5 ) # edgecolor='none' no effect?
     ax.add_patch(poly)

     
def convert_to_pixel_coords(tie_lons, tie_lats, lon, lat):
    pixel_distances = distance(tie_lons[:], tie_lats[:], lon, lat)
    pixel_y = np.where(pixel_distances == pixel_distances.min())[0][0]
    pixel_x = np.where(pixel_distances == pixel_distances.min())[1][0]
    return (pixel_y, pixel_x)
     

def roundup(x):
    return int(math.ceil(x / 10.0)) * 10
    
    
    
#!--------------------------------------------     
# Script parameters
inputdir = r'F:\MERIS Geneva\input'
outputdir = r'F:\MERIS Geneva\output_rescale'
insitu_file = r'F:\MERIS Geneva\in_situ_Geneva_all.csv'

insitu_sample = open(r'F:\MERIS Geneva\output_rescale\insitu_point.txt', 'w')
insitu_Lon = 6.58875
insitu_Lat = 46.45262

sample_text_1 = open(r'F:\MERIS Geneva\output_rescale\West_point.txt', 'w')
sample_text_2 = open(r'F:\MERIS Geneva\output_rescale\East_point.txt', 'w')
sample_points = [{
                'coords':(6.219509,46.311911),
                'output': sample_text_1
                },{
                'coords': (6.820888,46.421707),
                'output': sample_text_2
                }]

#!----------------------------------------------
# Arguments
# depths where we calculate PP(z)
zvals = np.array([0,1,2,3.5,5,7.5,10,15,20,30])
# finer depth grid of 100 points covering the same range as zvals, to calculate pp_int more accurately
zvals_fine = np.linspace(zvals[0],zvals[-1],100)
# use a value for qpar0 that is dependant on the month of the year.
qpar0_lookup = {
                1:2.5, 
                2:2.5,
                3:4.0,
                4:4.0,
                5:6.5,
                6:6.5,
                7:6.5,
                8:6.5,
                9:4.0,
                10:4.0,
                11:2.5,
                12:2.5
}

# regex to extract date from filename (e.g. match '20020517' from 
# MER_RR__2PNACR20020517_102559_000000452006_00051_01107_0000
fileDatePattern = re.compile(".*(\d{8,8})_\d{6,6}_\d{12,12}_\d{5,5}_\d{5,5}_\d{4,4}.*")

# min and max for the scale bar
ppmin = 0
# pp_cut defines the cut-off point to ignore pixel values (outliers)
pp_cut = 1000

#-MAIN--------------------------------------------        
# make sure outputdir exists
try:
     os.makedirs(outputdir)
except OSError:
     if not os.path.isdir(outputdir):
         raise 
         
insitu = np.loadtxt(insitu_file,comments='#', delimiter=',',
                     converters= { 0: lambda s: time.mktime(datetime.datetime.strptime(s,"%d/%m/%Y").timetuple()),
                                   1: lambda s: float(s or 0),
                                   2: lambda s: float(s or 0),
                                   3: float,
                                   4: float })


l2files=glob.glob(inputdir + os.path.sep + '*.nc')
for filename in l2files:
    print '\nprocessing.. ' + filename
    #datestr is the matched date from the filename
    datestr = fileDatePattern.match(filename).groups()[0]
    # satellite(img) date as as datetime object
    sat_date_dt = datetime.datetime.strptime(datestr, "%Y%m%d")
    # date as seconds
    sat_date = time.mktime(datetime.datetime.strptime(datestr,"%Y%m%d").timetuple())
    
    [isDate,isChl,isPP,isLon,isLat]=insitu[np.fabs(insitu[:,0]-sat_date) == \
    np.min(np.fabs(insitu[:,0]-sat_date))][0]
    isDate_dt = datetime.datetime.fromtimestamp(isDate)
    
    l2data = Dataset(filename)
    lons = l2data.variables['lon'][:]
    lats = l2data.variables['lat'][:]
    conc_chl_oc4 = l2data.variables['conc_chl_oc4'][:]
    Kd490 = l2data.variables['Kd_490'][:]
    KdMorel = 0.0864 + 0.884 * Kd490 - 0.00137/Kd490
    l2data.close()

    cornerlons = 0.25*(lons[:-1,:-1] + lons[:-1,1:] + lons[1:,1:] + lons[1:,:-1])
    cornerlats = 0.25*(lats[:-1,:-1] + lats[:-1,1:] + lats[1:,1:] + lats[1:,:-1])
    
    qpar0 = np.zeros_like(conc_chl_oc4)
    # get the value of the qpar0 based on the month of the year
    try:
        qpar_constant = qpar0_lookup[sat_date_dt.month]
    except KeyError:
        # Default value is 6
        qpar_constant = 6
    qpar0 = qpar0 + qpar_constant   
    
    # prepare maps:
    print 'preparing maps'
    thefig = plt.figure(figsize=(8,5))
    theax = thefig.add_axes([0.1,0.075,0.75,0.85])
    colormap = plt.get_cmap(name='jet')
    
    # Geographic coordinates of the lake extent
    in_lake = ((lons > 6.1) & (lons < 6.9) & (lats < 46.55) & (lats > 46.2))
    
    # center on Lake Geneva 46.449903, 6.485912
    themap = Basemap(lon_0=6.53,lat_0=46.37, width=80000,height=80000*3/4, \
                     projection='stere', resolution='h', ax=theax, suppress_ticks=False)

    temp, tickY = themap(6.0*np.ones(4),np.linspace(46.2,46.5,4))
    tickX, temp = themap(np.linspace(6.0,7.0,6), 46.0*np.ones(6))
    theax.xaxis.set_ticks(tickX)
    theax.xaxis.set_ticklabels([u'6.0\N{DEGREE SIGN}E',u'6.2\N{DEGREE SIGN}E',\
                                u'6.4\N{DEGREE SIGN}E',u'6.6\N{DEGREE SIGN}E',\
                                u'6.8\N{DEGREE SIGN}E'])
    theax.yaxis.set_ticks(tickY)
    theax.yaxis.set_ticklabels([u'46.2\N{DEGREE SIGN}N', u'46.3\N{DEGREE SIGN}N',\
                                u'46.4\N{DEGREE SIGN}N', u'46.5\N{DEGREE SIGN}N'])

    themap.drawcoastlines(color='black', linewidth='0.5')
    themap.drawrivers(color='blue')
    themap.drawmapscale(6.3, 46.175, 6.3, 46.18, 10)
    thecmap = plt.get_cmap(name='jet')

    axcb = thefig.add_axes([.875, .1,.025,.80]) 
    
    # An output file is opened ready to write the pixel lat/long and pixel values for the image
    inputfilename = os.path.split(filename)[-1]
    output = open(os.path.join(outputdir, inputfilename[:-3] + '_output.txt'), 'w')
    output.write('Longitude Latitude PPint\n')
    # Calculate the pixel values for the image and write the values to the output file.
    pp_track = []
    ppint_track = []
    for i in range(1,qpar0.shape[0]-1):
        for j in range(1,qpar0.shape[1]-1):
            if ((np.isnan(conc_chl_oc4[i,j])) or not (in_lake[i,j]) \
                or not (qpar0[i,j])):
                continue
            ppint = trapz(ppmodel.PP(zvals_fine, qpar0[i,j], conc_chl_oc4[i,j],\
                                     KdMorel[i,j]), zvals_fine)
            
            pixlons = [cornerlons[i-1,j-1],cornerlons[i-1,j],cornerlons[i,j],\
                       cornerlons[i,j-1]]
            pixlats = [cornerlats[i-1,j-1],cornerlats[i-1,j],cornerlats[i,j],\
                       cornerlats[i,j-1]]
            pp_track.append((pixlons, pixlats, ppint))
            # Test for 'nan' values by casting to int.  Ignore any values that 
            # throw an error, and add the pixel value otherwise to the ppint_track list. 
            try:
                int(ppint)
                ppint_track.append(ppint)
            except ValueError:
                pass
            output.write(str(lons[i,j]))
            output.write(' ')
            output.write(str(lats[i,j]))
            output.write(' ')
            output.write(str(ppint))
            output.write('\n')
    output.close()
    
    # The upper value of the chart scale bar (ppmax) is taken from either the 
    # highest pixel value stored in ppint_track or the insitu value, which ever
    # is higher.
    ppmax = np.percentile(np.array(ppint_track), 98)
    if ppmax > isPP:
        # Round to the nearest 10
        ppmax = roundup(ppmax)
    else:
        if isDate == sat_date:
            ppmax = roundup(isPP)
        else:
            ppmax = roundup(ppmax)
    
    # Set the chart color scale
    cNorm  = mpl.colors.Normalize(vmin=ppmin, vmax= ppmax)
    scalarMap = mpl.cm.ScalarMappable(norm=cNorm, cmap=thecmap )
    colorbar = mpl.colorbar.ColorbarBase(axcb,cmap=thecmap, norm=cNorm)
    colorbar.set_label('$\mathsf{PP}_{\!\mathsf{ar}}\ \ [\mathsf{mg\ C\ m}^{-2} \mathsf{h}^{-1}]$',\
                       labelpad= 20, rotation=270)
    
    # Draw the pixels
    print 'Drawing pixels...'
    for pixel in pp_track:
        if(pixel[2] <= pp_cut):
            draw_screen_poly(pixel[0], pixel[1], themap, scalarMap.to_rgba(pixel[2]), theax)

    # On each day, draw a circle at the coord. of the in situ measurement, and put the measured value there
    if isDate == sat_date:
        print 'matched insitu data'
        themap.tissot(isLon, isLat, # lon, lat
                     0.005, # radius of dot in degrees lon
                      300, # number of points used to draw the dot
                     facecolor=scalarMap.to_rgba(isPP), # color of dot
            ax=theax, edgecolor='black')

    thefig.savefig(os.path.join(outputdir, inputfilename[:-3] + '.png'))
    thefig.clf()
    plt.close(thefig)
    
    # Sample the image at the sample point locations and at any insitu dates
    # and write to the appropriate files.
    print 'Sampling Points'
    for sample_point in sample_points:
        indices = convert_to_pixel_coords(lons, lats, sample_point['coords'][0], sample_point['coords'][1])
        y_coord = indices[0]
        x_coord = indices[1]
        ppint = trapz(ppmodel.PP(zvals_fine, qpar0[y_coord, x_coord], conc_chl_oc4[y_coord, x_coord],\
                                     KdMorel[y_coord, x_coord]), zvals_fine)
        sample_point['output'].write(str(sample_point['coords'][0]))
        sample_point['output'].write(' ')
        sample_point['output'].write(str(sample_point['coords'][1]))
        sample_point['output'].write(' ')
        sample_point['output'].write(str(sat_date_dt))
        sample_point['output'].write(' ')
        sample_point['output'].write(str(ppint))
        sample_point['output'].write('\n')
    
    # Sample insitu points
    insitu_indices = convert_to_pixel_coords(lons, lats, insitu_Lon, insitu_Lat)
    y_coord = insitu_indices[0]
    x_coord = insitu_indices[1]
    ppint = trapz(ppmodel.PP(zvals_fine, qpar0[y_coord, x_coord], conc_chl_oc4[y_coord, x_coord],\
                                     KdMorel[y_coord, x_coord]), zvals_fine)   
    insitu_sample.write(str(insitu_Lon))
    insitu_sample.write(' ')
    insitu_sample.write(str(insitu_Lat))
    insitu_sample.write(' ')
    insitu_sample.write(str(sat_date_dt))
    insitu_sample.write(' ')
    insitu_sample.write(str(ppint))
    insitu_sample.write(' ')
    if isDate == sat_date:
        insitu_sample.write('MATCH')
        insitu_sample.write(' ')
        insitu_sample.write(str(isDate_dt))
        insitu_sample.write(' ')
        insitu_sample.write(str(isPP))
    insitu_sample.write('\n')
        
for sample_point in sample_points:
    sample_point['output'].close()
        
insitu_sample.close()      
print '\ndone'
