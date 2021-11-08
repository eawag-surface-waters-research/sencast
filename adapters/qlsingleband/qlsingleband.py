#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""The QLSingleBand adapter creates single-band quick looks output as .png files.

Individual bands are plotted geospatially using matplotlib and exported to .png
"""

import math
import os
import re

import numpy as np
import cartopy.crs as ccrs
import cartopy.io.srtm as srtm
import cartopy.io.img_tiles as maps
import matplotlib as mpl
import matplotlib.cm as cm
import matplotlib.colors as colors
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

import adapters.qlsingleband.colour_scales as colscales

from cartopy.io import PostprocessedRasterSource, LocatedImage
from haversine import haversine
from snappy import GPF, HashMap, jpy, Mask, PixelPos, ProductUtils, ProductIO

from utils.product_fun import get_lons_lats

plt.switch_backend('agg')
mpl.pyplot.switch_backend('agg')
canvas_area = []

# key of the params section for this adapter
PARAMS_SECTION = "QLSINGLEBAND"


def apply(env, params, l2product_files, date):
    """Apply QLSingleBand adapter.

    Parameters
    -------------

    env
        Dictionary of environment parameters, loaded from input file
    params
        Dictionary of parameters, loaded from input file
    l2product_files
        Dictionary of Level 2 product files created by processors
    date
        Run date
    """
    wkt = params['General']['wkt']

    for key in params[PARAMS_SECTION].keys():
        processor = key.upper()
        if processor in l2product_files.keys():
            log(env["General"]["log"], "Creating quicklooks for {}".format(processor))
            bands = list(filter(None, params[PARAMS_SECTION][key].split(",")))[::3]
            bandmins = list(filter(None, params[PARAMS_SECTION][key].split(",")))[1::3]
            bandmaxs = list(filter(None, params[PARAMS_SECTION][key].split(",")))[2::3]
            product_name = os.path.splitext(os.path.basename(l2product_files[processor]))[0]
            for band, bandmin, bandmax in zip(bands, bandmins, bandmaxs):
                if band == 'secchidepth':
                    processor = 'SECCHIDEPTH'
                elif band == 'forelule':
                    processor = 'FORELULE'
                ql_path = os.path.dirname(l2product_files[processor]) + "-" + band
                ql_file = os.path.join(ql_path, "{}-{}.pdf".format(product_name, band))
                if os.path.exists(ql_file):
                    if "synchronise" in params["General"].keys() and params['General']['synchronise'] == "false":
                        log(env["General"]["log"], "Removing file: ${}".format(ql_file))
                        os.remove(ql_file)
                        param_range = None if float(bandmin) == 0 == float(bandmax) else [float(bandmin), float(bandmax)]
                        plot_map(env, l2product_files[processor], ql_file, band, wkt, "srtm_hillshade",
                                 param_range=param_range)
                    else:
                        log(env["General"]["log"], "Skipping QLSINGLEBAND. Target already exists: {}".format(os.path.basename(ql_file)))
                else:
                    param_range = None if float(bandmin) == 0 == float(bandmax) else [float(bandmin), float(bandmax)]
                    os.makedirs(os.path.dirname(ql_file), exist_ok=True)
                    plot_map(env, l2product_files[processor], ql_file, band, wkt, "srtm_hillshade",
                             param_range=param_range)


def plot_map(env, input_file, output_file, layer_str, wkt=None, basemap='srtm_elevation', crop_ext=None,
             param_range=None, cloud_layer=None, suspect_layer=None, water_layer=None, grid=True, shadow_layer=None,
             aspect_balance=None):
    """ basemap options are srtm_hillshade, srtm_elevation, quadtree_rgb, nobasemap """

    product = ProductIO.readProduct(input_file)

    # mpl.rc('font', family='Times New Roman')
    # mpl.rc('text', usetex=True)

    if layer_str not in product.getBandNames():
        raise RuntimeError('{} not in product bands. Edit the parameter file.'.format(layer_str))

    legend_extension = 1
    bar_orientation = 'vertical'
    linewidth = 0.8
    gridlabel_size = 6

    # Create a new product With the band to plot only
    width = product.getSceneRasterWidth()
    height = product.getSceneRasterHeight()
    param_band = product.getBand(layer_str)

    mask_array = np.zeros(shape=(height, width), dtype=np.int32)
    for x in range(0, width):
        for y in range(0, height):
            if param_band.isPixelValid(x, y):
                mask_array[y, x] = 1
    invalid_mask = np.where(mask_array == 1, 1, 0)

    param_dt = param_band.getDataType()
    if param_dt <= 12:
        data_type = np.int32
        d_type = 'int32'
    elif param_dt == 30:
        data_type = np.float32
        d_type = 'float32'
    elif param_dt == 31:
        data_type = np.float64
        d_type = 'float64'
    else:
        raise ValueError('cannot handle band of data_sh type \'' + param_dt + '\'')

    GPF.getDefaultInstance().getOperatorSpiRegistry().loadOperatorSpis()
    BandDescriptor = jpy.get_type('org.esa.snap.core.gpf.common.BandMathsOp$BandDescriptor')
    targetBand1 = BandDescriptor()
    targetBand1.name = layer_str + '_ql'
    targetBand1.type = d_type
    targetBand1.expression = layer_str
    targetBands = jpy.array('org.esa.snap.core.gpf.common.BandMathsOp$BandDescriptor', 1)
    targetBands[0] = targetBand1

    parameters = HashMap()
    parameters.put('targetBands', targetBands)
    sub_product = GPF.createProduct('BandMaths', parameters, product)
    ProductUtils.copyGeoCoding(product, sub_product)
    log(env["General"]["log"], 'Reading Band {}'.format(layer_str))
    param_band = sub_product.getBand(layer_str + '_ql')

    # read constituent band
    param_arr = np.zeros(width * height, dtype=data_type)
    param_band.readPixels(0, 0, width, height, param_arr)
    param_arr = param_arr.reshape(height, width)

    # Pixel zählen
    masked_param_arr = np.ma.array(param_arr, fill_value=np.nan) #, mask = invalid_mask
    masked_param_arr = np.ma.masked_where(invalid_mask == False, masked_param_arr)
    #masked_param_arr = np.ma.masked_where(masked_param_arr >= 9999, masked_param_arr)
    #masked_param_arr = np.ma.masked_where(masked_param_arr < 0.000000000001, masked_param_arr)
    log(env["General"]["log"],
        '   applicable values are found in ' + str(masked_param_arr.count()) + ' of ' + str(height * width) + ' pixels')
    if masked_param_arr.count() == 0:
        log(env["General"]["log"], 'Image is empty, skipping...')
        return

    # load flag bands if requested
    masked_cloud_arr = None
    if cloud_layer:
        if sub_product.getBand(cloud_layer[0]) is None:
            cloud_mask = sub_product.getMaskGroup().get(cloud_layer[0])
            cloud_band = jpy.cast(cloud_mask, Mask)
        else:
            cloud_band = sub_product.getBand(cloud_layer[0])
        cloud_arr = np.zeros(width * height, dtype=np.int32)
        cloud_band.readPixels(0, 0, width, height, cloud_arr)
        cloud_arr = cloud_arr.reshape(height, width)  # <- Problem: kommen nur Nullen!!
        cloud_ind = np.where(cloud_arr == cloud_layer[1])
        cloud_arr[cloud_ind] = 100
        masked_cloud_arr = np.ma.masked_where(cloud_arr != 100, cloud_arr)

    masked_shadow_arr = None
    if shadow_layer:
        if sub_product.getBand(shadow_layer[0]) is None:
            shadow_mask = sub_product.getMaskGroup().get(shadow_layer[0])
            shadow_band = jpy.cast(shadow_mask, Mask)
        else:
            shadow_band = sub_product.getBand(shadow_layer[0])
        shadow_arr = np.zeros(width * height, dtype=np.int32)
        shadow_band.readPixels(0, 0, width, height, shadow_arr)
        shadow_arr = shadow_arr.reshape(height, width)
        shadow_ind = np.where(shadow_arr == shadow_layer[1])
        shadow_arr[shadow_ind] = 100
        masked_shadow_arr = np.ma.masked_where(shadow_arr != 100, shadow_arr)

    masked_suspect_arr = None
    if suspect_layer:
        if sub_product.getBand(suspect_layer[0]) is None:
            suspect_mask = sub_product.getMaskGroup().get(suspect_layer[0])
            suspect_band = jpy.cast(suspect_mask, Mask)
        else:
            suspect_band = sub_product.getBand(suspect_layer[0])
        suspect_arr = np.zeros(width * height, dtype=np.int32)
        suspect_band.readPixels(0, 0, width, height, suspect_arr)
        suspect_arr = suspect_arr.reshape(height, width)
        suspect_ind = np.where(suspect_arr == suspect_layer[1])
        suspect_arr[suspect_ind] = 100
        masked_suspect_arr = np.ma.masked_where(suspect_arr != 100, suspect_arr)

    if water_layer:
        if sub_product.getBand(water_layer[0]) is None:
            water_mask = sub_product.getMaskGroup().get(water_layer[0])
            water_band = jpy.cast(water_mask, Mask)
        else:
            water_band = sub_product.getBand(water_layer[0])
        water_arr = np.zeros(width * height, dtype=np.int32)
        water_band.readPixels(0, 0, width, height, water_arr)
        water_arr = water_arr.reshape(height, width)
        land_arr = np.zeros(width * height, dtype=np.int32)
        land_arr = land_arr.reshape(height, width)
        land_ind = np.where(water_arr != water_layer[1])
        land_arr[land_ind] = 100
        masked_param_arr = np.ma.masked_where(land_arr != 0, masked_param_arr)

    geocoding = sub_product.getSceneGeoCoding()
    lowlef = geocoding.getGeoPos(PixelPos(0, height - 1), None)
    upprig = geocoding.getGeoPos(PixelPos(width - 1, 0), None)
    prod_max_lat = upprig.lat
    prod_min_lat = lowlef.lat
    prod_max_lon = upprig.lon
    prod_min_lon = lowlef.lon

    # read lat and lon information
    if wkt:
        global canvas_area
        lons, lats = get_lons_lats(wkt)
        max_lat = max(lats)
        min_lat = min(lats)
        max_lon = max(lons)
        min_lon = min(lons)
        canvas_area = [[min_lon, min_lat], [max_lon, max_lat]]
    else:
        max_lat = prod_max_lat
        min_lat = prod_min_lat
        max_lon = prod_max_lon
        min_lon = prod_min_lon

    # add map extent if the input product hasn't been cropped e.g. with a lake shapefile
    if crop_ext:
        lat_ext = (max_lat - min_lat) / 8
        lon_ext = (max_lon - min_lon) / 8
    else:
        lat_ext = 0
        lon_ext = 0

    x_dist = haversine((min_lat, min_lon - lon_ext), (min_lat, max_lon + lon_ext))
    y_dist = haversine((min_lat - lat_ext, min_lon), (max_lat + lat_ext, min_lon))

    aspect_ratio = x_dist / y_dist
    if (0.7 < aspect_ratio) and (1.5 > aspect_ratio):
        orientation = 'square'
    elif x_dist < y_dist:
        orientation = 'portrait'
    else:
        orientation = 'landscape'

    # increase the smaller portion until the image aspect ratio is at most 3:2
    if aspect_balance:
        if aspect_ratio < 2 / 3:
            if lon_ext == 0:
                lon_ext = (max_lon - min_lon) / 20
            while aspect_ratio < 2 / 3:
                lon_ext = lon_ext * 1.1
                x_dist = haversine((min_lat, min_lon - lon_ext), (min_lat, max_lon + lon_ext))
                aspect_ratio = x_dist / y_dist
        if aspect_ratio > 3 / 2:
            if lat_ext == 0:
                lat_ext = (max_lat - min_lat) / 20
            while aspect_ratio > 3 / 2:
                lat_ext = lat_ext * 1.1
                y_dist = haversine((min_lat - lat_ext, min_lon), (max_lat + lat_ext, min_lon))
                aspect_ratio = x_dist / y_dist

    canvas_area = [[min_lon - lon_ext, min_lat - lat_ext], [max_lon + lon_ext, max_lat + lat_ext]]

    # Define colour scale
    title_str, legend_str, log = get_legend_str(layer_str)
    if log:
        log(env["General"]["log"], 'Transforming log data...')
        masked_param_arr = np.exp(masked_param_arr)

    bounds = None
    if ('hue' in title_str) and ('angle' in title_str):
        color_type = cm.get_cmap(name='viridis')
        param_range = [20, 230]
        tick_format = '%.0f'
        ticks = [45, 90, 135, 180, 225]
    elif ('dominant' in title_str) and ('wavelength' in title_str):
        param_range = [400, 700]
        color_type = colscales.spectral_cie(wvl_min = param_range[0], wvl_max = param_range[1])
        tick_format = '%.0f'
        ticks = [400, 450, 500, 550, 600, 650, 700]
    elif 'Forel-Ule' in title_str:
        color_type = colscales.forel_ule()
        param_range = [0.5, 21.5]
        ticks = [i + 1 for i in range(21)]
        boundaries = [fu - 0.5 for fu in range(1, 23, 1)]#[fu + 0.5 for fu in range(1, 21, 1)]
        norm = mpl.colors.BoundaryNorm(ticks, color_type)
        tick_format = '%.0f'
    elif 'Secchi' in title_str:
        color_type = cm.get_cmap(name='viridis_r')
        ticks = False
    else:
        color_type = cm.get_cmap(name='viridis')
        ticks = False
    #color_type = colscales.rainbow_king()
    #color_type = colscales.red2blue()
    #color_type = cm.get_cmap(name='magma_r')

    color_type.set_bad(alpha=0)
    if not param_range:
        log(env["General"]["log"], 'No range provided. Estimating...')
        range_intervals = [2000, 1000, 500, 200, 100, 50, 40, 30, 20, 15,
                           10, 8, 6, 4, 2, 1, 0.5, 0.2, 0.1, 0.08, 0.06,
                           0.04, 0.02, 0.01, 0.008, 0.006, 0.004, 0.002,
                           0.001]
        for n_interval in range(2, len(range_intervals)):
            if np.nanpercentile(masked_param_arr.compressed(), 90) > range_intervals[n_interval]:
                param_range = [0, range_intervals[n_interval - 2]]
                break
            elif np.nanpercentile(masked_param_arr.compressed(), 90) < range_intervals[-1]:
                param_range = [0, range_intervals[-1]]
                break
    log(env["General"]["log"], 'Parameters range set to: {}'.format(param_range))
    if not ticks:
        if param_range[1] >= 10:
            tick_format = '%.0f'
        elif param_range[1] >= 1:
            tick_format = '%.1f'
        elif param_range[1] >= 0.1:
            tick_format = '%.2f'
        elif param_range[1] >= 0.01:
            tick_format = '%.3f'
        else:
            tick_format = '%.4f'
        rel_ticks = [0.00, 0.2, 0.4, 0.6, 0.8, 1.00]
        ticks = [rel_tick * (param_range[1] - param_range[0]) + param_range[0] for rel_tick in rel_ticks]

    # Initialize plot
    fig = plt.figure(figsize=((aspect_ratio * 3) + (2 * legend_extension), 3))
    subplot_axes = fig.add_subplot(111, projection=ccrs.PlateCarree())  # ccrs.PlateCarree()) ccrs.Mercator())

    if wkt:
        subplot_axes.set_extent([canvas_area[0][0], canvas_area[1][0], canvas_area[0][1], canvas_area[1][1]])

    ##############################
    # ### SRTM plot version ######
    ##############################

    if basemap in ['srtm_hillshade', 'srtm_elevation']:
        if canvas_area[1][1] <= 60 and canvas_area[0][1] >= -60:
            if x_dist < 50 and y_dist < 50:
                log(env["General"]["log"], '   larger image side is ' + str(round(max(x_dist, y_dist), 1)) + ' km, applying SRTM1')
                source = srtm.SRTM1Source
            else:
                log(env["General"]["log"], '   larger image side is ' + str(round(max(x_dist, y_dist), 1)) + ' km, applying SRTM3')
                source = srtm.SRTM3Source

            #  Add shading if requested
            if basemap == 'srtm_hillshade':
                log(env["General"]["log"], '   preparing SRTM hillshade basemap')
                srtm_raster = PostprocessedRasterSource(source(max_nx=8, max_ny=8), shade)
                color_vals = [[0.8, 0.8, 0.8, 1], [1.0, 1.0, 1.0, 1]]
                shade_grey = colors.LinearSegmentedColormap.from_list("ShadeGrey", color_vals)
                base_cols = shade_grey
            else:  # elif basemap == 'srtm_elevation':
                log(env["General"]["log"], '   preparing SRTM elevation basemap')
                srtm_raster = PostprocessedRasterSource(source(max_nx=6, max_ny=6), elevate)
                color_vals = [[0.7, 0.7, 0.7, 1], [0.90, 0.90, 0.90, 1], [0.97, 0.97, 0.97, 1], [1.0, 1.0, 1.0, 1]]
                elev_grey = colors.LinearSegmentedColormap.from_list("ElevGrey", color_vals)
                base_cols = elev_grey

            # Plot the background
            subplot_axes.add_raster(srtm_raster, cmap=base_cols)

        else:
            log(env["General"]["log"], '   no SRTM data outside 55 deg N/S, proceeding without basemap')
            basemap = 'nobasemap'

    ##################################
    # ### non-SRTM plot version ######
    ##################################

    if basemap in ['quadtree_rgb', 'nobasemap']:

        if basemap == 'nobasemap':
            log(env["General"]["log"], '   proceeding without basemap')
        if basemap == 'quadtree_rgb':
            log(env["General"]["log"], '   preparing Quadtree tiles basemap')

            # background = maps.GoogleTiles(style='street')
            # background = maps.GoogleTiles(style='satellite')
            # background = maps.GoogleTiles(style='terrain')
            # background = maps.MapQuestOpenAerial()
            # background = maps.OSM()
            background = maps.QuadtreeTiles()
            # crs = maps.GoogleTiles().crs
            # crs = maps.QuadtreeTiles().crs

            # Add background
            subplot_axes.add_image(background, 10)

    ##############################
    # ### both plot versions #####
    ##############################

    # Plot parameter
    # Fun fact: interpolation='none' causes interpolation if opened in OSX Preview:
    # https://stackoverflow.com/questions/54250441/pdf-python-plot-is-blurry-image-interpolation
    parameter = subplot_axes.imshow(masked_param_arr, extent=[prod_min_lon, prod_max_lon, prod_min_lat, prod_max_lat],
                                    transform=ccrs.PlateCarree(), origin='upper', cmap=color_type, #interpolation='none',
                                    vmin=param_range[0], vmax=param_range[1], zorder=10)

    # Plot flags
    if cloud_layer:
        cloud_colmap = colscales.cloud_color()
        cloud_colmap.set_bad('w', 0)
        _ = plt.imshow(masked_cloud_arr, extent=[prod_min_lon, prod_max_lon, prod_min_lat, prod_max_lat],
                       transform=ccrs.PlateCarree(), origin='upper', cmap=cloud_colmap, interpolation='none',
                       zorder=20)

    if shadow_layer:
        shadow_colmap = colscales.shadow_color()
        shadow_colmap.set_bad('w', 0)
        _ = plt.imshow(masked_shadow_arr, extent=[prod_min_lon, prod_max_lon, prod_min_lat, prod_max_lat],
                       transform=ccrs.PlateCarree(), origin='upper', cmap=shadow_colmap, interpolation='none',
                       zorder=20)

    if suspect_layer:
        suspect_colmap = colscales.suspect_color()
        suspect_colmap.set_bad('w', 0)
        _ = plt.imshow(masked_suspect_arr, extent=[prod_min_lon, prod_max_lon, prod_min_lat, prod_max_lat],
                       transform=ccrs.PlateCarree(), origin='upper', cmap=suspect_colmap, interpolation='none',
                       zorder=20)

    # Add gridlines
    if grid:
        gridlines = subplot_axes.gridlines(draw_labels=True, linewidth=linewidth, color='black', alpha=1.0,
                                           linestyle=':', zorder=23)  # , n_steps=3)
        if orientation == 'square':
            x_n_ticks = 4
            y_n_ticks = 4
        elif orientation == 'portrait':
            x_n_ticks = 3
            y_n_ticks = 4
        else:
            x_n_ticks = 4
            y_n_ticks = 3

        x_ticks = get_tick_positions(canvas_area[0][0], canvas_area[1][0], x_n_ticks)
        y_ticks = get_tick_positions(canvas_area[0][1], canvas_area[1][1], y_n_ticks)
        gridlines.xlocator = mpl.ticker.FixedLocator(x_ticks)
        gridlines.ylocator = mpl.ticker.FixedLocator(y_ticks)

        gridlines.xlabel_style = {'size': gridlabel_size, 'color': 'black'}
        gridlines.ylabel_style = {'size': gridlabel_size, 'color': 'black'}

    # Create colorbar
    log(env["General"]["log"], '   creating colorbar')
    fig = plt.gcf()
    fig.subplots_adjust(top=1, bottom=0, left=0,
                        right=(aspect_ratio * 3) / ((aspect_ratio * 3) + (1.2 * legend_extension)),
                        wspace=0.05, hspace=0.05)
    cax = fig.add_axes([(aspect_ratio * 3) / ((aspect_ratio * 3) + (0.6 * legend_extension)), 0.15, 0.03, 0.7])

    # discrete colorbar option for Forel-Ule classes
    if 'Forel-Ule' in title_str:
        cbar = fig.colorbar(parameter, cax=cax, orientation=bar_orientation, norm=norm, boundaries=boundaries,
                            ticks=ticks, format=tick_format)
        cbar.ax.tick_params(labelsize=6)
    else:
        cbar = fig.colorbar(parameter, cax=cax, ticks=ticks, format=tick_format, orientation=bar_orientation)
        cbar.ax.tick_params(labelsize=8)

    # Save plot
    plt.title(legend_str, y=1.05, fontsize=8)
    log(env["General"]["log"], 'Writing {}'.format(os.path.basename(output_file)))
    plt.savefig(output_file, bbox_inches='tight', dpi=300)
    plt.close()
    sub_product.closeIO()
    product.closeIO()


def elevate(located_elevations):
    canvas_extent = (canvas_area[0][0], canvas_area[1][0], canvas_area[0][1], canvas_area[1][1])
    x_pixpdeg = len(located_elevations[0][0, :]) / (located_elevations.extent[1] - located_elevations.extent[0])
    y_pixpdeg = len(located_elevations[0][:, 0]) / (located_elevations.extent[3] - located_elevations.extent[2])
    left_ind = math.floor(x_pixpdeg * (canvas_area[0][0] - located_elevations.extent[0]))
    righ_ind = math.floor(x_pixpdeg * (canvas_area[1][0] - located_elevations.extent[0]))
    lowe_ind = len(located_elevations[0][:, 0]) - math.ceil(
        y_pixpdeg * (canvas_area[1][1] - located_elevations.extent[2]))
    uppe_ind = len(located_elevations[0][:, 0]) - math.ceil(
        y_pixpdeg * (canvas_area[0][1] - located_elevations.extent[2]))

    # Rückgabe ganzer SRTM Tiles, macht Bildcanvas so gross wie unsichtbare SRTM Fläche
    # return LocatedImage(scaled_elevations, located_elevations.extent)
    return LocatedImage(located_elevations[0][lowe_ind:uppe_ind, left_ind:righ_ind], canvas_extent)


def shade(located_elevations):
    located_shades = srtm.add_shading(located_elevations.image, azimuth=135, altitude=15)
    canvas_extent = (canvas_area[0][0], canvas_area[1][0], canvas_area[0][1], canvas_area[1][1])
    x_pixpdeg = len(located_shades[0, :]) / (located_elevations.extent[1] - located_elevations.extent[0])
    y_pixpdeg = len(located_shades[:, 0]) / (located_elevations.extent[3] - located_elevations.extent[2])
    left_ind = math.floor(x_pixpdeg * (canvas_area[0][0] - located_elevations.extent[0]))
    righ_ind = math.floor(x_pixpdeg * (canvas_area[1][0] - located_elevations.extent[0]))
    lowe_ind = len(located_shades[:, 0]) - math.ceil(y_pixpdeg * (canvas_area[1][1] - located_elevations.extent[2]))
    uppe_ind = len(located_shades[:, 0]) - math.ceil(y_pixpdeg * (canvas_area[0][1] - located_elevations.extent[2]))

    # Rückgabe ganzer SRTM Tiles, macht Bildcanvas so gross wie unsichtbare SRTM Fläche
    # return LocatedImage(located_shades, located_elevations.extent)
    return LocatedImage(located_shades[lowe_ind:uppe_ind, left_ind:righ_ind], canvas_extent)


def get_tick_positions(lower, upper, n_ticks):
    coord_range = upper - lower
    exponent = round(np.log(coord_range))
    lower_floored = np.floor(lower * pow(10, - exponent)) * pow(10, exponent)
    upper_ceiled = np.ceil(upper * pow(10, - exponent)) * pow(10, exponent)
    range_section = (upper_ceiled - lower_floored) / coord_range
    grid_step = (upper_ceiled - lower_floored) / (n_ticks * range_section)
    decimal = 1
    while grid_step < 10:
        grid_step = grid_step * 10
        decimal = decimal * 10
    if grid_step < 20:
        grid_step_round = 10 / decimal
    elif grid_step < 50:
        grid_step_round = 20 / decimal
    elif grid_step < 100:
        grid_step_round = 50 / decimal
    else:
        grid_step_round = 50 / decimal
    tick_list = [lower_floored]
    current = lower_floored + grid_step_round
    while tick_list[-1] < upper_ceiled:
        tick_list.append(current)
        current = current + grid_step_round
    return tick_list


def get_legend_str(layer_str):

    # Fluo products
    if layer_str in ['L_CHL']:
        legend_str = r'$\mathbf{[mg/m^3]}$'
        title_str = r'$\mathbf{L-Fluo\/CHL}$'
        log = False
    elif layer_str in ['L_FPH']:
        legend_str = r'$\mathbf{[mW\/m^{-2}\/sr^{-1}\/nm^{-1}]}$'
        title_str = r'$\mathbf{L-Fluo\/phytoplankton\/fluorescence}$'
        log = False
    elif layer_str in ['L_APD']:
        legend_str = r'$\mathbf{[mW\/m^{-2}\/sr^{-1}\/nm^{-1}]}$'
        title_str = r'$\mathbf{L-Fluo\/phytoplankton\/absorption}$'
        log = False

    # C2RCC products
    elif 'rhow' in layer_str and 'rhown' not in layer_str:
        lstr = re.findall(r'\d*$', layer_str)[0]
        legend_str = r'$\mathbf{[dl]}$'
        title_str = r'$\mathbf{C2RCC\/\/R_w(' + lstr + ')}$'
        log = False
    elif 'rhown' in layer_str:
        lstr = re.findall(r'\d*$', layer_str)[0]
        legend_str = r'$\mathbf{[dl]}$'
        title_str = r'$\mathbf{C2RCC\/\/R_{w,n}(' + lstr + ')}$'
        log = False
    elif layer_str in ['kdmin']:
        legend_str = r'$\mathbf{[m^-1]}$'
        title_str = r'$\mathbf{C2RCC\/K_{d}}$'
        log = False
    elif layer_str in ['conc_tsm']:
        legend_str = r'$\mathbf{[g/m^3]}$'
        title_str = r'$\mathbf{C2RCC\/TSM}$'
        log = False
    elif layer_str in ['conc_chl']:
        legend_str = r'$\mathbf{[mg/m^3]}$'
        title_str = r'$\mathbf{C2RCC\/CHL}$'
        log = False

    # MPH products
    elif layer_str == 'chl':
        legend_str = r'$\mathbf{[mg/m^3]}$'
        title_str = r'$\mathbf{MPH\/CHL}$'
        log = False
    elif layer_str == 'mph':
        legend_str = r'$\mathbf{[dl]}$'
        title_str = r'$\mathbf{MPH}$'
        log = False

    # sen2cor products
    elif layer_str == 'ndvi':
        legend_str = r'$\mathbf{[dl}$'
        title_str = r'$\mathbf{NDVI}$'
        log = False
    elif layer_str == 'ndmi':
        legend_str = r'$\mathbf{NDMI\/[dl]}$'
        title_str = r'$\mathbf{NDMI}$'
        log = False
    elif layer_str == 'ndwi_gao':
        legend_str = r'$\mathbf{[dl]}$'
        title_str = r'$\mathbf{Gao\/NDWI}$'
        log = False
    elif layer_str == 'ndwi_mcfeeters':
        legend_str = r'$\mathbf{[dl]}$'
        title_str = r'$\mathbf{McFeeters\/NDWI}$'
        log = False

    # polymer products
    elif 'Rw' in layer_str:
        lstr = re.findall(r'\d{3}', layer_str)[0]
        legend_str = r'$\mathbf{[dl]}$'
        title_str = r'$\mathbf{Polymer\/\/R_w(' + lstr + ')}$'
        log = False
    elif layer_str == 'bbs':
        legend_str = r'$\mathbf{[m^{-1}]}$'
        title_str = r'$\mathbf{Polymer\/b_{b_{s}}}$'
        log = False
    elif layer_str == 'logchl':
        legend_str = r'$\mathbf{[mg/m^3]}$'
        title_str = r'$\mathbf{Polymer\/\/CHL}$'
        log = True
    elif layer_str == 'tsm_vantrepotte665':
        legend_str = r'$\mathbf{[g/m^3]}$'
        title_str = r'$\mathbf{Vantrepotte\/665\/nm\/TSM}$'
        log = False
    elif layer_str == 'tsm_zhang709':
        legend_str = r'$\mathbf{[g/m^3]}$'
        title_str = r'$\mathbf{Zhang\/709\/nm\/TSM}$'
        log = False
    elif layer_str == 'tsm_binding754':
        legend_str = r'$\mathbf{[g/m^3]}$'
        title_str = r'$\mathbf{Binding\/754\/nm\/TSM}$'
        log = False
    elif layer_str == 'chl_oc2':
        legend_str = r'$\mathbf{[mg/m^3]}$'
        title_str = r'$\mathbf{OC2\/CHL}$'
        log = False
    elif layer_str == 'chl_oc3':
        legend_str = r'$\mathbf{[mg/m^3]}$'
        title_str = r'$\mathbf{OC3\/CHL}$'
        log = False
    elif layer_str == 'chl_2band':
        legend_str = r'$\mathbf{[mg/m^3]}$'
        title_str = r'$\mathbf{2-band\/CHL}$'
        log = False
    elif layer_str == 'chl_gons':
        legend_str = r'$\mathbf{[mg/m^3]}$'
        title_str = r'$\mathbf{Gons\/CHL}$'
        log = False
    elif layer_str == 'chl_ndci':
        legend_str = r'$\mathbf{[dl]}$'
        title_str = r'$\mathbf{NDCI}$'
        log = False
    elif layer_str == 'rgb_tri':
        legend_str = r'$\mathbf{[dl]}$'
        title_str = r'$\mathbf{RGB\/reflectance\/triangle\/area}$'
        log = False
    elif layer_str == 'rgb_int':
        legend_str = r'$\mathbf{[dl]}$'
        title_str = r'$\mathbf{RGB\/reflectance\/integral\/area}$'
        log = False

    # QAA products
    elif layer_str.startswith('Z'):
        lstr = re.findall(r'\d{3}', layer_str)[0]
        legend_str = r'$\mathbf{[m]}$'
        title_str = r'$\mathbf{Secchi\/\/depth at ' + lstr + '}$'
        log = False
    elif layer_str == 'bbs':
        legend_str = r'$\mathbf{[m^{-1}]}$'
        title_str = r'$\mathbf{Polymer\/b_{b_{s}}}$'
        log = False

    # Forel-Ule products
    elif layer_str == 'forel_ule':
        legend_str = r'$\mathbf{[FU]}$'
        title_str = r'$\mathbf{Forel-Ule\/type}$'
        log = False
    elif layer_str == 'dominant_wavelength':
        legend_str = r'$\mathbf{[nm]}$'
        title_str = r'$\mathbf{dominant\/wavelength}$'
        log = False
    elif layer_str == 'hue_angle':
        legend_str = r'$\mathbf{[deg]}$'
        title_str = r'$\mathbf{hue\/angle}$'
        log = False

    # all other products
    else:
        legend_str = 'ND'
        title_str = layer_str
        log = False
    return title_str, legend_str, log
