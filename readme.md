# Sencast

Sencast is a toolbox to download and derive water quality parameters from satellite images. It acts as a framework for 
the use a variety of processors such as Idepix, Polymer, Sen2Cor and Acolite. It supports ESA satellites Sentinel 2 and 
Sentinel 3 and USGS satellite Landsat 8.

It is developed and maintained by the [SURF Remote Sensing group at Eawag](https://www.eawag.ch/en/department/surf/main-focus/remote-sensing/).
## Installation
Anaconda and Snap Desktop are required to install Sencast
- [Anaconda](https://www.anaconda.com)
- [SNAP Desktop](https://step.esa.int/main/download/snap-download/)
```
git clone git@gitlab.com:eawag-rs/sencast.git
conda env create -f ~/sencast/sencast.yml
```
Then create your **environment file** (use environments/example.ini as a template) and test your installation as follows:
```
cd ~/sencast
conda activate sencast
python3 tests/test_installation.py
```
This will output a log of which processors are functioning. After the above steps it is normal that only Idepix and MPH 
processors function. For installation of the additional processors refer to the full documentation below:

## Documentation

Full documentation is available at [ReadTheDocs](https://sencast.readthedocs.io/en/latest/?).

## Papers

**SenCast: Copernicus Satellite Data on Demand**  
*D. Odermatt, J. Runnalls, J. Sturm, A. Damm*  
[German](https://www.dora.lib4ri.ch/eawag/islandora/object/eawag%3A21549/datastream/PDF4/Odermatt-2020-SenCast-%28accepted_version%29.pdf) [English](https://www.dora.lib4ri.ch/eawag/islandora/object/eawag%3A21549/datastream/PDF3/Odermatt-2020-SenCast-%28unspecified_8a1c1609%29.pdf)