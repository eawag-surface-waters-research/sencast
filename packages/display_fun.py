#! /usr/bin/env python
# coding: utf8


import matplotlib.pyplot as plt
plt.switch_backend('agg')
import matplotlib.cm as cm
import numpy as np
import matplotlib.patches as mpatches   
    
def rescale_intensity(x, minval, maxval):
    with np.errstate(invalid='ignore'):
        x[x < minval] = minval
        x[x > maxval] = maxval
        y = (x - minval) / (maxval-minval)
        y[y < 0] = 0.
        y[y > 1] = 1.
    return y


def unscale_values(x, minval, maxval):
    return x * (maxval-minval) + minval

    
def display_band_with_flag(product, bandname, flag=None, log=False,
                           vmax=0.00001, savefig=False, savename='',
                           cbtitle=' '):
    Bx = product.getBand(bandname)
    unit = Bx.getUnit()
    if unit is '1' or unit is None:
        unit = ' '
    w = product.getSceneRasterWidth()
    h = product.getSceneRasterHeight()
    if flag is None:
        flag = np.zeros((h,w), dtype=np.uint32)
    Bx_data = np.zeros(w*h, dtype = np.float32)
    Bx.readPixels(0,0,w,h,Bx_data)
    Bx_data.shape = (h,w)
    Bx_data[Bx_data > 1000] = np.nan
    if log:
        print('Transforming log data...')
        Bx_data = np.exp(Bx_data)
    val1, val2 = np.nanpercentile(Bx_data, (1,99))
    if vmax != 0.00001:
        val2 = vmax
    else:
        vmax = val2
    if val1 == val2 or np.isnan(val2) or np.isinf(val2) or np.isnan(val1) or np.isinf(val1):
        Bx_data_new = Bx_data
        val1 = 0
        val2 = 1
    else:
        Bx_data_new = rescale_intensity(Bx_data, val1, val2)
    
    fig, ax = plt.subplots(figsize=(12, 12))                     
    cax = ax.imshow(Bx_data_new, cmap=cm.gray)  
    cb = fig.colorbar(cax, orientation='horizontal')
    # Get tick values
    ticks = [float(t.get_text().replace(u'\N{MINUS SIGN}', '-')) for t in cb.ax.get_xticklabels()]
    ticks = np.round(unscale_values(np.array(ticks), val1, val2)*10000)/10000
    cb.ax.set_xticklabels(ticks)
    if (unit != ' ' and cbtitle == ' '):
        cb.ax.set_title(unit)
    elif cbtitle != ' ':
        cb.ax.set_title(cbtitle)
    else:
        cb.ax.set_title(unit)
    ax.get_xaxis().set_visible(False)
    ax.get_yaxis().set_visible(False)
    plt.title(product.getName())
    if savefig:
        plt.savefig(savename, dpi=300, bbox_inches='tight')
    else:
        plt.show()
    plt.close()

def display_rgb_with_flag(product, bandnames, flag1=None, flag2=None,
                          flag3=None, savefig=False, savename='',
                          flaglabel1='flag1', flaglabel2='flag2',
                          flaglabel3='flag3'):
    w = product.getSceneRasterWidth()
    h = product.getSceneRasterHeight()
    if flag1 is None:
        flag1 = np.zeros((h,w), dtype=np.uint8)
    if flag2 is None:
        flag2 = np.zeros((h,w), dtype=np.uint8)
    if flag3 is None:
        flag3 = np.zeros((h,w), dtype=np.uint8)
     
    bandata = np.zeros((h,w,3), dtype=np.float32)
    c = 0
    for bn in bandnames:
        Bx = product.getBand(bn)
        Bx_data = np.zeros(w*h, dtype = np.float32)
        Bx.readPixels(0,0,w,h,Bx_data)
        Bx_data.shape = (h,w)
        # APPLY FLAG (OPTIONAL?)
        flag = np.logical_or(flag1 == 1, flag2 == 1)
        flag = np.logical_or(flag, flag3 == 1)
        Bx_data[flag] = np.nan
        #########################
        val1, val2 = np.nanpercentile(Bx_data, (2,98))
        Bx_data_new = rescale_intensity(Bx_data, val1, val2)
        bandata[:,:,c] = Bx_data_new
        c += 1
        
    fig, ax = plt.subplots(figsize=(12, 12))                     
    fig = ax.imshow(bandata)
    cmap = {}
    labels = {}
    if np.nanmax(flag1) > 0:
        cmap[1] = cm.Pastel1(0)
        labels[1] = flaglabel1
        flag1 = np.ma.masked_where(flag1 == 0, flag1)
        fig = ax.imshow(flag1, cmap=cm.Pastel1, alpha=0.6)
    if np.nanmax(flag2) > 0:
        cmap[2] = cm.Pastel2(0)
        labels[2] = flaglabel2
        flag2 = np.ma.masked_where(flag2 == 0, flag2)
        fig = ax.imshow(flag2, cmap=cm.Pastel2, alpha=0.6)
    if np.nanmax(flag3) > 0:
        cmap[3] = cm.jet(0)
        labels[3] = flaglabel3
        flag3 = np.ma.masked_where(flag3 == 0, flag3)
        fig = ax.imshow(flag3, cmap=cm.jet, alpha=0.6)
    ax.get_xaxis().set_visible(False)
    ax.get_yaxis().set_visible(False)
    plt.title(product.getName())
    if cmap:
        patches =[mpatches.Patch(color=cmap[i],label=labels[i]) for i in cmap]
        plt.legend(handles=patches, loc=4, borderaxespad=0., fontsize=12)
    if savefig:
        plt.savefig(savename)
        print('fig saved')
    else:
        plt.show()
    plt.close()
