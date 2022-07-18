# Sencast

Sencast is a toolbox to derive water quality factors by processing images from the ESA satelites Sentinel 2 and Sentinel 3.
It is develeoped and maintained by the [SURF Remote Sensing group at Eawag](https://www.eawag.ch/en/department/surf/main-focus/remote-sensing/).

## Installation
You are expected to have Anaconda and SNAP installed.
```
cd ~
git clone git@gitlab.com:eawag-rs/sencast.git
conda env create -f ~/sencast/sencast-37.yml
```
Then create your environment file and test your installation as follows:
```
cd ~/sencast
conda activate sencast-37
python3 tests/test_installation.py
```

## Documentation

Documentation is available at [ReadTheDocs](https://sencast.readthedocs.io/en/latest/?).

## Papers

**SenCast: Copernicus Satellite Data on Demand**  
*D. Odermatt, J. Runnalls, J. Sturm, A. Damm*  
[German](https://www.dora.lib4ri.ch/eawag/islandora/object/eawag%3A21549/datastream/PDF4/Odermatt-2020-SenCast-%28accepted_version%29.pdf) [English](https://www.dora.lib4ri.ch/eawag/islandora/object/eawag%3A21549/datastream/PDF3/Odermatt-2020-SenCast-%28unspecified_8a1c1609%29.pdf)