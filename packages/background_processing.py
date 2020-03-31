import os
import sys

from snappy import ProductIO
from threading import Semaphore, Thread

from processors import idepix, c2rcc, mph, polymer


def start_processing_threads(env, params, product_paths_available, product_paths_to_download, download_threads, max_parallel_processing=1):
    # initialize output paths, create them if they do not exist yet
    name, wkt = params['General']['name'], params['General']['wkt'].split(".")[0]
    start, end = params['General']['start'][:10], params['General']['end'][:10]
    l2_path = env['DIAS']['l2_path'].format(params['General']['sensor'])
    out_path = os.path.join(l2_path, "{}_{}_{}_{}".format(name, wkt, start, end))
    os.makedirs(out_path, exist_ok=True)

    processing_threads = []
    semaphore = Semaphore(max_parallel_processing)

    # creating and starting processes to process already available products
    for product_path in product_paths_available:
        processing_threads.append(Thread(target=do_processing, args=(env, params, product_path, out_path, semaphore)))
        processing_threads[-1].start()

    # creating and starting threads to process after products which are being downloaded
    for product_path, download_thread in zip(product_paths_to_download, download_threads):
        processing_threads.append(Thread(target=do_processing, args=(env, params, product_path, out_path, semaphore, download_thread)))
        processing_threads[-1].start()

    return processing_threads


def do_processing(env, params, product_path, out_path, semaphore, download_thread=None):
    if download_thread:
        download_thread.join()

    with semaphore:
        product = ProductIO.readProduct(product_path)

        # FOR S3 MAKE SURE THE NON-DEFAULT S3TBX SETTING IS SELECTED IN THE SNAP PREFERENCES!
        if params['General']['sensor'] == 'OLCI' and 'PixelGeoCoding2' not in str(product.getSceneGeoCoding()):
            sys.exit('The S3 product was read without pixelwise geocoding, please check the preference settings of the S3TBX!')

        product_name = os.path.basename(product_path)
        gpt, gpt_xml_path = env['General']['gpt_path'], env['General']['gpt_xml_path']
        wkt_file = os.path.join(env['DIAS']['wkt_path'], params['General']['wkt'])
        sensor, resolution = params['General']['sensor'], params['General']['resolution']

        if "IDEPIX" == params['General']['preprocessor']:
            l1m, l1p = idepix.process(gpt, gpt_xml_path, wkt_file, product_path, product_name, out_path, sensor, resolution, params['IDEPIX'])

        if "C2RCC" in params['General']['processors'].split(","):
            c2rcc.process(gpt, gpt_xml_path, wkt_file, l1m, product_name, out_path, sensor, params['C2RCC'])

        if "POLYMER" in params['General']['processors'].split(","):
            gsw_path = os.path.join(env['DIAS']['dias_path'], "data_landmask_gsw")
            polymer.process(gpt, gpt_xml_path, wkt_file, product_path, l1p, product_name, out_path, sensor, resolution, params['POLY'], gsw_path)

        if "MPH" in params['General']['processors'].split(","):
            mph.process(gpt, gpt_xml_path, wkt_file, l1m, product_name, out_path, sensor, params['MPH'])
