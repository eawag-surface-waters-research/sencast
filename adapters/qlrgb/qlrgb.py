#! /usr/bin/env python
# -*- coding: utf-8 -*-

import cartopy.crs as ccrs
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import os

from haversine import haversine
from PIL import Image
from snappy import ProductIO, PixelPos

from product_fun import get_lons_lats

# key of the params section for this adapter
PARAMS_SECTION = "QLRGB"

plt.switch_backend('agg')
mpl.pyplot.switch_backend('agg')
canvas_area = []


def apply(_, params, l2_product_files):
    wkt = params['General']['wkt']
    for ql_key in list(filter(None, params[PARAMS_SECTION]["qls"].split(","))):
        processor = ql_key[0:ql_key.find("_")]
        ql_name = ql_key.replace("{}_".format(processor), "")
        print("Creating {} quicklooks for {}".format(ql_name, processor))
        bands = list(filter(None, params[PARAMS_SECTION][ql_key].split(",")))
        max_value = float(params[PARAMS_SECTION]["{}_max".format(ql_key)])
        if params['General']['sensor'] == "OLCI":
            bands = [band.replace('radiance', 'reflectance') for band in bands]
        ql_path = os.path.dirname(l2_product_files[processor]) + "-" + ql_name
        product_name = os.path.splitext(os.path.basename(l2_product_files[processor]))[0]
        ql_file = os.path.join(ql_path, "{}-{}.png".format(product_name, ql_name))
        os.makedirs(os.path.dirname(ql_file), exist_ok=True)
        plot_pic(l2_product_files[processor], ql_file, wkt, rgb_layers=bands, max_val=max_value)


def plot_pic(input_file, output_file, wkt=None, crop_ext=None, rgb_layers=None, grid=True, max_val=0.10):
    linewidth = 0.8
    gridlabel_size = 6

    product = ProductIO.readProduct(input_file)

    all_bns = product.getBandNames()
    for rgbls in rgb_layers:
        if rgbls not in all_bns:
            raise RuntimeError("{} not in product bands. Edit the parameter file.".format(rgbls))

    # Create a new product With RGB bands only
    width = product.getSceneRasterWidth()
    height = product.getSceneRasterHeight()

    red_band = product.getBand(rgb_layers[0])
    red_dt = red_band.getDataType()

    if red_dt <= 12:
        data_type = np.int32
        # d_type = 'int32'
    elif red_dt == 21:
        data_type = np.float64
        # d_type = 'float64'
    elif red_dt == 30:
        data_type = np.float32
        # d_type = 'float32'
    elif red_dt == 31:
        data_type = np.float64
        # d_type = 'float64'
    else:
        raise ValueError("Cannot handle band of data_sh type '{}'".format(str(red_dt)))

    red_band = product.getBand(rgb_layers[0])
    green_band = product.getBand(rgb_layers[1])
    blue_band = product.getBand(rgb_layers[2])

    # read rgb bands
    red_arr = np.zeros(width * height, dtype=data_type)
    red_band.readPixels(0, 0, width, height, red_arr)
    red_arr = red_arr.reshape(height, width)
    green_arr = np.zeros(width * height, dtype=data_type)
    green_band.readPixels(0, 0, width, height, green_arr)
    green_arr = green_arr.reshape(height, width)
    blue_arr = np.zeros(width * height, dtype=data_type)
    blue_band.readPixels(0, 0, width, height, blue_arr)
    blue_arr = blue_arr.reshape(height, width)

    # read lat and lon information
    geocoding = product.getSceneGeoCoding()
    lowlef = geocoding.getGeoPos(PixelPos(0, height - 1), None)
    upprig = geocoding.getGeoPos(PixelPos(width - 1, 0), None)

    # add map extent if the input product hasn't been cropped e.g. with a lake shapefile
    if crop_ext:
        lat_ext = (upprig.lat - lowlef.lat) / 8
        lon_ext = (upprig.lon - lowlef.lon) / 8
    else:
        lat_ext = 0
        lon_ext = 0

    x_dist = haversine((lowlef.lat, lowlef.lon - lon_ext), (lowlef.lat, upprig.lon + lon_ext))
    y_dist = haversine((lowlef.lat - lat_ext, lowlef.lon), (upprig.lat + lat_ext, lowlef.lon))
    aspect_ratio = x_dist / y_dist
    if (0.7 < aspect_ratio) and (1.5 > aspect_ratio):
        orientation = 'square'
    elif x_dist < y_dist:
        orientation = 'portrait'
    else:
        orientation = 'landscape'

    product_area = [[lowlef.lon - lon_ext, lowlef.lat - lat_ext], [upprig.lon + lon_ext, upprig.lat + lat_ext]]

    # Initialize plot
    fig = plt.figure()
    subplot_axes = fig.add_subplot(111, projection=ccrs.PlateCarree())  # ccrs.Mercator())

    # adjust image brightness scaling (empirical...)
    rgb_array = np.zeros((height, width, 3), 'float32')  # uint8
    rgb_array[..., 0] = red_arr
    rgb_array[..., 1] = green_arr
    rgb_array[..., 2] = blue_arr

    scale_factor = 250 / max_val

    for i_rgb in range(rgb_array.shape[-1]):
        zero_ind = np.where(rgb_array[:, :, i_rgb] == 0)
        nan_ind = np.where(rgb_array[:, :, i_rgb] == -1)
        exc_ind = np.where(rgb_array[:, :, i_rgb] > max_val)
        rgb_array[:, :, i_rgb] = rgb_array[:, :, i_rgb] * scale_factor
        rgb_array[:, :, i_rgb][zero_ind] = 250
        rgb_array[:, :, i_rgb][nan_ind] = 250
        rgb_array[:, :, i_rgb][exc_ind] = 250

    img = Image.fromarray(rgb_array.astype(np.uint8))

    global canvas_area
    if wkt:
        lons, lats = get_lons_lats(wkt)
        canvas_area = [[min(lons), min(lats)], [max(lons), max(lats)]]
    else:
        canvas_area = product_area
    subplot_axes.set_extent([canvas_area[0][0], canvas_area[1][0], canvas_area[0][1], canvas_area[1][1]])

    subplot_axes.imshow(img, extent=[product_area[0][0], product_area[1][0], product_area[0][1], product_area[1][1]],
                        transform=ccrs.PlateCarree(), origin='upper', interpolation='nearest', zorder=1)

    # Add gridlines
    if grid:
        gridlines = subplot_axes.gridlines(draw_labels=True, linewidth=linewidth, color='black', alpha=1.0,
                                           linestyle=':', zorder=2)  # , n_steps=3)
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

    # Save plot
    print('Saving image {}'.format(os.path.basename(output_file)))
    plt.savefig(output_file, box_inches='tight', dpi=300)
    plt.close()
    product.closeIO()


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
