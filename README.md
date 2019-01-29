# sentinel_hindcast
Sentinel hindcast for inland water monitoring

This project is used to download and process Sentinel MSI and OLCI data and apply Atmospheric corrections and/or MPH algorithm for 
inland water studies.

# How to use
-Read the header of the sentinel_hindcast.ipynb file.
-Copy a template file and edit it. 

# Flaws to fix:
- The code only works on linux. Edits are requested on the paths in the different packages/*py files to make it work on any OS
- For the processor to work, you need to have the dhusget.sh code (available at https://scihub.copernicus.eu/twiki/do/view/SciHubUserGuide/BatchScripting#Scripts_Examples)
in a directory under the following path: '/home/username/dhusget/dhusget.sh'. Originally I was using a lot of features from this script but with the current version of the code, it doesn't make sense to use this bash script and the function packages/download_coah_query.py needs modification (you just want to check the available products for the date range and create a text file with the urls of the products).
- You also need to have polymer-v4.9 installed at '/home/username/software' or you need to modify the 'POLYMER_INSTALL_DIR' variable at the beginning of 'packages/MyProductc.py'
- You have to install snappy for python from SNAP (ESA) in your python environnement and edit the path to snappy in packages/main.py
- Currently, when using the COAH, only the first page of the results is read (99 products max) and all pages should be read.
- In general, the code would need revision and simplification.
