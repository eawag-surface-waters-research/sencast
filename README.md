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
git clone git@github.com:eawag-surface-waters-research/sencast.git
conda env create -f sencast.yml
```
Then create your **environment file** (use environments/example.ini as a template) and test your installation as follows:
```
cd ~/sencast
conda activate sencast
python main.py -t
```
This will output a log of which processors are functioning. After the above steps it is normal that only the image download functions. 
For installation of the processors refer to the full documentation below.

### ⚠️ Warning
It can be difficult and time-consuming to get a local installation set up (particularly for Windows). For users not 
planning on developing the code it is recommended to use the Docker image provided (see below).

## Documentation

Full documentation is available at [ReadTheDocs](https://sencast.readthedocs.io/en/latest/?).


## Arguments

```
python main.py
```

| Parameter         |       Default       | Description                                                       |	
|:------------------|:-------------------:|:------------------------------------------------------------------|
| -t --tests 	      |       	False        | run test processing to check setup                                |
| -x --delete_tests |       	False        | delete previous test run                                          |
| -p --parameters 	 |      	Required      | link to the parameters.ini file (required when not running tests) |
| -e  --environment | ${machine-name}.ini | link to the environment.ini file                                  |
| -d -–downloads 	  |         	1	         | number of parallell downloads                                     |
| -p --processors   |         1	          | number of parallell processors                                    |
| -a --adapters	    |          1          | number of parallell adapters                                      |

## Papers

**SenCast: Copernicus Satellite Data on Demand**  
*D. Odermatt, J. Runnalls, J. Sturm, A. Damm*  
[German](https://www.dora.lib4ri.ch/eawag/islandora/object/eawag%3A21549/datastream/PDF4/Odermatt-2020-SenCast-%28accepted_version%29.pdf) [English](https://www.dora.lib4ri.ch/eawag/islandora/object/eawag%3A21549/datastream/PDF3/Odermatt-2020-SenCast-%28unspecified_8a1c1609%29.pdf)

## Docker

Manual installation of all the processors is challenging and can be simplified through the use of a docker container.

Users should first ensure they have a functioning docker installation.

### Pull container

The docker image can be downloaded from docker hub using the following command:
`docker pull eawag/sencast:0.2.0`

### Run Tests

In order to test the setup is working the following command can be run which will output a report on the 
functioning of the processors. **This must be run from inside the sencast repository.**

The option `-v /DIAS:/DIAS` maps the input/ output folders to a location outside the container. This should be updated to 
the appropriate location, e.g. `-v /home/user/DIAS:/DIAS`

`docker run -v /DIAS:/DIAS -v $(pwd):/sencast --rm -it eawag/sencast:0.2.0 -e docker.ini -t`

`-e` name of the environment file in `sencast/environments`
`-t` flag to indicate a test should be run 

### Run script

In order to run a parameters file it can be passed to the command as follows using the `-p` flag.

`docker run -v /DIAS:/DIAS -v $(pwd):/sencast --rm -it eawag/sencast:0.2.0 -e docker.ini -p example.ini`

`-p` name of the parameter file in `sencast/parameters`

### Run Interactive Container

Sometimes it is desirable to interact directly with the container, this can be achieved with the following command:

`docker run -v /DIAS:/DIAS -v $(pwd):/sencast --rm -it --entrypoint /bin/bash eawag/sencast:0.2.0`

### Locally build container

`docker build -t eawag/sencast:0.2.0 .`
