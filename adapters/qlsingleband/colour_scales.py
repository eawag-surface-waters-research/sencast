#! /usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Daniel'

import numpy as np
import matplotlib.colors as colors
import colour as colour_science


def rainbow_bright():

    cdict = {
        'red':   [(0.00,  0.50, 0.50),
                  (0.02,  0.50, 0.50),
                  (0.05,  0.50, 0.50),
                  (0.10,  0.50, 0.50),
                  (0.15,  0.50, 0.50),
                  (0.20,  0.75, 0.75),
                  (0.30,  1.00, 1.00),
                  (0.40,  1.00, 1.00),
                  (0.50,  1.00, 1.00),
                  (0.60,  1.00, 1.00),
                  (0.75,  1.00, 1.00),
                  (1.00,  0.75, 0.75)],

        'green': [(0.00,  0.50, 0.50),
                  (0.02,  0.75, 0.75),
                  (0.05,  1.00, 1.00),
                  (0.10,  1.00, 1.00),
                  (0.15,  1.00, 1.00),
                  (0.20,  1.00, 1.00),
                  (0.30,  1.00, 1.00),
                  (0.40,  0.75, 0.75),
                  (0.50,  0.50, 0.50),
                  (0.60,  0.50, 0.50),
                  (0.75,  0.50, 0.50),
                  (1.00,  0.50, 0.50)],

        'blue':  [(0.00,  1.00, 1.00),
                  (0.02,  1.00, 1.00),
                  (0.05,  1.00, 1.00),
                  (0.10,  0.75, 0.75),
                  (0.15,  0.50, 0.50),
                  (0.20,  0.50, 0.50),
                  (0.30,  0.50, 0.50),
                  (0.40,  0.50, 0.50),
                  (0.50,  0.50, 0.50),
                  (0.60,  0.75, 0.75),
                  (0.75,  1.00, 1.00),
                  (1.00,  1.00, 1.00)]}

    return colors.LinearSegmentedColormap('RainbowBright', cdict)


def rainbow_king():

    cdict = {
        'red':   [(0.00,  0.05, 0.05),
                  (0.02,  0.08, 0.08),
                  (0.05,  0.09, 0.09),
                  (0.10,  0.30, 0.30),
                  (0.15,  0.63, 0.63),
                  (0.20,  1.00, 1.00),
                  (0.30,  1.00, 1.00),
                  (0.40,  1.00, 1.00),
                  (0.50,  1.00, 1.00),
                  (0.60,  1.00, 1.00),
                  (0.75,  0.95, 0.95),
                  (1.00,  0.51, 0.51)],

        'green': [(0.00,  0.00, 0.00),
                  (0.02,  0.00, 0.00),
                  (0.05,  0.32, 0.32),
                  (0.10,  0.58, 0.58),
                  (0.15,  0.81, 0.81),
                  (0.20,  1.00, 1.00),
                  (0.30,  0.65, 0.65),
                  (0.40,  0.50, 0.50),
                  (0.50,  0.38, 0.38),
                  (0.60,  0.00, 0.00),
                  (0.75,  0.00, 0.00),
                  (1.00,  0.00, 0.00)],

        'blue':  [(0.00,  0.31, 0.31),
                  (0.02,  0.49, 0.49),
                  (0.05,  0.42, 0.42),
                  (0.10,  0.30, 0.30),
                  (0.15,  0.12, 0.12),
                  (0.20,  0.00, 0.00),
                  (0.30,  0.05, 0.05),
                  (0.40,  0.00, 0.00),
                  (0.50,  0.05, 0.05),
                  (0.60,  0.00, 0.00),
                  (0.75,  0.51, 0.51),
                  (1.00,  0.25, 0.25)]}

    return colors.LinearSegmentedColormap('RainbowKing', cdict)


