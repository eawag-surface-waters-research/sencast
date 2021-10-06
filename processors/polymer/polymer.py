#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Polymer is an algorithm aimed at recovering the radiance scattered and absorbed by the oceanic waters (also called
Ocean Colour) from the signal measured by satellite sensors in the visible spectrum.

For an overview of the processor: https://www.hygeos.com/polymer
or for more details: https://forum.hygeos.com/viewforum.php?f=3
"""

import os
import subprocess
from datetime import datetime
from math import ceil, floor

import rasterio
from netCDF4 import Dataset
from pyproj import Transformer
from haversine import haversine

from polymer.ancillary_era5 import Ancillary_ERA5
from polymer.gsw import GSW
from polymer.level1_msi import Level1_MSI
from polymer.level1_olci import Level1_OLCI
from polymer.level1_landsat8 import Level1_OLI
from polymer.level2 import default_datasets
from polymer.main import run_atm_corr, Level2

from utils.auxil import log
from utils.product_fun import get_reproject_params_from_wkt, get_south_east_north_west_bound, generate_l8_angle_files, \
    get_lons_lats, get_sensing_date_from_product_name
import processors.polymer.vicarious.polymer_vicarious as polymer_vicarious

# Key of the params section for this processor
PARAMS_SECTION = "POLYMER"
# The name of the folder to which the output product will be saved
OUT_DIR = "L2POLY"
# A pattern for the name of the file to which the output product will be saved (completed with product name)
OUT_FILENAME = "L2POLY_L1P_reproj_{}_{}.nc"
# A pattern for name of the folder to which the quicklooks will be saved (completed with band name)
QL_DIR = "L2POLY-{}"
# A pattern for the name of the file to which the quicklooks will be saved (completed with product name and band name)
QL_FILENAME = "L2POLY_L1P_reproj_{}_{}.png"
# The name of the xml file for gpt
GPT_XML_FILENAME = "polymer_{}.xml"


def process(env, params, l1product_path, _, out_path):
    """This processor applies polymer to the source product and stores the result."""

    gpt, product_name = env['General']['gpt_path'], os.path.basename(l1product_path)
    date_str = get_sensing_date_from_product_name(product_name)
    sensor, resolution, wkt = params['General']['sensor'], params['General']['resolution'], params['General']['wkt']
    water_model, validexpression = params['POLYMER']['water_model'], params['POLYMER']['validexpression']
    vicar_version = params['POLYMER']['vicar_version']
    gsw_path, ancillary_path = env['GSW']['root_path'], env['CDS']['era5_path']
    os.makedirs(gsw_path, exist_ok=True)
    os.makedirs(ancillary_path, exist_ok=True)

    try:
        date = datetime.strptime(date_str, "%Y%m%d")
        lons, lats = get_lons_lats(wkt)
        coords = (max(lats) + min(lats)) / 2, (max(lons) + min(lons)) / 2
        ancillary = Ancillary_ERA5(directory=ancillary_path)
        ozone = round(ancillary.get("ozone", date)[coords])  # Test can retrieve parameters
        anc_name = "ERA5"
        log(env["General"]["log"], "Polymer collected ERA5 ancillary data.")
    except (Exception, ):
        ancillary = None
        anc_name = "NA"
        log(env["General"]["log"], "Polymer failed to collect ERA5 ancillary data.")

    output_file = os.path.join(out_path, OUT_DIR, OUT_FILENAME.format(anc_name, product_name))
    if os.path.isfile(output_file):
        if "synchronise" in params["General"].keys() and params['General']['synchronise'] == "false":
            log(env["General"]["log"], "Removing file: ${}".format(output_file))
            os.remove(output_file)
        else:
            log(env["General"]["log"], "Skipping POLYMER, target already exists: {}".format(OUT_FILENAME.format(anc_name, product_name)))
            return output_file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    if sensor == "MSI":
        log(env["General"]["log"], "Reading MSI Level 1 data...", indent=1)
        calib_gains = polymer_vicarious.msi_vicarious(vicar_version)
        granule_path = os.path.join(l1product_path, "GRANULE")
        msi_product_path = os.path.join(granule_path, os.listdir(granule_path)[0])
        ul, ur, lr, ll = get_corner_pixels_roi_msi(msi_product_path, wkt)
        sline, scol, eline, ecol = min(ul[0], ur[0]), min(ul[1], ur[1]), max(ll[0], lr[0]), max(ll[1], lr[1])
        # Normalize to correct resolution
        target_divisor = 60 / int(resolution)
        sline, scol, eline, ecol = [(i * 10 / int(resolution)) for i in [sline, scol, eline, ecol]]
        sline, scol = [int(floor(i / target_divisor) * target_divisor) for i in [sline, scol]]
        eline, ecol = [int(ceil(i / target_divisor) * target_divisor) for i in [eline, ecol]]
        gsw = GSW(directory=gsw_path)
        l1 = Level1_MSI(msi_product_path, sline=sline, eline=eline, scol=scol, ecol=ecol, landmask=gsw, ancillary=ancillary, resolution=resolution)
        additional_ds = ['sza']
    elif sensor == "OLCI":
        log(env["General"]["log"], "Reading OLCI L1 data...", indent=1)
        calib_gains = polymer_vicarious.olci_vicarious(vicar_version)
        ul, ur, lr, ll = get_corner_pixels_roi_olci(l1product_path, wkt)
        sline, scol, eline, ecol = min(ul[0], ur[0]), min(ul[1], ur[1]), max(ll[0], lr[0]), max(ll[1], lr[1])
        gsw = GSW(directory=gsw_path, agg=8)
        l1 = Level1_OLCI(l1product_path, sline=sline, eline=eline, scol=scol, ecol=ecol, landmask=gsw, ancillary=ancillary)
        additional_ds = ['vaa', 'vza', 'saa', 'sza']
    elif sensor == "OLI_TIRS":
        log(env["General"]["log"], "Reading OLI_TIRS data...", indent=1)
        if generate_l8_angle_files(env, l1product_path):
            raise RuntimeError("Could not create angle files for L8 product: {}".format(l1product_path))
        calib_gains = polymer_vicarious.oli_vicarious(vicar_version)
        ul, ur, lr, ll = get_corner_pixels_roi_oli(l1product_path, wkt)
        sline, scol, eline, ecol = min(ul[0], ur[0]), min(ul[1], ur[1]), max(ll[0], lr[0]), max(ll[1], lr[1])
        gsw = GSW(directory=gsw_path, agg=8)
        l1 = Level1_OLI(l1product_path, sline=sline, eline=eline, scol=scol, ecol=ecol, landmask=gsw, ancillary=ancillary)
        additional_ds = ['sza']
    else:
        raise RuntimeError("Unknown sensor for polymer: {}".format(sensor))

    poly_tmp_file = os.path.join(out_path, OUT_DIR, "_reproducibility",
                                 OUT_FILENAME.format(anc_name, product_name) + ".tmp")
    l2 = Level2(filename=poly_tmp_file, fmt='netcdf4', overwrite=True, datasets=default_datasets + additional_ds)
    os.makedirs(os.path.dirname(poly_tmp_file), exist_ok=True)
    log(env["General"]["log"], "Running atmospheric correction...", indent=1)
    run_atm_corr(l1, l2, water_model=water_model, calib=calib_gains)
    log(env["General"]["log"], "Atmospheric correction complete.", indent=1)

    gpt_xml_file = os.path.join(out_path, OUT_DIR, "_reproducibility", GPT_XML_FILENAME.format(sensor))
    if not os.path.isfile(gpt_xml_file):
        rewrite_xml(gpt_xml_file, sensor, validexpression, resolution, wkt)

    args = [gpt, gpt_xml_file, "-c", env['General']['gpt_cache_size'], "-e", "-SsourceFile={}".format(poly_tmp_file),
            "-PoutputFile={}".format(output_file)]
    log(env["General"]["log"], "Calling '{}'".format(args), indent=1)

    process = subprocess.Popen(args, stdout=subprocess.PIPE, universal_newlines=True)
    while True:
        output = process.stdout.readline()
        log(env["General"]["log"], output.strip(), indent=2)
        return_code = process.poll()
        if return_code is not None:
            if return_code != 0:
                raise RuntimeError("GPT Failed.")
            break

    return output_file


def rewrite_xml(gpt_xml_file, sensor, validexpression, resolution, wkt):
    with open(os.path.join(os.path.dirname(__file__), GPT_XML_FILENAME.format(sensor)), "r") as f:
        xml = f.read()

    reproject_params = get_reproject_params_from_wkt(wkt, resolution)
    xml = xml.replace("${wkt}", wkt)
    xml = xml.replace("${validPixelExpression}", validexpression)
    xml = xml.replace("${easting}", reproject_params['easting'])
    xml = xml.replace("${northing}", reproject_params['northing'])
    xml = xml.replace("${pixelSizeX}", reproject_params['pixelSizeX'])
    xml = xml.replace("${pixelSizeY}", reproject_params['pixelSizeY'])
    xml = xml.replace("${width}", reproject_params['width'])
    xml = xml.replace("${height}", reproject_params['height'])

    os.makedirs(os.path.dirname(gpt_xml_file), exist_ok=True)
    with open(gpt_xml_file, "w") as f:
        f.write(xml)


def get_corner_pixels_roi_msi(l1product_path, wkt):
    """ Get the uper left, upper right, lower right, and lower left pixel position of the wkt containing rectangle """

    south, east, north, west = get_south_east_north_west_bound(wkt)

    img_dirs = list(filter(lambda d: d.endswith("_TCI.jp2"), os.listdir(os.path.join(l1product_path, "IMG_DATA"))))
    l1product_path = os.path.join(l1product_path, "IMG_DATA", img_dirs[0])

    with rasterio.open(l1product_path) as dataset:
        h, w = dataset.height, dataset.width
        ul_pos = get_pixel_pos_msi(dataset, west, north)
        ur_pos = get_pixel_pos_msi(dataset, east, north)
        ll_pos = get_pixel_pos_msi(dataset, west, south)
        lr_pos = get_pixel_pos_msi(dataset, east, south)

    ul = [int(ul_pos[1]) if (0 <= ul_pos[1] < h) else 0, int(ul_pos[0]) if (0 <= ul_pos[0] < w) else 0]
    ur = [int(ur_pos[1]) if (0 <= ur_pos[1] < h) else 0, int(ur_pos[0]) if (0 <= ur_pos[0] < w) else w]
    ll = [int(ll_pos[1]) if (0 <= ll_pos[1] < h) else h, int(ll_pos[0]) if (0 <= ll_pos[0] < w) else 0]
    lr = [int(lr_pos[1]) if (0 <= lr_pos[1] < h) else h, int(lr_pos[0]) if (0 <= lr_pos[0] < w) else w]

    return ul, ur, lr, ll


def get_pixel_pos_msi(dataset, lon, lat):
    transformer = Transformer.from_crs("epsg:4326", dataset.crs)
    row, col = transformer.transform(lat, lon)
    x, y = dataset.index(row, col)
    return [-1, -1] if x < 0 or y < 0 else [x, y]


def get_corner_pixels_roi_olci(l1product_path, wkt):
    """ Get the uper left, upper right, lower right, and lower left pixel position of the wkt containing rectangle """

    with Dataset(os.path.join(l1product_path, "geo_coordinates.nc")) as nc:
        product_lons, product_lats = nc.variables['longitude'][:], nc.variables['latitude'][:]

    h, w = len(product_lons), len(product_lons[0])

    south, east, north, west = get_south_east_north_west_bound(wkt)
    ul_pos = get_pixel_pos(product_lons, product_lats, west, north)
    ur_pos = get_pixel_pos(product_lons, product_lats, east, north)
    ll_pos = get_pixel_pos(product_lons, product_lats, west, south)
    lr_pos = get_pixel_pos(product_lons, product_lats, east, south)

    ul = [int(ul_pos[0]) if (0 <= ul_pos[0] < h) else 0, int(ul_pos[1]) if (0 <= ul_pos[1] < w) else 0]
    ur = [int(ur_pos[0]) if (0 <= ur_pos[0] < h) else 0, int(ur_pos[1]) if (0 <= ur_pos[1] < w) else w]
    ll = [int(ll_pos[0]) if (0 <= ll_pos[0] < h) else h, int(ll_pos[1]) if (0 <= ll_pos[1] < w) else 0]
    lr = [int(lr_pos[0]) if (0 <= lr_pos[0] < h) else h, int(lr_pos[1]) if (0 <= lr_pos[1] < w) else w]

    return ul, ur, lr, ll


def get_pixel_pos(longitudes, latitudes, lon, lat, x=None, y=None, step=None):
    """
    Returns the coordinates of the pixel [x, y] which cover a certain geo location (lon/lat).
    :param longitudes: matrix representing the longitude of each pixel
    :param latitudes: matrix representing the latitude of every pixel
    :param lon: longitude of the geo location of interest
    :param lat: latitude of the geo location of interest
    :param x: starting point of the algorithm
    :param y: starting point of the algorithm
    :param step: starting step size of the algorithm
    :return: [-1, -1] if the geo location is not covered by this product
    """

    lons_height, lons_width = len(longitudes), len(longitudes[0])
    lats_height, lats_width = len(latitudes), len(latitudes[0])

    if lats_height != lons_height or lats_width != lons_width:
        raise RuntimeError("Provided latitudes and longitudes matrices do not have the same size!")

    if x is None:
        x = int(lons_width / 2)
    if y is None:
        y = int(lats_height / 2)
    if step is None:
        step = int(ceil(max(lons_width, lons_height) / 4))

    new_coords = [[x, y], [x - step, y - step], [x - step, y], [x - step, y + step], [x, y + step],
                  [x + step, y + step], [x + step, y], [x + step, y - step], [x, y - step]]
    distances = [haversine((lat, lon), (latitudes[new_x][new_y], longitudes[new_x][new_y])) for [new_x, new_y] in
                 new_coords]

    idx = distances.index(min(distances))

    if step == 1:
        if x <= 0 or x >= lats_width - 1 or y <= 0 or y >= lats_height - 1:
            return [-1, -1]
        return new_coords[idx]
    else:
        return get_pixel_pos(longitudes, latitudes, lon, lat, new_coords[idx][0], new_coords[idx][1], int(ceil(step / 2)))


def get_corner_pixels_roi_oli(l1product_path, wkt):
    """ Get the uper left, upper right, lower right, and lower left pixel position of the wkt containing rectangle """

    south, east, north, west = get_south_east_north_west_bound(wkt)

    product_name = os.path.basename(l1product_path)
    sample_file_path = os.path.join(l1product_path, "{}_BQA.TIF".format(product_name))

    with rasterio.open(sample_file_path) as dataset:
        h, w = dataset.height, dataset.width
        ul_pos = get_pixel_pos_oli(dataset, west, north)
        ur_pos = get_pixel_pos_oli(dataset, east, north)
        ll_pos = get_pixel_pos_oli(dataset, west, south)
        lr_pos = get_pixel_pos_oli(dataset, east, south)

    ul = [int(ul_pos[1]) if (0 <= ul_pos[1] < h) else 0, int(ul_pos[0]) if (0 <= ul_pos[0] < w) else 0]
    ur = [int(ur_pos[1]) if (0 <= ur_pos[1] < h) else 0, int(ur_pos[0]) if (0 <= ur_pos[0] < w) else w]
    ll = [int(ll_pos[1]) if (0 <= ll_pos[1] < h) else h, int(ll_pos[0]) if (0 <= ll_pos[0] < w) else 0]
    lr = [int(lr_pos[1]) if (0 <= lr_pos[1] < h) else h, int(lr_pos[0]) if (0 <= lr_pos[0] < w) else w]

    return ul, ur, lr, ll


def get_pixel_pos_oli(dataset, lon, lat):
    transformer = Transformer.from_crs("epsg:4326", dataset.crs)
    row, col = transformer.transform(lat, lon)
    x, y = dataset.index(row, col)
    return [-1, -1] if x < 0 or y < 0 else [x, y]
    
