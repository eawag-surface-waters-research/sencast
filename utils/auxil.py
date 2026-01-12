#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import platform
import socket
import getpass
import subprocess
import configparser
import urllib.request
from http.cookiejar import CookieJar
from threading import Timer
from datetime import datetime

project_path = os.path.dirname(__file__)


def init_hindcast(env_file, params_file):
    """Initialize a sencast run with an environment file and a parameters file."""
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
    log_file = os.path.join(out_path, "Logs", os.path.basename(params_file).split(".")[0]+"_log_"+datetime.now().strftime("%Y%m%dT%H%M%S")+".txt")
    if not os.path.exists(os.path.dirname(log_file)):
        os.makedirs(os.path.dirname(log_file))
    env["General"]["log"] = log_file
    log(log_file, "Starting SenCast.")
    log(log_file, "Max memory: {}".format(env["General"]["max_memory"]), indent=1)
    log(log_file, "GPT cache size: {}".format(env["General"]["gpt_cache_size"]), indent=1)

    if os.path.isdir(out_path) and os.listdir(out_path) and os.path.isfile(os.path.join(out_path, os.path.basename(params_file))):
        log(log_file, "Output folder for this run already exists.")
        if "overwrite" in params["General"].keys() and params['General']['overwrite'] == "true":
            log(log_file, "Overwriting existing run")
        else:
            log(log_file, "Reading params from output folder to ensure comparable results.")
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

    if env.has_section("GSW"):
        os.makedirs(env['GSW']['root_path'], exist_ok=True)

    return env, params, out_path


def load_environment(env_file=None, env_path=os.path.join(project_path, "../environments")):
    """Load the environment configuration from a ini file. If no ini file is provided, it tries to automatically pick one."""
    env = configparser.ConfigParser()

    # Try to use provided env file
    if env_file:
        if not os.path.isabs(env_file) and env_path:
            env_file = os.path.join(env_path, env_file)
        if not os.path.isfile(env_file):
            raise RuntimeError("The evironment file could not be found: {}".format(env_file))
        env.read(env_file)
        set_memory_parameters(env)
        return env, env_file

    # Try to use host and user specific env file
    host_user_env_file = os.path.join(env_path, "{}.{}.ini".format(socket.gethostname(), getpass.getuser()))
    if os.path.isfile(host_user_env_file):
        env.read(host_user_env_file)
        set_memory_parameters(env)
        return env, host_user_env_file

    # Try to use host specific env file
    host_env_file = os.path.join(env_path, "{}.ini".format(socket.gethostname()))
    if os.path.isfile(host_env_file):
        env.read(host_env_file)
        set_memory_parameters(env)
        return env, host_env_file

    raise RuntimeError("Could not load any of the following evironments:\n{}\n{}".format(host_user_env_file,
                       host_env_file))


def load_params(params_file, params_path=os.path.join(project_path, "../parameters")):
    """Read the parameters from a ini file."""
    if not os.path.isabs(params_file) and params_path:
        params_file = os.path.join(params_path, params_file)
    if not os.path.isfile(params_file):
        raise RuntimeError("The parameter file could not be found: {}".format(os.path.abspath(params_file)))
    params = configparser.ConfigParser()
    params.read(params_file)
    return params, params_file


def load_wkt(wkt_file, wkt_path=os.path.join(project_path, "../wkt")):
    """Read the perimeter from a given wkt file."""
    if not os.path.isabs(wkt_file) and wkt_path:
        wkt_file = os.path.join(wkt_path, wkt_file)
    if not os.path.isfile(wkt_file):
        raise RuntimeError("The wkt file could not be found: {}".format(wkt_file))
    with open(wkt_file, "r") as file:
        return file.read(), wkt_file


def log_output(res, log_path, indent=2):
    for line in res.split("\n"):
        if line != "":
            log(log_path, line.strip(), indent=indent)


def gpt_subprocess(cmd, log_path, attempts=1, timeout=False, indent=1):
    log(log_path, "Calling '{}'".format(' '.join(cmd)), indent=indent)
    for attempt in range(attempts):
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        if attempt != attempts - 1 and timeout:
            log(log_path, "Beginning attempt {} of {} with a {} second timeout.".format(attempt + 1, attempts, timeout), indent=indent)
            timer = Timer(timeout, process.kill)
            timer.start()
        else:
            log(log_path, "Beginning attempt {} of {} with no timeout.".format(attempt +1, attempts), indent=indent)
        res = process.communicate()
        if attempt != attempts - 1 and timeout:
            timer.cancel()
        if process.returncode == 0:
            log_output(res[0], log_path)
            log(log_path, "GPT operation completed.", indent=indent)
            return True
        else:
            log_output(res[0], log_path)
            log_output(res[1], log_path)
            if process.returncode == -9:
                log(log_path, "GPT process was killed. Either by timeout or memory restrictions.", indent=indent)
            else:
                log(log_path, "GPT failed.", indent=indent)
    return False


