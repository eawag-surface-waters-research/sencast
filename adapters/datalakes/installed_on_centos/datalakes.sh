#!/bin/bash
mkdir -p /prj/datalakes/log
filename=/prj/datalakes/log/$(date '+%Y-%m-%d-%H%M%S').log
touch "$filename"
source /opt/anaconda3/etc/profile.d/conda.sh
conda activate sentinel-hindcast-37
python datalakes.py > "$filename" 2>&1
