import os
import re

from threading import Semaphore, Thread

from adapters import datalakes


def start_adapter_threads(env, params, product_paths, processing_threads):
    adapter_threads, semaphore = [], Semaphore(1)

    for product_path, processing_thread in zip(product_paths, processing_threads):
        adapter_threads.append(Thread(target=apply_adapters, args=(env, params, product_path, semaphore, processing_thread)))
        adapter_threads[-1].start()

    return adapter_threads


def apply_adapters(env, params, product_path, semaphore, processing_thread):
    processing_thread.join()

    with semaphore:
        date = re.findall(r"\d{8}T\d{6}", os.path.basename(product_path['l2c2rcc']))[0]

        if "datalakes" in params['General']['adapters'].split(","):
            datalakes.apply(env, params['General']['wkt'].split('.')[0], date, product_path['l2c2rcc'])
