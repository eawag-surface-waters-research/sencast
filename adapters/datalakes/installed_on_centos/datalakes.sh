#!/bin/bash
mkdir -p /prj/datalakes/log
filename=/prj/datalakes/log/$(date '+%Y-%m-%d-%H%M%S').log
touch $filename
conda activate sentinel-hindcast-37
python datalakes.py > $filename
# sudo shutdown
