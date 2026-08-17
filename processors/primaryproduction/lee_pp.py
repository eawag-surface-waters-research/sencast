"""
Lee primary production model for sencast.
Spectrally resolved (400-700 nm, 10 nm) with Staehr & Markager 2004 aph.
"""

import numpy as np
from scipy.integrate import trapezoid

WV = np.arange(400, 710, 10)
N_DEPTH = 101

# Staehr & Markager 2004 (31 bands, 400-700 nm at 10 nm)
A_SM = np.array([
    0.033, 0.03840468, 0.045, 0.05008251, 0.053, 0.0509849,
    0.048, 0.04547831, 0.042, 0.03696949, 0.031, 0.02498517,
    0.019, 0.01539597, 0.013, 0.01045871, 0.009, 0.00811671,
    0.007, 0.00797494, 0.008, 0.00802645, 0.009, 0.00949961,
    0.01, 0.01138279, 0.014, 0.02161268, 0.023, 0.0129098,
    0.005,
])

B_SM = np.array([
    0.233, 0.24552237, 0.259, 0.27323491, 0.281, 0.29265144,
    0.299, 0.29762277, 0.307, 0.29821063, 0.258, 0.21450849,
    0.172, 0.13739559, 0.111, 0.09845876, 0.103, 0.11762342,
    0.134, 0.1619905, 0.184, 0.17937802, 0.164, 0.17907438,
    0.193, 0.211646, 0.219, 0.19884796, 0.159, 0.11693024,
    0.137,
])

# Reference PAR spectrum (31 bands, 400-700 nm at 10 nm)
PAR_FRACTION = np.array([
    0.00227, 0.00218, 0.00239, 0.00189, 0.00297, 0.00348, 0.00345, 0.00344,
    0.00373, 0.00377, 0.00362, 0.00364, 0.00360, 0.00367, 0.00354, 0.00368,
    0.00354, 0.00357, 0.00363, 0.00332, 0.00358, 0.00357, 0.00359, 0.00340,
    0.00350, 0.00332, 0.00342, 0.00347, 0.00342, 0.00290, 0.00314,
])

PHI_MAX = 0.06
SCALAR_CORR = 1.4
UMOL_S_TO_MOL_H = 3600 * 1e-6


def _kd490_to_kdpar(kd490):
    """Morel (2007) conversion from Kd(490) to Kd(PAR)."""
    return 0.0864 + 0.884 * kd490 - 0.00137 / kd490


def _quantum_yield(E_mol_h):
    """Lee quantum yield. E in mol/m2/h."""
    E_mol_h = np.maximum(E_mol_h, 1e-6)
    return PHI_MAX * (0.4 * np.exp(-0.24 * E_mol_h)) / (0.4 + E_mol_h)


def lee_pp(chl, kd490, par_hourly):
    """Compute daily primary production for all pixels.

    Takes Chl [mg/m3], Kd490 [m-1], and hourly PAR [umol/m2/s].
    Returns PP [mg C/m2/day] and KdPAR [m-1].
    """
    chl = np.asarray(chl, dtype=np.float64)
    kd490 = np.asarray(kd490, dtype=np.float64)
    N = chl.shape[0]

    npp = np.full(N, np.nan)
    kdpar = np.full(N, np.nan)

    valid = np.isfinite(chl) & np.isfinite(kd490) & (chl > 0) & (kd490 > 0)
    if not np.any(valid):
        return npp, kdpar

    c = chl[valid]
    k = kd490[valid]
    M = c.shape[0]

    aph_spec = A_SM[None, :] * (c[:, None] ** (-B_SM[None, :])) * c[:, None]
    kp = _kd490_to_kdpar(k)

    z_max = np.minimum(4.6 / kp, 200.0)
    zfrac = np.linspace(0, 1, N_DEPTH)
    z_grid = z_max[:, None] * zfrac[None, :]
    atten = np.exp(-kp[:, None, None] * z_grid[:, :, None]) * PAR_FRACTION[None, None, :]

    e_weight = trapezoid(atten, WV, axis=2) * SCALAR_CORR * UMOL_S_TO_MOL_H
    ap_weight = trapezoid(atten * aph_spec[:, None, :], WV, axis=2) * SCALAR_CORR * UMOL_S_TO_MOL_H

    npp_valid = np.zeros(M)
    for par_surface in par_hourly:
        if par_surface <= 0 or not np.isfinite(par_surface):
            continue
        e_scalar = par_surface * e_weight
        ap = par_surface * ap_weight
        f = _quantum_yield(e_scalar)
        pp_z = 12000 * f * ap
        npp_valid += trapezoid(pp_z, z_grid, axis=1)

    npp[valid] = npp_valid
    kdpar[valid] = kp

    return npp, kdpar
