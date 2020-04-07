import os

from snappy import ProductIO
from threading import Semaphore, Thread

from processors import idepix, c2rcc, mph, polymer


def start_processing_threads(env, params, wkt, out_path, product_paths, download_threads, max_parallel_processing=1):
    l2_product_paths, processing_threads, semaphore = [], [], Semaphore(max_parallel_processing)

    for product_path, download_thread in zip(product_paths, download_threads):
        l2_product_paths.append({})
        processing_threads.append(Thread(target=do_processing, args=(env, params, wkt, product_path, out_path, l2_product_paths[-1], semaphore, download_thread)))
        processing_threads[-1].start()

    return l2_product_paths, processing_threads


def do_processing(env, params, wkt, product_path, out_path, l2_product_path, semaphore, download_thread):
    download_thread.join()

    with semaphore:
        product = ProductIO.readProduct(product_path)

        # FOR S3 MAKE SURE THE NON-DEFAULT S3TBX SETTING IS SELECTED IN THE SNAP PREFERENCES!
        if params['General']['sensor'] == 'OLCI' and 'PixelGeoCoding2' not in str(product.getSceneGeoCoding()):
            raise RuntimeError("The S3 product was read without pixelwise geocoding, please check the preference settings of the S3TBX!")

        product_name = os.path.basename(product_path)
        gpt, gpt_xml_path = env['General']['gpt_path'], env['General']['gpt_xml_path']
        sensor, resolution = params['General']['sensor'], params['General']['resolution']

        if "IDEPIX" in params['General']['preprocessor'].split(","):
            l1m, l1p = idepix.process(gpt, gpt_xml_path, wkt, product_path, product_name, out_path, sensor, resolution, params['IDEPIX'])
            l2_product_path['l1m'], l2_product_path['l1p'] = l1m, l1p

        if "C2RCC" in params['General']['processors'].split(","):
            l2c2rcc = c2rcc.process(gpt, gpt_xml_path, wkt, l1m, product_name, out_path, sensor, params['C2RCC'])
            l2_product_path['l2c2rcc'] = l2c2rcc

        if "POLYMER" in params['General']['processors'].split(","):
            gsw_path = os.path.join(env['DIAS']['dias_path'], "data_landmask_gsw")
            l2poly = polymer.process(gpt, gpt_xml_path, wkt, product_path, l1p, product_name, out_path, sensor, resolution, params['POLY'], gsw_path)
            l2_product_path['l2poly'] = l2poly

        if "MPH" in params['General']['processors'].split(","):
            l2mph = mph.process(gpt, gpt_xml_path, wkt, l1m, product_name, out_path, sensor, params['MPH'])
            l2_product_path['l2mph'] = l2mph
