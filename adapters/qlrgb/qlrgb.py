#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""The QLRGB adapter creates RGB quick looks output as .pdf files."""

import cartopy.crs as ccrs
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import os

from PIL import Image
from snappy import ProductIO, PixelPos

from utils.auxil import log
from utils.product_fun import get_lons_lats

# key of the params section for this adapter
PARAMS_SECTION = "QLRGB"

plt.switch_backend('agg')
mpl.pyplot.switch_backend('agg')
canvas_area = []


def apply(env, params, l2product_files, date):
    """Apply QLRGB adapter.

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
        processor = key[0:key.find("_")].upper()
        if processor in l2product_files.keys():
            ql_name = key[key.find("_") + 1:]
            log(env["General"]["log"], "Creating {} quicklooks for {}".format(ql_name, processor))
            bands = list(filter(None, params[PARAMS_SECTION][key].split(",")))[0:-1]
            bandmax = list(filter(None, params[PARAMS_SECTION][key].split(",")))[-1]
            if params['General']['sensor'] == "OLCI":
                bands = [band.replace('radiance', 'reflectance') for band in bands]
            ql_path = os.path.dirname(l2product_files[processor]) + "-" + ql_name
            product_name = os.path.splitext(os.path.basename(l2product_files[processor]))[0]
            ql_file = os.path.join(ql_path, "{}-{}.pdf".format(product_name, ql_name))
            if os.path.exists(ql_file):
                if "synchronise" in params["General"].keys() and params['General']['synchronise'] == "false":
                    log(env["General"]["log"], "Removing file: ${}".format(ql_file))
                    os.remove(ql_file)
                    plot_pic(env, l2product_files[processor], ql_file, wkt, rgb_layers=bands, max_val=float(bandmax))
                else:
                    log(env["General"]["log"], "Skipping QLRGB. Target already exists: {}".format(os.path.basename(ql_file)))
            else:
                os.makedirs(os.path.dirname(ql_file), exist_ok=True)
                plot_pic(env, l2product_files[processor], ql_file, wkt, rgb_layers=bands, max_val=float(bandmax))


def plot_pic(env, input_file, output_file, wkt=None, crop_ext=None, rgb_layers=None, grid=True, max_val=0.10):
    linewidth = 0.8
    gridlabel_size = 5

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
    lowlef = geocoding.getGeoPos(PixelPos(0, height), None)
    upprig = geocoding.getGeoPos(PixelPos(width, 0), None)

    # add map extent if the input product hasn't been cropped e.g. with a lake shapefile
    if crop_ext:
        lat_ext = (upprig.lat - lowlef.lat) / 8
        lon_ext = (upprig.lon - lowlef.lon) / 8
    else:
        lat_ext = 0
        lon_ext = 0

    lon_range = (upprig.lon + lon_ext) - (lowlef.lon - lon_ext)
    lat_range = (upprig.lat + lat_ext) - (lowlef.lat - lon_ext)

    # Calculate a suitable grid distance with which the smaller image portion gets three gridlines
    grid_dist = min(lon_range, lat_range) / 3

    if grid_dist < 0.01:
        decimal = 0.001
    elif grid_dist < 0.1:
        decimal = 0.01
    elif grid_dist < 1:
        decimal = 0.1
    elif grid_dist < 10:
        decimal = 1
    elif grid_dist < 100:
        decimal = 10
    else:
        decimal = 100

    grid_dist = round(grid_dist / decimal) * decimal

    # Calculate a gridline anchor position with a round value, around which the other gridlines are defined
    lat_center = round((lowlef.lat + (upprig.lat - lowlef.lat) / 2) / ( decimal * 10)) * (decimal * 10)
    lon_center = round((lowlef.lon + (upprig.lon - lowlef.lon) / 2) / ( decimal * 10)) * (decimal * 10)
    x_ticks = [lon_center]
    y_ticks = [lat_center]
    i=0
    while (max(x_ticks) <= upprig.lon or min(x_ticks) >= lowlef.lon):
        i+=1
        x_ticks.extend((lon_center + (i * grid_dist), lon_center - (i * grid_dist)))
    x_ticks.sort()
    i=0
    while (max(y_ticks) <= upprig.lat or min(y_ticks) >= lowlef.lat):
        i+=1
        y_ticks.extend((lat_center + (i * grid_dist), lat_center - (i * grid_dist)))
    y_ticks.sort()

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

        gridlines.xlocator = mpl.ticker.FixedLocator(x_ticks)
        gridlines.ylocator = mpl.ticker.FixedLocator(y_ticks)

        gridlines.xlabel_style = {'size': gridlabel_size, 'color': 'black'}
        gridlines.ylabel_style = {'size': gridlabel_size, 'color': 'black'}

    # Save plot
    log(env["General"]["log"], 'Saving image {}'.format(os.path.basename(output_file)))
    plt.savefig(output_file, dpi=300)
    plt.close()
    product.closeIO()
