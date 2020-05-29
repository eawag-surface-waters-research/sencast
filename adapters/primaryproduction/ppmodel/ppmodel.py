import numpy as np
from matplotlib import pyplot as plt
import os

this_dir, this_filename = os.path.split(__file__)

# text file with Staehr absorption parametrisation taken from Excel:
staehr = np.loadtxt(os.path.join(this_dir, 'staehr.csv'), delimiter=',')

def absorption(Cchl) :
    return staehr[1,:]*(Cchl**(1-staehr[2,:]))

def q0par(z, qpar0, Cchl, Kpar) :
    C1 = 1.32*Kpar**0.153
    C2 = 0.0023*Cchl + 0.016

    return C1*np.exp(C2*z) * 0.94*qpar0*np.exp(-Kpar*z)

def Qstarpar(z, q0par, Cchl) :
    return q0par*np.average(absorption(Cchl))

def M (qpar0, Cchl, Kpar):
    if Cchl < 35:
        return 3.18-0.2125*Kpar**2.5+0.34*qpar0
    if Cchl < 80:
        return 3.58-0.31*qpar0-0.0072*Cchl
    if Cchl < 120:
        return 2.46 - 0.106*qpar0 - 0.00083*Cchl**1.5
    else :
        return 0.67

def Fpar(z, q0par, M) :
    Fmax = 0.08
    return Fmax/(1+M*q0par)**1.5

def PP(z, qpar0, Cchl, Kpar):
    Mval = M(qpar0, Cchl, Kpar)
    rad = q0par(z, qpar0, Cchl, Kpar)
    return 12000*Fpar(z, rad, Mval)*Qstarpar(z, rad, Cchl)
