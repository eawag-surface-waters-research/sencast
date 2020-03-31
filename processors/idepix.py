import os
import subprocess

from haversine import haversine
from snappy import WKTReader, ProductIO

from packages import auxil
from packages.ql_mapping import plot_pic

# The name of the folder to which the output product will be saved
OUT_DIR = "L1P"
# A pattern for the name of the file to which the output product will be saved (completed with product name)
FILENAME = "merge_reproj_L1P_subset_{}.nc"
# A pattern for the name of the file to which the output product will be saved (completed with product name)
FILENAME_2 = "L1P_reproj_{}.nc"
# A pattern for name of the folder to which the quicklooks will be saved (completed with band name)
QL_OUT_DIR = "L1P-{}"
# A pattern for the name of the file to which the quicklooks will be saved (completed with product name and band name)
QL_FILENAME = "reproj_L1P_subset_{}_{}.png"


def process(gpt, gpt_xml_path, wkt_file, source, product_name, out_path, sensor, resolution, params):
    """ This processor applies subset, idepix, merge and reprojection to the source product and stores the result.
    It returns the location of the output product. """

    print("Applying IDEPIX...")

    target = os.path.join(out_path, OUT_DIR, FILENAME.format(product_name))
    target_2 = os.path.join(out_path, OUT_DIR, FILENAME_2.format(product_name))
    if os.path.isfile(target) and os.path.isfile(target_2):
        print("Skipping IDEPIX, targets already exist: {}, {}".format(os.path.basename(target), os.path.basename(target_2)))
        return target, target_2
    os.makedirs(os.path.dirname(target), exist_ok=True)
    os.makedirs(os.path.dirname(target_2), exist_ok=True)

    gpt_xml_file, gpt_xml_file_2 = rewrite_xml(gpt_xml_path, out_path, wkt_file, sensor, resolution)

    args = [gpt, gpt_xml_file, "-SsourceProduct={}".format(source), "-PtargetProduct={}".format(target)]
    subprocess.call(args)

    args_2 = [gpt, gpt_xml_file_2, "-SsourceProduct={}".format(source), "-PtargetProduct={}".format(target_2)]
    subprocess.call(args_2)

    rgb_bands = params['rgb_bands'].split(",")
    fc_bands = params['fc_bands'].split(",")
    create_quicklooks(out_path, product_name, wkt_file, sensor, rgb_bands, fc_bands)

    return target, target_2


def rewrite_xml(gpt_xml_path, out_path, wkt_file, sensor, resolution):
    with open(os.path.join(gpt_xml_path, "idepix.xml"), "r") as f:
        xml = f.read()
    reproject_params = create_reproject_parameters_from_wkt(wkt_file, resolution)
    xml = xml.replace("${idepixOperator}", "Idepix.Olci" if sensor == "OLCI" else "Idepix.S2")
    xml = xml.replace("${wkt}", auxil.load_wkt(wkt_file))
    xml = xml.replace("${easting}", reproject_params['easting'])
    xml = xml.replace("${northing}", reproject_params['northing'])
    xml = xml.replace("${pixelSizeX}", reproject_params['pixelSizeX'])
    xml = xml.replace("${pixelSizeY}", reproject_params['pixelSizeY'])
    xml = xml.replace("${width}", reproject_params['width'])
    xml = xml.replace("${height}", reproject_params['height'])
    gpt_xml_file = os.path.join(out_path, "idepix.xml")
    with open(gpt_xml_file, "wb") as f:
        f.truncate()
        f.write(xml.encode())

    with open(os.path.join(gpt_xml_path, "idepix2.xml"), "r") as f:
        xml_2 = f.read()
    reproject_params = create_reproject_parameters_from_wkt(wkt_file, resolution)
    xml_2 = xml_2.replace("${idepixOperator}", "Idepix.Olci" if sensor == "OLCI" else "Idepix.S2")
    xml_2 = xml_2.replace("${wkt}", auxil.load_wkt(wkt_file))
    xml_2 = xml_2.replace("${easting}", reproject_params['easting'])
    xml_2 = xml_2.replace("${northing}", reproject_params['northing'])
    xml_2 = xml_2.replace("${pixelSizeX}", reproject_params['pixelSizeX'])
    xml_2 = xml_2.replace("${pixelSizeY}", reproject_params['pixelSizeY'])
    xml_2 = xml_2.replace("${width}", reproject_params['width'])
    xml_2 = xml_2.replace("${height}", reproject_params['height'])
    gpt_xml_file_2 = os.path.join(out_path, "idepix2.xml")
    with open(gpt_xml_file_2, "wb") as f:
        f.truncate()
        f.write(xml_2.encode())

    return gpt_xml_file, gpt_xml_file_2


def create_reproject_parameters_from_wkt(wkt_file, resolution):
    perimeter = WKTReader().read(auxil.load_wkt(wkt_file))
    lats = [coordinate.y for coordinate in perimeter.getCoordinates()]
    lons = [coordinate.x for coordinate in perimeter.getCoordinates()]
    x_dist = haversine((min(lats), min(lons)), (min(lats), max(lons)))
    y_dist = haversine((min(lats), min(lons)), (max(lats), min(lons)))
    x_pix = int(round(x_dist / (int(resolution) / 1000)))
    y_pix = int(round(y_dist / (int(resolution) / 1000)))
    x_pixsize = (max(lons) - min(lons)) / x_pix
    y_pixsize = (max(lats) - min(lats)) / y_pix

    return {'easting': str(min(lons)), 'northing': str(max(lats)), 'pixelSizeX': str(x_pixsize),
            'pixelSizeY': str(y_pixsize), 'width': str(x_pix), 'height': str(y_pix)}


def create_quicklooks(out_path, product_name, wkt_file, sensor, rgb_bands, fc_bands):
    print("Creating quicklooks for IDEPIX")
    if sensor == "OLCI":
        rgb_bands = [bn.replace('radiance', 'reflectance') for bn in rgb_bands]
        fc_bands = [bn.replace('radiance', 'reflectance') for bn in fc_bands]

    product = ProductIO.readProduct(os.path.join(out_path, OUT_DIR, FILENAME.format(product_name)))
    ql_file = os.path.join(out_path, QL_OUT_DIR.format("rgb"), QL_FILENAME.format(product_name, "rgb"))
    os.makedirs(os.path.dirname(ql_file), exist_ok=True)
    plot_pic(product, ql_file, rgb_layers=rgb_bands, grid=True, max_val=0.16, perimeter_file=wkt_file)
    ql_file = os.path.join(out_path, QL_OUT_DIR.format("fc"), QL_FILENAME.format(product_name, "fc"))
    os.makedirs(os.path.dirname(ql_file), exist_ok=True)
    plot_pic(product, ql_file, rgb_layers=fc_bands, grid=True, max_val=0.3, perimeter_file=wkt_file)
    product.closeIO()
