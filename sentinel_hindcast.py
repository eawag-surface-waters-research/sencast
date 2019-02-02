# Import libs
from packages.main import eawag_hindcast
import getpass


user = getpass.getuser()
POLYMER_INSTALL_DIR = '/home/'+user+'/software/polymer-v4.9'
sys.path.append(POLYMER_INSTALL_DIR)
# Options
params_filename = 'test-S3.txt'

eawag_hindcast(params_filename, POLYMER_INSTALL_DIR)
