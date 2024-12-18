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
from netCDF4 import Dataset

from utils.auxil import log
from utils.product_fun import get_band_names_from_nc, get_name_width_height_from_nc, \
    get_lons_lats, get_lat_lon_from_x_y_from_nc, read_pixels_from_nc, get_np_data_type

# key of the params section for this adapter
PARAMS_SECTION = "QLRGB"
QL_PATH = "{}/QuickLooks/{}-{}"
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

            if not isinstance(l2product_files[processor], list):
                l2product_files[processor] = [l2product_files[processor]]
            for l2product_file in l2product_files[processor]:
                folder = os.path.basename(os.path.dirname(l2product_file))
                path = os.path.dirname(os.path.dirname(l2product_file))
                ql_path = QL_PATH.format(path, folder, ql_name)
                product_name = os.path.splitext(os.path.basename(l2product_file))[0]
                ql_file = os.path.join(ql_path, "{}-{}.pdf".format(product_name, ql_name))
                if os.path.exists(ql_file):
                    if "overwrite" in params["General"].keys() and params['General']['overwrite'] == "true":
                        log(env["General"]["log"], "Removing file: ${}".format(ql_file))
                        os.remove(ql_file)
                        plot_pic(env, l2product_file, ql_file, wkt, rgb_layers=bands, max_val=float(bandmax))
                    else:
                        log(env["General"]["log"],
                            "Skipping QLRGB. Target already exists: {}".format(os.path.basename(ql_file)))
                else:
                    os.makedirs(os.path.dirname(ql_file), exist_ok=True)
                    plot_pic(env, l2product_file, ql_file, wkt, rgb_layers=bands, max_val=float(bandmax))


def plot_pic(env, input_file, output_file, wkt=None, crop_ext=None, rgb_layers=None, grid=True, max_val=0.10):
    linewidth = 0.8
    gridlabel_size = 5

    with Dataset(input_file) as src:
        product_band_names = get_band_names_from_nc(src)
        for rgbls in rgb_layers:
            if rgbls not in product_band_names:
                raise RuntimeError("{} not in product bands. Edit the parameter file.".format(rgbls))

        # Create a new product With RGB bands only
        data_type = get_np_data_type(src, rgb_layers[0])

        # read rgb bands
        _, width, height = get_name_width_height_from_nc(src)
        red_arr = read_pixels_from_nc(src, rgb_layers[0], 0, 0, width, height, dtype=data_type)
        red_arr = red_arr.reshape(height, width)
        green_arr = read_pixels_from_nc(src, rgb_layers[1], 0, 0, width, height, dtype=data_type)
        green_arr = green_arr.reshape(height, width)
        blue_arr = read_pixels_from_nc(src, rgb_layers[2], 0, 0, width, height, dtype=data_type)
        blue_arr = blue_arr.reshape(height, width)

        # read lat and lon information
        lat_min, lon_min = get_lat_lon_from_x_y_from_nc(src, 0, height-1)
        lat_max, lon_max = get_lat_lon_from_x_y_from_nc(src, width-1, 0)

        # add map extent if the input product hasn't been cropped e.g. with a lake shapefile
        if crop_ext:
            lat_ext = (lat_max - lat_min) / 8
            lon_ext = (lon_max - lon_min) / 8
        else:
            lat_ext = 0
            lon_ext = 0

        lon_range = (lon_max + lon_ext) - (lon_min - lon_ext)
        lat_range = (lat_max + lat_ext) - (lat_min - lon_ext)

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
        lat_center = round((lat_min + (lat_max - lat_min) / 2) / (decimal * 10)) * (decimal * 10)
        lon_center = round((lon_min + (lon_max - lon_min) / 2) / (decimal * 10)) * (decimal * 10)
        x_ticks = [lon_center]
        y_ticks = [lat_center]
        i = 0
        while max(x_ticks) <= lon_max or min(x_ticks) >= lon_min:
            i += 1
            x_ticks.extend((lon_center + (i * grid_dist), lon_center - (i * grid_dist)))
        x_ticks.sort()
        i = 0
        while max(y_ticks) <= lat_max or min(y_ticks) >= lat_min:
            i += 1
            y_ticks.extend((lat_center + (i * grid_dist), lat_center - (i * grid_dist)))
        y_ticks.sort()

        product_area = [[lon_min - lon_ext, lat_min - lat_ext], [lon_max + lon_ext, lat_max + lat_ext]]

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
        subplot_axes.imshow(img,
                            extent=[product_area[0][0], product_area[1][0], product_area[0][1], product_area[1][1]],
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
