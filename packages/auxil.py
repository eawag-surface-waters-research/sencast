#! /usr/bin/env python
# coding: utf8

import configparser
import getpass
import os
import socket


def load_environment(env_file=None, env_path="environments"):
    env = configparser.ConfigParser()

    # Try to use provided env file
    if env_file and not os.path.isabs(env_file):
        env_file = os.path.join(env_path, env_file)
        if not os.path.isfile(env_file):
            raise RuntimeError("The evironment file could not be found: {}".format(env_file))
        env.read(env_file)
        return env

    # Try to use host and user specific env file
    host_user_env_file = os.path.join(env_path, "{}.{}.ini".format(socket.gethostname(), getpass.getuser()))
    if os.path.isfile(host_user_env_file):
        env.read(host_user_env_file)
        return env

    # Try to use host specific env file
    host_env_file = os.path.join(env_path, "{}.ini".format(socket.gethostname()))
    if os.path.isfile(host_env_file):
        env.read(host_env_file)
        return env

    raise RuntimeError("Could not load any of the following evironments:\n{}\n{}".format(host_user_env_file, host_env_file))


def load_params(params_file, params_path=None):
    if params_path and not os.path.isabs(params_file):
        params_file = os.path.join(params_path, params_file)
    if not os.path.isfile(params_file):
        raise RuntimeError("The parameter file could not be found: {}".format(params_file))
    params = configparser.ConfigParser()
    params.read(params_file)
    return params


def load_wkt(wkt_file, wkt_path=None):
    if wkt_path and not os.path.isabs(wkt_file):
        wkt_file = os.path.join(wkt_path, wkt_file)
    if not os.path.isfile(wkt_file):
        raise RuntimeError("The wkt file could not be found: {}".format(wkt_file))
    with open(wkt_file, "r") as file:
        return file.read()