def moores_seven_owt():

    cdict = {
        'red':   [(0.00,  0.00, 0.40),
                  (0.14,  0.40, 0.20),
                  (0.29,  0.20, 0.60),
                  (0.43,  0.60, 0.60),
                  (0.57,  0.60, 0.40),
                  (0.71,  0.40, 0.80),
                  (0.86,  0.80, 0.60),
                  (1.00,  0.60, 0.00)],

        'green': [(0.00,  0.00, 0.20),
                  (0.14,  0.20, 0.40),
                  (0.29,  0.40, 1.00),
                  (0.43,  1.00, 0.80),
                  (0.57,  0.80, 0.60),
                  (0.71,  0.60, 0.60),
                  (0.86,  0.60, 0.40),
                  (1.00,  0.40, 0.00)],

        'blue':  [(0.00,  0.00, 0.60),
                  (0.14,  0.60, 0.80),
                  (0.29,  0.80, 1.00),
                  (0.43,  1.00, 0.20),
                  (0.57,  0.20, 0.40),
                  (0.71,  0.40, 0.40),
                  (0.86,  0.40, 0.00),
                  (1.00,  0.00, 0.00)]}

    return colors.LinearSegmentedColormap('MooresSevenOWT', cdict)


def cyano_portion():

    cdict = {
        'red':   [(0.00,  0.17, 0.17),
                  (0.25,  0.17, 0.17),
                  (0.50,  0.17, 0.17),
                  (0.75,  0.17, 0.17),
                  (1.00,  0.17, 0.17)],

        'green': [(0.00,  0.40, 0.40),
                  (0.25,  0.72, 0.72),
                  (0.50,  0.72, 0.72),
                  (0.75,  0.67, 0.67),
                  (1.00,  0.34, 0.34)],

        'blue':  [(0.00,  0.17, 0.17),
                  (0.25,  0.43, 0.43),
                  (0.50,  0.71, 0.71),
                  (0.75,  0.95, 0.95),
                  (1.00,  0.66, 0.66)]}

    return colors.LinearSegmentedColormap('CyanoPortion', cdict)


def floating_portion():

    cdict = {
        'red':   [(0.00,  0.17, 0.17),
                  (0.25,  0.43, 0.43),
                  (0.50,  0.71, 0.71),
                  (0.75,  0.95, 0.95),
                  (1.00,  0.66, 0.66)],

        'green': [(0.00,  0.40, 0.40),
                  (0.25,  0.72, 0.72),
                  (0.50,  0.72, 0.72),
                  (0.75,  0.67, 0.67),
                  (1.00,  0.34, 0.34)],

        'blue':  [(0.00,  0.17, 0.17),
                  (0.25,  0.27, 0.27),
                  (0.50,  0.53, 0.53),
                  (0.75,  0.95, 0.95),
                  (1.00,  0.71, 0.71)]}

    return colors.LinearSegmentedColormap('FloatingPortion', cdict)


def num_obs_scale():

    cdict = {
        'red':   [(0.000,  0.00, 0.5),
                  (0.167,  0.5, 0.5),
                  (0.333,  0.5, 0.75),
                  (0.500,  0.75, 1.0),
                  (0.667,  1.0, 1.0),
                  (0.833,  1.0, 1.0),
                  (1.000,  1.0, 0.00)],

        'green': [(0.000,  0.00, 0.5),
                  (0.167,  0.5, 1.0),
                  (0.333,  1.0, 1.0),
                  (0.500,  1.0, 1.0),
                  (0.667,  1.0, 0.75),
                  (0.833,  0.75, 0.5),
                  (1.000,  0.5, 0.00)],

        'blue':  [(0.000,  0.00, 1.0),
                  (0.167,  1.0, 1.0),
                  (0.333,  1.0, 0.75),
                  (0.500,  0.75, 0.5),
                  (0.667,  0.5, 0.5),
                  (0.833,  0.5, 0.5),
                  (1.000,  0.5, 0.00)]}

    return colors.LinearSegmentedColormap('NumObsScale', cdict)


def extent_true():

    cdict = {
        'red':   [(0.00,  1.00, 1.00),
                  (0.33,  1.00, 0.30),
                  (0.66,  0.30, 1.00),
                  (1.00,  1.00, 1.00)],

        'green': [(0.00,  1.00, 1.00),
                  (0.33,  1.00, 0.30),
                  (0.66,  0.30, 1.00),
                  (1.00,  1.00, 1.00)],

        'blue':  [(0.00,  1.00, 1.00),
                  (0.33,  1.00, 0.30),
                  (0.66,  0.30, 0.30),
                  (1.00,  0.30, 0.30)]}

    return colors.LinearSegmentedColormap('ExtentTrue', cdict)


