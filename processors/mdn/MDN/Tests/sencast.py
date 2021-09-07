#author: https://github.com/BrandonSmithJ/MDN/blob/master/README.md
import sys
sys.path.append("../..")
from MDN import image_estimates, get_tile_data, get_sensor_bands, get_tile_data_polymer
import numpy as np

def exec_mdn(sensor, in_path, out_path):
    if "poly" in sensor:
        bands, Rrs = get_tile_data_polymer(in_path, sensor, allow_neg=False)
    else:
        bands, Rrs = get_tile_data(in_path, sensor, allow_neg=False)
    estimates = image_estimates(Rrs, sensor=sensor)
    chlor_a = estimates[0]
    a = np.asarray(chlor_a)
    np.savetxt(out_path, a, delimiter=",")


# Sensor: <S2A, S2B, or OLCI>
sensor = 'OLCI-poly'    #'OLCI' works only if 673 nm band is present, which is not the case for polymer!
in_path = '../data/polymer_test.nc'
out_path = '../data/mdn_test.csv'


exec_mdn(sensor, in_path, out_path)

#'MSI': [443, 490, 560, 665, 705, 740, 783],
#'MSI-rho': [443, 490, 560, 665, 705, 740, 783, 865],
#'OLCI': [411, 442, 490, 510, 560, 619, 664, 673, 681, 708, 753, 761, 764, 767, 778],
#'OLCI-e': [411, 442, 490, 510, 560, 619, 664, 673, 681, 708, 753, 778],
#'OLCI-poly': [411, 442, 490, 510, 560, 619, 664, 681, 708, 753, 778],
#'OLCI-sat': [411, 442, 490, 510, 560, 619, 664, 673, 681, 708, 753, 761, 764, 767, ],