#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os

from main import hindcast


hindcast(os.path.join(os.path.dirname(os.path.abspath(__file__)), "parameters", "test_S2.ini"))
