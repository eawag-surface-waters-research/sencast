#! /usr/bin/env python
# -*- coding: utf-8 -*-

import configparser
import getpass
import os
import socket

project_path = os.path.dirname(__file__)


def init_hindcast(env_file, params_file):
    # load environment and params from file
    env, env_file = load_environment(env_file)
    params, params_file = load_params(params_file, env['General']['params_path'])

    # create output path, if it does not exist yet
    wkt_name = params['General']['wkt_name']
    kwargs = {
        'params_name': os.path.splitext(os.path.basename(params_file))[0],
        'wkt_name': wkt_name,
        'start': params['General']['start'][:10],
        'end': params['General']['end'][:10]

    }
    out_path = os.path.join(env['General']['out_path'].format(**kwargs))

    if os.path.isdir(out_path) and os.listdir(out_path) and os.path.isfile(os.path.join(out_path, os.path.basename(params_file))):
        print("Output folder for this run already exists.")
        if "synchronise" in params["General"].keys() and params['General']['synchronise'] == "false":
            print("Overwriting existing run")
        else:
            print("Reading params from output folder to ensure comparable results.")
            params, params_file = load_params(os.path.join(out_path, os.path.basename(params_file)))
        if not params['General']['wkt']:
            params['General']['wkt'], _ = load_wkt("{}.wkt".format(wkt_name), env['General']['wkt_path'])
    else:
        # copy params file to new output folder
        os.makedirs(out_path, exist_ok=True)
        if not params['General']['wkt']:
            params['General']['wkt'], _ = load_wkt("{}.wkt".format(wkt_name), env['General']['wkt_path'])
        with open(os.path.join(out_path, os.path.basename(params_file)), "w") as f:
            params.write(f)

    if env.has_section("CDS"):
        os.makedirs(env['CDS']['era5_path'], exist_ok=True)
    if env.has_section("EARTHDATA"):
        os.makedirs(env['EARTHDATA']['root_path'], exist_ok=True)
    if env.has_section("GSW"):
        os.makedirs(env['GSW']['root_path'], exist_ok=True)

    return env, params, out_path


def load_environment(env_file=None, env_path=os.path.join(project_path, "../environments")):
    env = configparser.ConfigParser()

    # Try to use provided env file
    if env_file:
        if not os.path.isabs(env_file) and env_path:
            env_file = os.path.join(env_path, env_file)
        if not os.path.isfile(env_file):
            raise RuntimeError("The evironment file could not be found: {}".format(env_file))
        env.read(env_file)
        set_gpt_cache_size(env)
        return env, env_file

    # Try to use host and user specific env file
    host_user_env_file = os.path.join(env_path, "{}.{}.ini".format(socket.gethostname(), getpass.getuser()))
    if os.path.isfile(host_user_env_file):
        env.read(host_user_env_file)
        set_gpt_cache_size(env)
        return env, host_user_env_file

    # Try to use host specific env file
    host_env_file = os.path.join(env_path, "{}.ini".format(socket.gethostname()))
    if os.path.isfile(host_env_file):
        env.read(host_env_file)
        set_gpt_cache_size(env)
        return env, host_env_file

    raise RuntimeError("Could not load any of the following evironments:\n{}\n{}".format(host_user_env_file,
                       host_env_file))


def load_params(params_file, params_path=os.path.join(project_path, "../parameters")):
    if not os.path.isabs(params_file) and params_path:
        params_file = os.path.join(params_path, params_file)
    if not os.path.isfile(params_file):
        raise RuntimeError("The parameter file could not be found: {}".format(params_file))
    params = configparser.ConfigParser()
    params.read(params_file)
    return params, params_file


def load_wkt(wkt_file, wkt_path=os.path.join(project_path, "../wkt")):
    if not os.path.isabs(wkt_file) and wkt_path:
        wkt_file = os.path.join(wkt_path, wkt_file)
    if not os.path.isfile(wkt_file):
        raise RuntimeError("The wkt file could not be found: {}".format(wkt_file))
    with open(wkt_file, "r") as file:
        return file.read(), wkt_file


def set_gpt_cache_size(env):
    if not env['General']['gpt_cache_size']:
        heap_size = ""
        with open(os.path.join(os.path.dirname(env['General']['gpt_path']), "gpt.vmoptions"), "rt") as f:
            for line in f:
                if line.startswith(r"-Xmx"):
                    heap_size = line.replace(r"-Xmx", "")
                    if "m" in heap_size:
                        heap_size = float(heap_size.replace(r"m", ""))/1000
                    elif "G" in heap_size:
                        heap_size = float(heap_size.replace(r"G", ""))
        if not heap_size:
            raise RuntimeError("Could not read heap size from GPT vmoptions. Set it in your env file!")
        cache_size = str(int(round(int(heap_size) * 1, 0,))) + "G"
        print("Setting GPT cache size to {}".format(cache_size))
        env['General']['gpt_cache_size'] = cache_size


def load_properties(properties_file, separator_char='=', comment_char='#'):
    """ Read a properties file into a dict. """
    properties_dict = {}
    with open(properties_file, "rt") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith(comment_char):
                key_value = line.split(separator_char)
                key = key_value[0].strip()
                value = separator_char.join(key_value[1:]).strip().strip('"')
                properties_dict[key] = value
    return properties_dict
