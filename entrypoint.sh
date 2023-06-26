#!/bin/bash

# Initialize Conda
. /opt/conda/etc/profile.d/conda.sh

# Activate the Conda environment
conda activate sencast

# Execute your Python script or desired command
python -u /sencast/main.py "$@"
