import os
import subprocess

from polymer.main import run_atm_corr, Level1, Level2
from polymer.level1_msi import Level1_MSI
from polymer.gsw import GSW
from polymer.level2 import default_datasets
from snappy import ProductIO

from packages.product_fun import get_corner_pixels_ROI
from packages.ql_mapping import plot_map

# The name of the folder to which the output product will be saved
OUT_DIR = "L2POLY"
# A pattern for the name of the file to which the output product will be saved (completed with product name)
FILENAME = "L2POLY_L1P_reproj_{}.nc"
# A pattern for name of the folder to which the quicklooks will be saved (completed with band name)
QL_OUT_DIR = "L2POLY-{}"
# A pattern for the name of the file to which the quicklooks will be saved (completed with product name and band name)
QL_FILENAME = "L2POLY_L1P_reproj_{}_{}.png"


def process(gpt, gpt_xml_path, wkt_file, product_path, l1p, product_name, out_path, sensor, resolution, params, gsw_path):
    """ This processor applies polymer to the source product and stores the result. """

    print("Applying POLYMER...")

    target = os.path.join(out_path, OUT_DIR, FILENAME.format(product_name))
    if os.path.isfile(target):
        print("Skipping POLYMER, target already exists: {}".format(FILENAME.format(product_name)))
        return target
    os.makedirs(os.path.dirname(target), exist_ok=True)

    UL, UR, LR, LL = get_corner_pixels_ROI(ProductIO.readProduct(product_path), wkt_file)
    sline = min(UL[0], UR[0])
    eline = max(LL[0], LR[0])
    scol = min(UL[1], UR[1])
    ecol = max(LL[1], LR[1])

    poly_tmp_file = "{}.tmp".format(target)
    if sensor == "MSI":
        gsw = GSW(directory=gsw_path)
        l1 = Level1_MSI(product_path, sline=sline, scol=scol, eline=eline, ecol=ecol, landmask=gsw, resolution=resolution)
        l2 = Level2(filename=poly_tmp_file, fmt='netcdf4', overwrite=True, datasets=default_datasets + ['sza'])
        run_atm_corr(l1, l2)
    else:
        gsw = GSW(directory=gsw_path, agg=8)
        l1 = Level1(product_path, sline=sline, scol=scol, eline=eline, ecol=ecol, landmask=gsw)
        l2 = Level2(filename=poly_tmp_file, fmt='netcdf4', overwrite=True, datasets=default_datasets + ['vaa', 'vza', 'saa', 'sza'])
        run_atm_corr(l1, l2)

    gpt_xml_file = os.path.join(out_path, "polymer.xml")
    rewrite_xml(gpt_xml_path, gpt_xml_file)

    args = [gpt, gpt_xml_file,
            "-SmasterProduct={}".format(l1p),
            "-SslaveProduct={}".format(poly_tmp_file),
            "-PtargetProduct={}".format(target)]
    subprocess.call(args)

    os.remove(poly_tmp_file)

    create_quicklooks(out_path, product_name, wkt_file, params['bands'].split(","), params['bandmaxs'].split(","))


def rewrite_xml(gpt_xml_path, gpt_xml_file):
    with open(os.path.join(gpt_xml_path, "polymer.xml"), "r") as f:
        xml = f.read()

    with open(gpt_xml_file, "wb") as f:
        f.write(xml.encode())


def create_quicklooks(out_path, product_name, wkt_file, bands, bandmaxs):
    print("Creating quicklooks for POLYMER for bands: {}".format(bands))
    product = ProductIO.readProduct(os.path.join(out_path, OUT_DIR, FILENAME.format(product_name)))
    for band, bandmax in zip(bands, bandmaxs):
        if int(bandmax) == 0:
            bandmax = False
        else:
            bandmax = range(0, int(bandmax))
        ql_file = os.path.join(out_path, QL_OUT_DIR.format(band), QL_FILENAME.format(product_name, band))
        os.makedirs(os.path.dirname(ql_file), exist_ok=True)
        plot_map(product, ql_file, band, basemap="srtm_hillshade", grid=True, perimeter_file=wkt_file, param_range=bandmax)
        print("Plot for band {} finished.".format(band))
    product.closeIO()
