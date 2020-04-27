#!/bin/bash
mkdir -p /prj/sentinel-hindcast/log
filename=/prj/sentinel-hindcast/log/$(date '+%Y-%m-%d-%H%M%S').log
touch $filname
conda activate sentinel-hindcast-37
python datalakes.py > $filename
# sudo shutdown
