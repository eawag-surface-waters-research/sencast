import getpass
import socket
import os
import sys


user = getpass.getuser()
hostname = socket.gethostname()


if hostname in ['daniels-macbook-pro.home', 'Daniels-MacBook-Pro.local']:
    os.chdir(os.path.join('/Users', user, 'Dropbox', 'Wrk Eawag', 'DIAS'))
    cwd = os.getcwd()
    wkt_dir = os.path.join(cwd, 'wkt')
    params_path = os.path.join('/Users', user, 'PycharmProjects', 'sentinel_hindcast', 'parameters')
    gpt_path = '/Applications/snap/bin/gpt'
    polymer_path = '/miniconda3/lib/python3.6/site-packages/polymer-v4.9'


elif hostname == 'SUR-ODERMADA-MC.local':
    os.chdir(os.path.join('/Volumes', 'DIAS-drive', 'DIAS'))
    cwd = os.getcwd()
    wkt_dir = os.path.join(cwd, 'wkt')
    params_path = os.path.join('/Users', user, 'PycharmProjects', 'sentinel_hindcast', 'parameters')
    gpt_path = '/Applications/snap/bin/gpt'
    polymer_path = '/Users/' + user + '/anaconda3/envs/sentinel-hindcast/lib/python3.6/site-packages/polymer-v4.11'


elif hostname == 'tbd':
    os.chdir(os.path.join('/home/', user))
    cwd = os.getcwd()
    wkt_dir = os.path.join(cwd, 'wkt')
    params_path = os.path.join(cwd, 'jupyter', 'sentinel_hindcast', 'parameters')
    gpt_path = '/Applications/snap/bin/gpt'
    polymer_path = '/Users/' + user + '/PycharmProjects/sentinel_hindcast_git/polymer-v4.11'


else:
    sys.exit('Hostname is ' + hostname + ', please add path configuration to path_config.py')