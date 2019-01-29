from packages.main import eawag_hindcast
from packages.auxil import read_parameters_file, open_products
import os
import urllib3
import urllib.parse
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

os.chdir('/home/nouchi/jupyter/dev_1P')
# Options
param_file = '/home/nouchi/jupyter/dev_1P/parameters/params1.txt'
params = read_parameters_file(param_file, verbose=True)
# Select an existing output directory
out_dir = '/home/nouchi/output/'

eawag_hindcast(params, out_dir)
