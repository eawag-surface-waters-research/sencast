#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Nasa Earth Data API

Documentation for Nasa Earth Data API can be found `here. <https://wiki.earthdata.nasa.gov/display/EL/How+To+Access+Data+With+Python>`_
"""

__author__ = 'Daniel'

from http.cookiejar import CookieJar
import urllib.request


api_endpoint = "https://oceandata.sci.gsfc.nasa.gov/cgi/getfile/"


def authenticate(env):
    # See discussion https://github.com/SciTools/cartopy/issues/789#issuecomment-245789751
    # And the solution on https://wiki.earthdata.nasa.gov/display/EL/How+To+Access+Data+With+Python

    # Create a password manager to deal with the 401 reponse that is returned from
    # Earthdata Login
    password_manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    password_manager.add_password(None, "https://urs.earthdata.nasa.gov", env['EARTHDATA']['username'], env['EARTHDATA']['password'])

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