def red2blue():

    cdict = {
        'red':   [(0.00,  202/255, 202/255),
                  (0.25,  244/255, 244/255),
                  (0.50,  247/255, 247/255),
                  (0.75,  146/255, 146/255),
                  (1.00,  5/255, 5/255)],

        'green': [(0.00,  0.00, 0.00),
                  (0.25,  165/255, 165/255),
                  (0.50,  247/255, 247/255),
                  (0.75,  197/255, 197/255),
                  (1.00,  113/255, 113/255)],

        'blue':  [(0.00,  32/255, 32/255),
                  (0.25,  130/255, 130/255),
                  (0.50,  247/255, 247/255),
                  (0.75,  222/255, 222/255),
                  (1.00,  176/255, 176/255)]}

    return colors.LinearSegmentedColormap('Red2Blue', cdict)


def spectral_cie(wvl_min, wvl_max):
    # from https://colour.readthedocs.io/en/develop/_modules/colour/plotting/colorimetry.html#plot_visible_spectrum
    # and https://colour.readthedocs.io/en/develop/_modules/colour/plotting/colorimetry.html#plot_single_sd

    cmfs = 'CIE 1931 2 Degree Standard Observer'
    cmfs = colour_science.utilities.first_item(colour_science.plotting.filter_cmfs(cmfs).values())

    wavelengths = cmfs.wavelengths

    RGB = colour_science.plotting.XYZ_to_plotting_colourspace(
        colour_science.colorimetry.wavelength_to_XYZ(wavelengths, cmfs),
        illuminant=colour_science.ILLUMINANTS['CIE 1931 2 Degree Standard Observer']['E'],
        apply_cctf_encoding=True)

    cdict = {'red': [], 'green': [], 'blue': []}

    for i, wvl in enumerate(wavelengths):
        if wvl >= wvl_min and wvl <= wvl_max:
            rel_pos = (wvl - wvl_min) / (wvl_max - wvl_min)
            cdict['red'].append([rel_pos, RGB[i][0], RGB[i][0]])
            cdict['green'].append([rel_pos, RGB[i][1], RGB[i][1]])
            cdict['blue'].append([rel_pos, RGB[i][2], RGB[i][2]])

    return colors.LinearSegmentedColormap('SpectralCIE', cdict)


def forel_ule():
    # see https://www.researchgate.net/figure/RGB-values-for-the-reproduction-of-the-FU-legend_tbl2_258687751

    rel_pos =  [i/21 for i in range(1, 21)]
    cdict = {'red': [], 'green': [], 'blue': []}

    Rs = [ 33,  49,  50,  75,  86, 109, 105, 117, 123, 125, 149, 148, 165, 170, 173, 168, 174, 179, 175, 164, 161]
    Gs = [ 88, 109, 124, 128, 143, 146, 140, 158, 166, 174, 182, 182, 188, 184, 181, 169, 159, 160, 138, 105,  77]
    Bs = [188, 197, 187, 160, 150, 152, 134, 114,  84,  56,  69,  96, 118, 109,  95, 101,  92,  83,  68,   5,   4]

    # first anchor; FU 1 color at 0.5
    cdict['red'].append([0, Rs[0] / 255, Rs[0] / 255])
    cdict['green'].append([0, Gs[0] / 255, Gs[0] / 255])
    cdict['blue'].append([0, Bs[0] / 255, Bs[0] / 255])

    # nth anchor
    for i, pos in enumerate(rel_pos):
        cdict['red'].append([pos, Rs[i]/255, Rs[i + 1]/255])
        cdict['green'].append([pos, Gs[i]/255, Gs[i + 1]/255])
        cdict['blue'].append([pos, Bs[i]/255, Bs[i + 1]/255])

    # last anchor; FU 21 color at 21.5
    cdict['red'].append([1, Rs[20] / 255, Rs[20] / 255])
    cdict['green'].append([1, Gs[20] / 255, Gs[20] / 255])
    cdict['blue'].append([1, Bs[20] / 255, Bs[20] / 255])

    return colors.LinearSegmentedColormap('ForelUle', cdict)


def cloud_color():
    return


def shadow_color():
    return


def suspect_color():
    return
