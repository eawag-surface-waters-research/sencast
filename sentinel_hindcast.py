#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Import libs
from packages.main import eawag_hindcast

# Options
params_filename = 'parameters_silsersee_S2.txt'

eawag_hindcast(params_filename)