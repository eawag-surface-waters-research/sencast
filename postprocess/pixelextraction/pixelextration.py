#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
from utils.auxil import load_environment, log
import subprocess

# The name of the xml file for gpt
GPT_XML_FILENAME = "pixelextraction.xml"


def pixelextration(files, coords, folder, env_file=None,  windowsize=1):
    env, env_file = load_environment(env_file)
    gpt = env['General']['gpt_path']
    gpt_xml_file = os.path.join(folder, GPT_XML_FILENAME)
    rewrite_xml(gpt_xml_file, files, folder, coords, windowsize)
    tmp_file = os.path.join(folder, "pixelextration.tmp")
    args = [gpt, gpt_xml_file, "-c", env['General']['gpt_cache_size']]
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


def rewrite_xml(gpt_xml_file, files, folder, coords, windowsize):
    with open(os.path.join(os.path.dirname(__file__), GPT_XML_FILENAME), "r") as f:
        xml = f.read()

    coords_arr = []
    for coord in coords:
        coords_arr.append("<coordinate><name>{}</name><latitude>{}</latitude><longitude>{}</longitude><originalValues/><id>0</id></coordinate>".format(coord["name"], coord["lat"], coord["lng"]))

    xml = xml.replace("${sourceproductpaths}", ",".join(files))
    xml = xml.replace("${coordinates}", "".join(coords_arr))
    xml = xml.replace("${outputdir}", folder)
    xml = xml.replace("${windowsize)", str(windowsize))

    os.makedirs(os.path.dirname(gpt_xml_file), exist_ok=True)
    with open(gpt_xml_file, "w") as f:
        f.write(xml)

