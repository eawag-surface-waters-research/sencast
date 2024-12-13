#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
The Datalakes adapter notifies Datalakes of new data
"""

import requests
from utils.auxil import log

# the url to post new data notification to
NOTIFY_URL = "https://api.datalakes-eawag.ch/externaldata/sync/remotesensing"

def apply(env, params, l2product_files, date):
    """Apply Datalakes adapter.
        1. Call Datalakes endpoint

        Parameters
        -------------

        params
            Dictionary of parameters, loaded from input file
        env
            Dictionary of environment parameters, loaded from input file
        l2product_files
            Dictionary of Level 2 product files created by processors
        date
            Run date
        """
    log(env["General"]["log"], "Notifying Datalakes API of updated data.", indent=1)
    requests.get(NOTIFY_URL)
