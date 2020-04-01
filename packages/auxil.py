#! /usr/bin/env python
# coding: utf8

import configparser
import getpass
import os
import socket


def init_hindcast(env_file, params_file, wkt_file):
    # Load environment, params and wkt from file
    env, env_file = load_environment(env_file)
    params, params_file = load_params(params_file, env['General']['params_path'])
    if not wkt_file:
        wkt_file = params['General']['wkt']
    wkt, wkt_file = load_wkt(wkt_file, env['DIAS']['wkt_path'])

    # Create output path, if it does not exist yet
    params_name, wkt_name = os.path.basename(os.path.splitext(params_file)[0]), params['General']['wkt'].split(".")[0]
    start, end = params['General']['start'][:10], params['General']['end'][:10]
    l2_path = env['DIAS']['l2_path'].format(params['General']['sensor'])
    out_path = os.path.join(l2_path, "{}_{}_{}_{}".format(params_name, wkt_name, start, end))

    if os.path.isdir(out_path) and os.listdir(out_path):
        # Reload params and wkt from existing output folder
        params, params_file = load_params(os.path.join(out_path, os.path.basename(params_file)))
        wkt, wkt_file = load_wkt(os.path.join(out_path, params['General']['wkt']))
    else:
        # Copy params file and wkt file to new output folder
        os.makedirs(out_path, exist_ok=True)
        with open(params_file, "r") as f:
            params_content = f.read()
        with open(os.path.join(out_path, os.path.basename(params_file)), "wb") as f:
            f.write(params_content.encode())
        with open(wkt_file, "r") as f:
            wkt_content = f.read()
        with open(os.path.join(out_path, params['General']['wkt']), "wb") as f:
            f.write(wkt_content.encode())

    return env, params, wkt, out_path


def load_environment(env_file=None, env_path="environments"):
    env = configparser.ConfigParser()

    # Try to use provided env file
    if env_file and not os.path.isabs(env_file):
        env_file = os.path.join(env_path, env_file)
        if not os.path.isfile(env_file):
            raise RuntimeError("The evironment file could not be found: {}".format(env_file))
        env.read(env_file)
        return env, env_file

    # Try to use host and user specific env file
    host_user_env_file = os.path.join(env_path, "{}.{}.ini".format(socket.gethostname(), getpass.getuser()))
    if os.path.isfile(host_user_env_file):
        env.read(host_user_env_file)
        return env, host_user_env_file

    # Try to use host specific env file
    host_env_file = os.path.join(env_path, "{}.ini".format(socket.gethostname()))
    if os.path.isfile(host_env_file):
        env.read(host_env_file)
        return env, host_env_file

    raise RuntimeError("Could not load any of the following evironments:\n{}\n{}".format(host_user_env_file, host_env_file))


def load_params(params_file, params_path=None):
    if params_path and not os.path.isabs(params_file):
        params_file = os.path.join(params_path, params_file)
    if not os.path.isfile(params_file):
        raise RuntimeError("The parameter file could not be found: {}".format(params_file))
    params = configparser.ConfigParser()
    params.read(params_file)
    return params, params_file


def load_wkt(wkt_file, wkt_path=None):
    if wkt_path and not os.path.isabs(wkt_file):
        wkt_file = os.path.join(wkt_path, wkt_file)
    if not os.path.isfile(wkt_file):
        raise RuntimeError("The wkt file could not be found: {}".format(wkt_file))
    with open(wkt_file, "r") as file:
        return file.read(), wkt_file
