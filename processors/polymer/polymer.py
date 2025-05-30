#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Polymer is an algorithm aimed at recovering the radiance scattered and absorbed by the oceanic waters (also called
Ocean Colour) from the signal measured by satellite sensors in the visible spectrum.

For an overview of the processor: https://www.hygeos.com/polymer
or for more details: https://forum.hygeos.com/viewforum.php?f=3
"""
import math
import os
import re
from datetime import datetime
from math import ceil, floor
from osgeo import gdal, osr
from netCDF4 import Dataset
from pyproj import Transformer

from polymer.ancillary_era5 import Ancillary_ERA5
from polymer.ancillary import Ancillary_NASA
from polymer.gsw import GSW
from polymer.level1_msi import Level1_MSI
from polymer.level1_olci import Level1_OLCI
from polymer.level1_landsat8 import Level1_OLI
from polymer.level2 import default_datasets, Level2
from polymer.main import run_atm_corr
from pyhdf.error import HDF4Error

from utils.auxil import log, gpt_subprocess
from utils.product_fun import get_reproject_params_from_wkt, get_south_east_north_west_bound, generate_l8_angle_files, \
    get_lons_lats, get_sensing_date_from_product_name, get_pixel_pos, get_reproject_params_from_nc, get_s2_tile_name_from_product_name
import processors.polymer.vicarious.polymer_vicarious as polymer_vicarious

# Key of the params section for this processor
PARAMS_SECTION = "POLYMER"
# The name of the folder to which the output product will be saved
OUT_DIR = "L2POLY"
# A pattern for the name of the file to which the output product will be saved (completed with product name)
OUT_FILENAME = "L2POLY_reproj_{}_{}.nc"
# A pattern for name of the folder to which the quicklooks will be saved (completed with band name)
QL_DIR = "L2POLY-{}"
# A pattern for the name of the file to which the quicklooks will be saved (completed with product name and band name)
QL_FILENAME = "L2POLY_reproj_{}_{}.png"
# The name of the xml file for gpt
GPT_XML_FILENAME = "polymer_{}.xml"
# Default number of attempts for the GPT
DEFAULT_ATTEMPTS = 1
# Default timeout for the GPT (doesn't apply to last attempt) in seconds
DEFAULT_TIMEOUT = False


def process(env, params, l1product_path, _, out_path):
    """This processor applies polymer to the source product and stores the result."""

    gpt, product_name = env['General']['gpt_path'], os.path.basename(l1product_path)
    date_str = get_sensing_date_from_product_name(product_name)
    sensor, resolution, wkt = params['General']['sensor'], params['General']['resolution'], params['General']['wkt']
    water_model, validexpression = params['POLYMER']['water_model'], params['POLYMER']['validexpression']
    vicar_version = params['POLYMER']['vicar_version']
    gsw_path = env['GSW']['root_path']
    os.makedirs(gsw_path, exist_ok=True)

    if "ancillary" in params['POLYMER'] and params['POLYMER']['ancillary'] not in ["NASA", "ERA5"]:
        ancillary = None
        anc_name = "NA"
        log(env["General"]["log"], "Polymer not using ancillary data.", indent=1)
    else:

        if params['POLYMER']['ancillary'] == "NASA":
            ancillary = Ancillary_NASA(directory=env['EARTHDATA']['anc_path'])
            anc_name = "NASA"
        else:
            ancillary = Ancillary_ERA5(directory=env['CDS']['anc_path'])
            anc_name = "ERA5"
        log(env["General"]["log"], "Polymer using {} ancillary data.".format(anc_name), indent=1)
        try:
            # Test the retrieval of parameters
            date = datetime.strptime(date_str, "%Y%m%d")
            lons, lats = get_lons_lats(wkt)
            coords = (max(lats) + min(lats)) / 2, (max(lons) + min(lons)) / 2
            ozone = round(ancillary.get("ozone", date)[coords])
            log(env["General"]["log"], "Polymer collected {} ancillary data.".format(anc_name), indent=1)
        except HDF4Error as he:
            print(he)
            ancillary = None
            anc_name = "NA"
            os.makedirs("ANCILLARY/METEO", exist_ok=True)
            log(env["General"]["log"],
                "Polymer failed to read ancillary file. HDF4 ERROR.", indent=1)
        except Exception as e:
            print(e)
            ancillary = None
            anc_name = "NA"
            os.makedirs("ANCILLARY/METEO", exist_ok=True)
            log(env["General"]["log"], "Polymer failed to collect ancillary data. If using NASA data ensure authentication is setup according to: https://wiki.earthdata.nasa.gov/display/EL/How+To+Access+Data+With+cURL+And+Wget", indent=1)

    output_file = os.path.join(out_path, OUT_DIR, OUT_FILENAME.format(anc_name, product_name))
    if os.path.isfile(output_file):
        if "overwrite" in params["General"].keys() and params['General']['overwrite'] == "true":
            log(env["General"]["log"], "Removing file: ${}".format(output_file), indent=1)
            os.remove(output_file)
        else:
            log(env["General"]["log"], "Skipping POLYMER, target already exists: {}".format(OUT_FILENAME.format(anc_name, product_name)), indent=1)
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
        l1 = Level1_MSI(msi_product_path, sline=sline, eline=eline, scol=scol, ecol=ecol, landmask=gsw, ancillary=ancillary, resolution=resolution)#, altitude=altitude)
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
                                 OUT_FILENAME.format(anc_name, product_name).replace("reproj", "unproj"))
    l2 = Level2(filename=poly_tmp_file, fmt='netcdf4', overwrite=True, datasets=default_datasets + additional_ds)
    os.makedirs(os.path.dirname(poly_tmp_file), exist_ok=True)
    log(env["General"]["log"], "Running atmospheric correction...", indent=1)
    run_atm_corr(l1, l2, water_model=water_model, calib=calib_gains)
    log(env["General"]["log"], "Atmospheric correction complete.", indent=1)

    gpt_xml_file = os.path.join(out_path, OUT_DIR, "_reproducibility", GPT_XML_FILENAME.format(sensor))

    tiles = True if "tiles" in params['General'] and params['General']["tiles"] != "" else False
    if tiles:
        gpt_xml_file = gpt_xml_file.replace(".xml", "_{}.xml".format(get_s2_tile_name_from_product_name(l1product_path)))

    if not os.path.isfile(gpt_xml_file):
        rewrite_xml(gpt_xml_file, sensor, validexpression, resolution, wkt, poly_tmp_file, tiles)

    args = [gpt, gpt_xml_file, "-c", env['General']['gpt_cache_size'], "-e", "-SsourceFile={}".format(poly_tmp_file),
            "-PoutputFile={}".format(output_file)]

    if PARAMS_SECTION in params and "attempts" in params[PARAMS_SECTION]:
        attempts = int(params[PARAMS_SECTION]["attempts"])
    else:
        attempts = DEFAULT_ATTEMPTS

    if PARAMS_SECTION in params and "timeout" in params[PARAMS_SECTION]:
        timeout = int(params[PARAMS_SECTION]["timeout"])
    else:
        timeout = DEFAULT_TIMEOUT

    if gpt_subprocess(args, env["General"]["log"], attempts=attempts, timeout=timeout):
        return output_file
    else:
        if os.path.exists(output_file):
            os.remove(output_file)
            log(env["General"]["log"], "Removed corrupted output file.", indent=2)
        raise RuntimeError("GPT Failed.")


def rewrite_xml(gpt_xml_file, sensor, validexpression, resolution, wkt, source_file, tiles):
    with open(os.path.join(os.path.dirname(__file__), GPT_XML_FILENAME.format(sensor)), "r") as f:
        xml = f.read()
    if tiles:
        reproject_params = get_reproject_params_from_nc(source_file, resolution)
    else:
        reproject_params = get_reproject_params_from_wkt(wkt, resolution)
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

    metadata_path = os.path.join(l1product_path, "MTD_TL.xml")
    crs = get_horizontal_cs_code(metadata_path)

    img_dirs = list(filter(lambda d: d.endswith("_TCI.jp2"), os.listdir(os.path.join(l1product_path, "IMG_DATA"))))
    l1product_path = os.path.join(l1product_path, "IMG_DATA", img_dirs[0])

    dataset = gdal.Open(l1product_path)
    w, h = dataset.RasterXSize, dataset.RasterYSize
    ul_pos = get_pixel_pos_gdal(dataset, west, north, crs)
    ur_pos = get_pixel_pos_gdal(dataset, east, north, crs)
    ll_pos = get_pixel_pos_gdal(dataset, west, south, crs)
    lr_pos = get_pixel_pos_gdal(dataset, east, south, crs)
    dataset = None

    ul = [int(ul_pos[1]) if (0 <= ul_pos[1] < h) else 0, int(ul_pos[0]) if (0 <= ul_pos[0] < w) else 0]
    ur = [int(ur_pos[1]) if (0 <= ur_pos[1] < h) else 0, int(ur_pos[0]) if (0 <= ur_pos[0] < w) else w]
    ll = [int(ll_pos[1]) if (0 <= ll_pos[1] < h) else h, int(ll_pos[0]) if (0 <= ll_pos[0] < w) else 0]
    lr = [int(lr_pos[1]) if (0 <= lr_pos[1] < h) else h, int(lr_pos[0]) if (0 <= lr_pos[0] < w) else w]

    return ul, ur, lr, ll


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


def get_corner_pixels_roi_oli(l1product_path, wkt):
    """ Get the uper left, upper right, lower right, and lower left pixel position of the wkt containing rectangle """

    south, east, north, west = get_south_east_north_west_bound(wkt)

    product_name = os.path.basename(l1product_path)
    sample_file_path = os.path.join(l1product_path, "{}_BQA.TIF".format(product_name))

    dataset = gdal.Open(sample_file_path)
    w, h = dataset.RasterXSize, dataset.RasterYSize
    ul_pos = get_pixel_pos_gdal(dataset, west, north, False)
    ur_pos = get_pixel_pos_gdal(dataset, east, north, False)
    ll_pos = get_pixel_pos_gdal(dataset, west, south, False)
    lr_pos = get_pixel_pos_gdal(dataset, east, south, False)
    dataset = None

    ul = [int(ul_pos[1]) if (0 <= ul_pos[1] < h) else 0, int(ul_pos[0]) if (0 <= ul_pos[0] < w) else 0]
    ur = [int(ur_pos[1]) if (0 <= ur_pos[1] < h) else 0, int(ur_pos[0]) if (0 <= ur_pos[0] < w) else w]
    ll = [int(ll_pos[1]) if (0 <= ll_pos[1] < h) else h, int(ll_pos[0]) if (0 <= ll_pos[0] < w) else 0]
    lr = [int(lr_pos[1]) if (0 <= lr_pos[1] < h) else h, int(lr_pos[0]) if (0 <= lr_pos[0] < w) else w]

    return ul, ur, lr, ll


def get_pixel_pos_gdal(dataset, lon, lat, crs):
    w, h = dataset.RasterXSize, dataset.RasterYSize
    if isinstance(crs, bool):
        wkt = dataset.GetProjection()
        spatial_ref = osr.SpatialReference()
        spatial_ref.ImportFromWkt(wkt)
        epsg = spatial_ref.GetAttrValue('AUTHORITY', 1)
        if epsg:
            crs = f"EPSG:{epsg}"
        else:
            raise ValueError("Failed to parse projection")
    transformer = Transformer.from_crs("epsg:4326", crs)
    x, y = transformer.transform(lat, lon)
    geo_transform = dataset.GetGeoTransform()
    inv_geo_transform = gdal.InvGeoTransform(geo_transform)
    col, row = gdal.ApplyGeoTransform(inv_geo_transform, x, y)
    col, row = math.floor(col), math.floor(row)
    xx = col if 0 < col <= w else -1
    yy = row if 0 < row <= h else -1
    return [xx, yy]


def get_horizontal_cs_code(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            xml_content = file.read()
        match = re.search(r'<HORIZONTAL_CS_CODE>(.*?)</HORIZONTAL_CS_CODE>', xml_content)
        return match.group(1) if match else False
    except Exception as e:
        return False
