#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
The QLSingleBand adapter creates single-band quick looks output as .png files.
Individual bands are plotted geospatially using matplotlib and exported to .png
"""

import cartopy.crs as ccrs
import cartopy.io.srtm as srtm
import cartopy.io.img_tiles as maps
import math
import matplotlib as mpl
import matplotlib.cm as cm
import matplotlib.colors as colors
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import os
import re
from cartopy.io import PostprocessedRasterSource, LocatedImage
from netCDF4 import Dataset

import adapters.qlsingleband.colour_scales as colscales
from utils.auxil import log
from utils.product_fun import get_lons_lats, get_lat_lon_from_x_y_from_nc, get_band_names_from_nc, \
    get_name_width_height_from_nc, read_pixels_from_nc

plt.switch_backend('agg')
mpl.pyplot.switch_backend('agg')
canvas_area = []

# key of the params section for this adapter
PARAMS_SECTION = "QLSINGLEBAND"
QL_PATH = "{}/QuickLooks/{}-{}"


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
    failed = []
    for key in params[PARAMS_SECTION].keys():
        processor = key.upper()
        if processor in l2product_files.keys():
            log(env["General"]["log"], "Creating quicklooks for {}".format(processor))
            bands = list(filter(None, params[PARAMS_SECTION][key].split(",")))[::3]
            bandmins = list(filter(None, params[PARAMS_SECTION][key].split(",")))[1::3]
            bandmaxs = list(filter(None, params[PARAMS_SECTION][key].split(",")))[2::3]

            if not isinstance(l2product_files[processor], list):
                l2product_files[processor] = [l2product_files[processor]]
            for l2product_file in l2product_files[processor]:
                product_name = os.path.splitext(os.path.basename(l2product_file))[0]
                for band, bandmin, bandmax in zip(bands, bandmins, bandmaxs):
                    if band == 'secchidepth':
                        processor = 'SECCHIDEPTH'
                    elif band == 'forelule':
                        processor = 'FORELULE'

                    folder = os.path.basename(os.path.dirname(l2product_file))
                    path = os.path.dirname(os.path.dirname(l2product_file))
                    ql_path = QL_PATH.format(path, folder, band)

                    ql_file = os.path.join(ql_path, "{}-{}.pdf".format(product_name, band))
                    if os.path.exists(ql_file):
                        if "overwrite" in params["General"].keys() and params['General']['overwrite'] == "true":
                            log(env["General"]["log"], "Removing file: ${}".format(ql_file))
                            os.remove(ql_file)
                        else:
                            log(env["General"]["log"],
                                "Skipping QLSINGLEBAND. Target already exists: {}".format(os.path.basename(ql_file)))
                            continue
                    param_range = None if float(bandmin) == 0 == float(bandmax) else [float(bandmin), float(bandmax)]
                    os.makedirs(os.path.dirname(ql_file), exist_ok=True)
                    try:
                        plot_map(env, l2product_file, ql_file, band, wkt, "esri_shaded", param_range=param_range)
                    except Exception as e:
                        print(e)
                        failed.append(os.path.basename(ql_file))
    if len(failed) > 0:
        raise ValueError("Singleband plot failed for: {}".format(",".join(failed)))


def plot_map(env, input_file, output_file, band_name, wkt=None, basemap='srtm_elevation', crop_ext=None,
             param_range=None, cloud_layer=None, suspect_layer=None, water_layer=None, grid=True, shadow_layer=None):
    """ basemap options are srtm_hillshade, srtm_elevation, quadtree_rgb, nobasemap """

    # mpl.rc('font', family='Times New Roman')
    # mpl.rc('text', usetex=True)

    with Dataset(input_file) as src:
        if band_name not in get_band_names_from_nc(src):
            raise RuntimeError('{} not in product bands. Edit the parameter file.'.format(band_name))

        legend_extension = 1
        bar_orientation = 'vertical'
        linewidth = 0.8
        gridlabel_size = 5

        # Create a new product With the band to plot only
        _, width, height = get_name_width_height_from_nc(src)
        band_arr = read_pixels_from_nc(src, band_name, 0, 0, width, height, dtype=np.float64)
        band_arr[band_arr == 0] = np.nan

        # Count pixels with applicable values
        applicable_values = np.count_nonzero(~np.isnan(band_arr))
        log(env["General"]["log"], 'Applicable values are found in {} of {} pixels'
            .format(str(applicable_values), str(height * width)))
        if applicable_values == 0:
            log(env["General"]["log"], 'Image is empty, skipping...')
            return

        # read constituent band
        band_arr = band_arr.reshape(height, width)

        # load flag bands if requested
        masked_cloud_arr = None
        if cloud_layer:
            cloud_arr = read_pixels_from_nc(src, cloud_layer[0], 0, 0, width, height, dtype=np.int32)
            cloud_arr = cloud_arr.reshape(height, width)
            cloud_ind = np.where(cloud_arr == cloud_layer[1])
            cloud_arr[cloud_ind] = 100
            masked_cloud_arr = np.ma.masked_where(cloud_arr != 100, cloud_arr)

        masked_shadow_arr = None
        if shadow_layer:
            shadow_arr = read_pixels_from_nc(src, shadow_layer[0], 0, 0, width, height, dtype=np.int32)
            shadow_arr = shadow_arr.reshape(height, width)
            shadow_ind = np.where(shadow_arr == shadow_layer[1])
            shadow_arr[shadow_ind] = 100
            masked_shadow_arr = np.ma.masked_where(shadow_arr != 100, shadow_arr)

        masked_suspect_arr = None
        if suspect_layer:
            suspect_arr = read_pixels_from_nc(src, suspect_layer[0], 0, 0, width, height, dtype=np.int32)
            suspect_arr = suspect_arr.reshape(height, width)
            suspect_ind = np.where(suspect_arr == suspect_layer[1])
            suspect_arr[suspect_ind] = 100
            masked_suspect_arr = np.ma.masked_where(suspect_arr != 100, suspect_arr)

        if water_layer:
            water_arr = read_pixels_from_nc(src, water_layer[0], 0, 0, width, height, dtype=np.int32)
            water_arr = water_arr.reshape(height, width)
            land_arr = np.zeros(width * height, dtype=np.int32)
            land_arr = land_arr.reshape(height, width)
            land_ind = np.where(water_arr != water_layer[1])
            land_arr[land_ind] = 100
            band_arr = np.ma.masked_where(land_arr != 0, band_arr)

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
            min_lat, min_lon = get_lat_lon_from_x_y_from_nc(src, band_name, 0, height - 1)
            max_lat, max_lon = get_lat_lon_from_x_y_from_nc(src, band_name, width - 1, 0)

        # add map extent if the input product hasn't been cropped e.g. with a lake shapefile
        if crop_ext:
            lat_ext = (max_lat - min_lat) / 8
            lon_ext = (max_lon - min_lon) / 8
        else:
            lat_ext = 0
            lon_ext = 0

        lon_range = (max_lon + lon_ext) - (min_lon - lon_ext)
        lat_range = (max_lat + lat_ext) - (min_lat - lon_ext)
        aspect_ratio = lon_range / lat_range

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
        lat_center = round((min_lat + (max_lat - min_lat) / 2) / (decimal * 10)) * (decimal * 10)
        lon_center = round((min_lon + (max_lon - min_lon) / 2) / (decimal * 10)) * (decimal * 10)
        x_ticks = [lon_center]
        y_ticks = [lat_center]
        i = 0
        while max(x_ticks) <= max_lon or min(x_ticks) >= min_lon:
            i += 1
            x_ticks.extend((lon_center + (i * grid_dist), lon_center - (i * grid_dist)))
        x_ticks.sort()
        i = 0
        while max(y_ticks) <= max_lat or min(y_ticks) >= min_lat:
            i += 1
            y_ticks.extend((lat_center + (i * grid_dist), lat_center - (i * grid_dist)))
        y_ticks.sort()

        canvas_area = [[min_lon - lon_ext, min_lat - lat_ext], [max_lon + lon_ext, max_lat + lat_ext]]

        # Define colour scale
        title_str, legend_str, log_num = get_legend_str(band_name)
        if log_num:
            log(env["General"]["log"], 'Transforming log data...')
            band_arr = np.exp(band_arr)

        if ('hue' in title_str) and ('angle' in title_str):
            color_type = cm.get_cmap(name='viridis').copy()
            param_range = [20, 230]
            tick_format = '%.0f'
            ticks = [45, 90, 135, 180, 225]
        elif ('dominant' in title_str) and ('wavelength' in title_str):
            param_range = [400, 700]
            color_type = colscales.spectral_cie(wvl_min=param_range[0], wvl_max=param_range[1])
            tick_format = '%.0f'
            ticks = [400, 450, 500, 550, 600, 650, 700]
        elif 'Forel-Ule' in title_str:
            color_type = colscales.forel_ule()
            param_range = [0.5, 21.5]
            ticks = [i + 1 for i in range(21)]
            boundaries = [fu - 0.5 for fu in range(1, 23, 1)]  # [fu + 0.5 for fu in range(1, 21, 1)]
            norm = mpl.colors.BoundaryNorm(ticks, color_type)
            tick_format = '%.0f'
        elif 'Whiting' in title_str:
            color_type = cm.get_cmap(name='Reds').copy()
            param_range = [0.5, 1.5]
            ticks = False
        elif 'Secchi' in title_str:
            color_type = cm.get_cmap(name='viridis_r').copy()
            ticks = False
        else:
            color_type = cm.get_cmap(name='viridis').copy()
            ticks = False
        # color_type = colscales.rainbow_king()
        # color_type = colscales.red2blue()
        # color_type = cm.get_cmap(name='magma_r')

        color_type.set_bad(alpha=0)
        if not param_range:
            log(env["General"]["log"], 'No range provided. Estimating...')
            range_intervals = [2000, 1000, 500, 200, 100, 50, 40, 30, 20, 15,
                               10, 8, 6, 4, 2, 1, 0.5, 0.2, 0.1, 0.08, 0.06,
                               0.04, 0.02, 0.01, 0.008, 0.006, 0.004, 0.002,
                               0.001]
            for n_interval in range(2, len(range_intervals)):
                if np.nanpercentile(band_arr, 90) > range_intervals[n_interval]:
                    param_range = [0, range_intervals[n_interval - 2]]
                    break
                elif np.nanpercentile(band_arr, 90) < range_intervals[-1]:
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
                if lat_range < 50 and lon_range < 50:
                    log(env["General"]["log"],
                        '   larger image side is ' + str(round(max(lon_range, lat_range), 1)) + ' km, applying SRTM1')
                    source = srtm.SRTM1Source
                else:
                    log(env["General"]["log"],
                        '   larger image side is ' + str(round(max(lon_range, lat_range), 1)) + ' km, applying SRTM3')
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
        if basemap == "esri_shaded":
            class ShadedReliefESRI(maps.GoogleTiles):
                def _image_url(self, tile):
                    x, y, z = tile
                    url = ('https://server.arcgisonline.com/ArcGIS/rest/services/World_Shaded_Relief/MapServer/tile/{z}/{y}/{x}.jpg').format(z=z, y=y, x=x)
                    return url

            subplot_axes.add_image(ShadedReliefESRI(), 12)

        ##############################
        # ### both plot versions #####
        ##############################

        # Plot parameter
        # Fun fact: interpolation='none' causes interpolation if opened in OSX Preview:
        # https://stackoverflow.com/questions/54250441/pdf-python-plot-is-blurry-image-interpolation
        parameter = subplot_axes.imshow(band_arr, extent=[min_lon, max_lon, min_lat, max_lat],
                                        transform=ccrs.PlateCarree(), origin='upper', cmap=color_type,
                                        # interpolation='none',
                                        vmin=param_range[0], vmax=param_range[1], zorder=10)

        # Plot flags
        if cloud_layer:
            cloud_colmap = colscales.cloud_color()
            cloud_colmap.set_bad('w', 0)
            _ = plt.imshow(masked_cloud_arr, extent=[min_lon, max_lon, min_lat, max_lat],
                           transform=ccrs.PlateCarree(), origin='upper', cmap=cloud_colmap, interpolation='none',
                           zorder=20)

        if shadow_layer:
            shadow_colmap = colscales.shadow_color()
            shadow_colmap.set_bad('w', 0)
            _ = plt.imshow(masked_shadow_arr, extent=[min_lon, max_lon, min_lat, max_lat],
                           transform=ccrs.PlateCarree(), origin='upper', cmap=shadow_colmap, interpolation='none',
                           zorder=20)

        if suspect_layer:
            suspect_colmap = colscales.suspect_color()
            suspect_colmap.set_bad('w', 0)
            _ = plt.imshow(masked_suspect_arr, extent=[min_lon, max_lon, min_lat, max_lat],
                           transform=ccrs.PlateCarree(), origin='upper', cmap=suspect_colmap, interpolation='none',
                           zorder=20)

        # Add gridlines
        if grid:
            gridlines = subplot_axes.gridlines(draw_labels=True, linewidth=linewidth, color='black', alpha=1.0,
                                               linestyle=':', zorder=23)  # , n_steps=3)
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


def get_legend_str(layer_str):
    # Fluo products
    if layer_str in ['L_CHL']:
        legend_str = r'$\mathbf{[mg/m^3]}$'
        title_str = r'$\mathbf{L-Fluo\/CHL}$'
        log_num = False
    elif layer_str in ['L_FPH']:
        legend_str = r'$\mathbf{[mW\/m^{-2}\/sr^{-1}\/nm^{-1}]}$'
        title_str = r'$\mathbf{L-Fluo\/phytoplankton\/fluorescence}$'
        log_num = False
    elif layer_str in ['L_APD']:
        legend_str = r'$\mathbf{[mW\/m^{-2}\/sr^{-1}\/nm^{-1}]}$'
        title_str = r'$\mathbf{L-Fluo\/phytoplankton\/absorption}$'
        log_num = False

    # Acolite products
    elif 'TUR_Nechad2016' in layer_str:
        split_str = layer_str.split('_')
        legend_str = r'$\mathbf{[FNU]}$'
        title_str = r'$\mathbf{Acolite\/Nechad\/2016\/turbidity\/(' + split_str[-1] + r'\/nm)}$'
        log_num = False
    elif layer_str == 'TUR_Dogliotti2015':
        split_str = layer_str.split('_')
        legend_str = r'$\mathbf{[FNU]}$'
        title_str = r'$\mathbf{Acolite\/Dogliotti\/2015\/turbidity\/(' + split_str[-1] + r'\/nm)}$'
        log_num = False
    elif 'rhow' in layer_str and 'rhown' not in layer_str:
        split_str = layer_str.split('_')
        legend_str = r'$\mathbf{[dl]}$'
        title_str = r'$\mathbf{Acolite\/R_w(' + split_str[-1] + r'\/nm)}$'
        log_num = False
    elif layer_str == 'hue_angle':
        legend_str = r'$\mathbf{[°]}$'
        title_str = r'$\mathbf{Acolite\/hue\/angle}$'
        log_num = False
    elif layer_str == 'qaa_v6_Zeu_Lee':
        legend_str = r'$\mathbf{[m]}$'
        title_str = r'$\mathbf{Acolite\/QAA\/Secchi\/depth}$'
        log_num = False

    # C2RCC products
    elif 'rhow' in layer_str and 'rhown' not in layer_str:
        lstr = re.findall(r'\d*$', layer_str)[0]
        legend_str = r'$\mathbf{[dl]}$'
        title_str = r'$\mathbf{C2RCC\/R_w(' + lstr + r'\/nm)}$'
        log_num = False
    elif 'rhown' in layer_str:
        lstr = re.findall(r'\d*$', layer_str)[0]
        legend_str = r'$\mathbf{[dl]}$'
        title_str = r'$\mathbf{C2RCC\/R_{w,n}(' + lstr + r'\/nm)}$'
        log_num = False
    elif layer_str in ['kdmin']:
        legend_str = r'$\mathbf{[m^-1]}$'
        title_str = r'$\mathbf{C2RCC\/K_{d}}$'
        log_num = False
    elif layer_str in ['conc_tsm']:
        legend_str = r'$\mathbf{[g/m^3]}$'
        title_str = r'$\mathbf{C2RCC\/TSM}$'
        log_num = False
    elif layer_str in ['conc_chl']:
        legend_str = r'$\mathbf{[mg/m^3]}$'
        title_str = r'$\mathbf{C2RCC\/CHL}$'
        log_num = False

    # MPH products
    elif layer_str == 'chl':
        legend_str = r'$\mathbf{[mg/m^3]}$'
        title_str = r'$\mathbf{MPH\/CHL}$'
        log_num = False
    elif layer_str == 'mph':
        legend_str = r'$\mathbf{[dl]}$'
        title_str = r'$\mathbf{MPH}$'
        log_num = False

    # sen2cor products
    elif layer_str == 'ndvi':
        legend_str = r'$\mathbf{[dl}$'
        title_str = r'$\mathbf{NDVI}$'
        log_num = False
    elif layer_str == 'ndmi':
        legend_str = r'$\mathbf{NDMI\/[dl]}$'
        title_str = r'$\mathbf{NDMI}$'
        log_num = False
    elif layer_str == 'ndwi_gao':
        legend_str = r'$\mathbf{[dl]}$'
        title_str = r'$\mathbf{Gao\/NDWI}$'
        log_num = False
    elif layer_str == 'ndwi_mcfeeters':
        legend_str = r'$\mathbf{[dl]}$'
        title_str = r'$\mathbf{McFeeters\/NDWI}$'
        log_num = False

    # polymer products
    elif 'Rw' in layer_str:
        lstr = re.findall(r'\d{3}', layer_str)[0]
        legend_str = r'$\mathbf{[dl]}$'
        title_str = r'$\mathbf{Polymer\/\/R_w(' + lstr + ')}$'
        log_num = False
    elif layer_str == 'bbs':
        legend_str = r'$\mathbf{[m^{-1}]}$'
        title_str = r'$\mathbf{Polymer\/b_{b_{s}}}$'
        log_num = False
    elif layer_str == 'logchl':
        legend_str = r'$\mathbf{[mg/m^3]}$'
        title_str = r'$\mathbf{Polymer\/\/CHL}$'
        log_num = True
    elif layer_str == 'tsm_vantrepotte665':
        legend_str = r'$\mathbf{[g/m^3]}$'
        title_str = r'$\mathbf{Vantrepotte\/665\/nm\/TSM}$'
        log_num = False
    elif layer_str == 'tsm_zhang709':
        legend_str = r'$\mathbf{[g/m^3]}$'
        title_str = r'$\mathbf{Zhang\/709\/nm\/TSM}$'
        log_num = False
    elif layer_str == 'tsm_binding754':
        legend_str = r'$\mathbf{[g/m^3]}$'
        title_str = r'$\mathbf{Binding\/754\/nm\/TSM}$'
        log_num = False
    elif layer_str == 'chl_oc2':
        legend_str = r'$\mathbf{[mg/m^3]}$'
        title_str = r'$\mathbf{OC2\/CHL}$'
        log_num = False
    elif layer_str == 'chl_oc3':
        legend_str = r'$\mathbf{[mg/m^3]}$'
        title_str = r'$\mathbf{OC3\/CHL}$'
        log_num = False
    elif layer_str == 'chl_2band':
        legend_str = r'$\mathbf{[mg/m^3]}$'
        title_str = r'$\mathbf{2-band\/CHL}$'
        log_num = False
    elif layer_str == 'chl_gons':
        legend_str = r'$\mathbf{[mg/m^3]}$'
        title_str = r'$\mathbf{Gons\/CHL}$'
        log_num = False
    elif layer_str == 'chl_ndci':
        legend_str = r'$\mathbf{[dl]}$'
        title_str = r'$\mathbf{NDCI}$'
        log_num = False
    elif layer_str == 'area_bgr':
        legend_str = r'$\mathbf{[dl]}$'
        title_str = r'$\mathbf{BGR\/Area\/(Heine\/et\/al.,\/2017)}$'
        log_num = False
    elif layer_str == 'bgr_whit':
        legend_str = r'$\mathbf{[dl]}$'
        title_str = r'$\mathbf{Whiting\/area}$'
        log_num = False

    # QAA products
    elif layer_str.startswith('Z'):
        lstr = re.findall(r'\d{3}', layer_str)[0]
        legend_str = r'$\mathbf{[m]}$'
        title_str = r'$\mathbf{Secchi\/\/depth at ' + lstr + '}$'
        log_num = False
    elif layer_str == 'bbs':
        legend_str = r'$\mathbf{[m^{-1}]}$'
        title_str = r'$\mathbf{Polymer\/b_{b_{s}}}$'
        log_num = False

    # Forel-Ule products
    elif layer_str == 'forel_ule':
        legend_str = r'$\mathbf{[FU]}$'
        title_str = r'$\mathbf{Forel-Ule\/type}$'
        log_num = False
    elif layer_str == 'dominant_wavelength':
        legend_str = r'$\mathbf{[nm]}$'
        title_str = r'$\mathbf{dominant\/wavelength}$'
        log_num = False
    elif layer_str == 'hue_angle':
        legend_str = r'$\mathbf{[deg]}$'
        title_str = r'$\mathbf{hue\/angle}$'
        log_num = False

    # all other products
    else:
        legend_str = 'ND'
        title_str = layer_str
        log_num = False
    return title_str, legend_str, log_num