def set_memory_parameters(env):
    """Set the max memory usage and GPT cache size if not set."""
    gpt_properties = os.path.join(os.path.dirname(env['General']['gpt_path']), "gpt.vmoptions")
    if "max_memory" in env["General"] and env["General"]["max_memory"]:
        if os.path.isfile(gpt_properties):
            with open(gpt_properties, 'rt') as f:
                lines = f.readlines()
            exists = False
            for i, line in enumerate(lines):
                if line.startswith(r"-Xmx"):
                    lines[i] = "-Xmx{}\n".format(env["General"]["max_memory"])
                    exists = True
            if not exists:
                lines.append("-Xmx{}\n".format(env["General"]["max_memory"]))
            with open(gpt_properties, 'w') as f:
                f.writelines(lines)
        else:
            with open(gpt_properties, 'w') as f:
                f.write("-Xmx{}\n".format(env["General"]["max_memory"]))
    else:
        if os.path.isfile(gpt_properties):
            with open(gpt_properties, 'rt') as f:
                lines = f.readlines()
            exists = False
            for i, line in enumerate(lines):
                if line.startswith(r"-Xmx"):
                    env["General"]["max_memory"] = line.replace(r"-Xmx", "").strip()
                    exists = True
            if not exists:
                raise RuntimeError("Could not read -Xmx size from GPT vmoptions. Set max_memory in your env file.")
        else:
            raise RuntimeError("Could not read -Xmx size from GPT vmoptions. Set max_memory in your env file.")

    if "gpt_cache_size" not in env['General'] or not env['General']['gpt_cache_size']:
        if "m" in env["General"]["max_memory"]:
            heap_size = float(env["General"]["max_memory"].replace(r"m", ""))
        elif "G" in env["General"]["max_memory"]:
            heap_size = float(env["General"]["max_memory"].replace(r"G", "")) * 1000
        elif "g" in env["General"]["max_memory"]:
            heap_size = float(env["General"]["max_memory"].replace(r"g", "")) * 1000
        else:
            raise RuntimeError("Unrecognised Xmx parameter: {}".format(env["General"]["max_memory"]))
        env['General']['gpt_cache_size'] = str(int(round(int(heap_size) * 0.7, 0,))) + "m"


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


def log(file, text, indent=0, blank=False):
    text = str(text).split(r"\n")
    with open(file, "a") as file:
        for t in text:
            if t != "" or blank:
                if blank:
                    out = t
                else:
                    out = datetime.now().strftime("%H:%M:%S.%f") + (" " * 3 * (indent + 1)) + t
                print(out)
                file.write(out + "\n")


def error(file, e):
    text = str(e).split("\n")
    with open(file, "a") as file:
        for t in text:
            if t != "":
                out = datetime.now().strftime("%H:%M:%S.%f") + "   ERROR: " + t
                print(out)
                file.write(out + "\n")
    raise ValueError(str(e))


def authenticate_earthdata_anc(env):
    """If the configuration contains username and password for NASA anc data api, create ~/.netrc and ~/.urs_cookies
    (Linux) or ~/_netrc (Windows) containing these credentials"""
    if "EARTHDATA" not in env or "username" not in env['EARTHDATA'] or "password" not in env['EARTHDATA']:
        return
    os.makedirs(env['EARTHDATA']['anc_path'], exist_ok=True)
    username = env['EARTHDATA']['username']
    password = env['EARTHDATA']['password']

    if "Windows" == platform.system():
        if not os.path.isfile(os.path.join(os.path.expanduser("~"), '_netrc')):
            with open(os.path.join(os.path.expanduser("~"), '_netrc'), 'w') as f:
                f.write("machine urs.earthdata.nasa.gov\nlogin {}\npassword {}".format(username, password))
    else:
        if not os.path.isfile(os.path.join(os.path.expanduser("~"), '.netrc')):
            with open(os.path.join(os.path.expanduser("~"), '.netrc'), 'w') as f:
                f.write("machine urs.earthdata.nasa.gov login {} password {}".format(username, password))
        if not os.path.isfile(os.path.join(os.path.expanduser("~"), '.urs_cookies')):
            with open(os.path.join(os.path.expanduser("~"), '.urs_cookies'), 'w') as f:
                f.write("")
    # See discussion https://github.com/SciTools/cartopy/issues/789#issuecomment-245789751
    # And the solution on https://wiki.earthdata.nasa.gov/display/EL/How+To+Access+Data+With+Python

    # Create a password manager to deal with the 401 reponse that is returned from
    # Earthdata Login
    password_manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    password_manager.add_password(None, "https://urs.earthdata.nasa.gov", username, password)

    # Create a cookie jar for storing cookies. This is used to store and return
    # the session cookie given to use by the data server (otherwise it will just
    # keep sending us back to Earthdata Login to authenticate).  Ideally, we
    # should use a file based cookie jar to preserve cookies between runs. This
    # will make it much more efficient.
    cookie_jar = CookieJar()

    # Install all the handlers.
    opener = urllib.request.build_opener(
        urllib.request.HTTPBasicAuthHandler(password_manager),
        urllib.request.HTTPCookieProcessor(cookie_jar))
    urllib.request.install_opener(opener)


def authenticate_cds_anc(env):
    """If the configuration contains username and password for CDS anc data api, create ~/.cdsapirc containing these
    credentials"""
    if "CDS" not in env or "uid" not in env['CDS'] or "api_key" not in env['CDS']:
        return
    os.makedirs(env['CDS']['anc_path'], exist_ok=True)
    uid = env['CDS']['uid']
    api_key = env['CDS']['api_key']

    if not os.path.isfile(os.path.join(os.path.expanduser("~"), ".cdsapirc")):
        with open(os.path.join(os.path.expanduser("~"), ".cdsapirc"), "w") as f:
            f.write("url: https://cds.climate.copernicus.eu/api/v2\n")
            f.write("key: {}:{}".format(uid, api_key))

def chmod_recursive(path, mode):
    """Recursively chmod a directory"""
    for root, dirs, files in os.walk(path):
        os.chmod(root, mode)
        for file in files:
            os.chmod(os.path.join(root, file), mode)
