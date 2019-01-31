# sentinel_hindcast
Sentinel hindcast for inland water monitoring

This project is used to download and process Sentinel MSI and OLCI data and apply Atmospheric corrections and/or MPH algorithm for 
inland water studies.

# How to use
- Read the header of the sentinel_hindcast.ipynb file.
- Copy a template file and edit it. 

# Flaws to fix:
- The code only works on linux. Edits are requested on the paths in the different packages/*py files to make it work on any OS
- You also need to have polymer-v4.9 installed at '/home/username/software' or you need to modify the 'POLYMER_INSTALL_DIR' variable at the beginning of 'packages/MyProductc.py'
- You have to install snappy for python from SNAP (ESA) in your python environnement and edit the path to snappy in packages/main.py
- In general, the code would need revision and simplification.
