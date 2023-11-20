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
conda env create -f ~/sencast/sencast.yml
```
Then create your **environment file** (use environments/example.ini as a template) and test your installation as follows:
```
cd ~/sencast
conda activate sencast
python main.py -t
```
This will output a log of which processors are functioning. After the above steps it is normal that only the image download functions. 
For installation of the processors refer to the full documentation below:

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

As this container contains non-open source code, the pre-build image is only available internally at Eawag. However, external parties can build the image
themselves by including `docker_dependencies/polymer-v4.15.tar.gz` in the repository.

Users should first ensure they have a functioning docker installation.

### Build

The docker image can be built using the following command:

`docker build -t eawag/sencast:0.0.1 .`

### Run Tests

In order to test the setup is working the following command can be run which will output a report on the 
functioning of the processors. This must be run from inside the sencast repository. 

The option `-v /DIAS:/DIAS` maps the input/ output folders to a location outside the container. This should be updated to 
the appropriate location, e.g. `-v /home/user/DIAS:/DIAS`

`docker run -v /DIAS:/DIAS -v $(pwd):/sencast --rm -it eawag/sencast:0.0.1 -e docker.ini -t`

`-e` name of the environment file in `sencast/environments`
`-t` flag to indicate a test should be run 

### Run script

In order to run a parameters file it can be passed to the command as follows using the `-p` flag.

`docker run -v /DIAS:/DIAS -v $(pwd):/sencast --rm -it eawag/sencast:0.0.1 -e docker.ini -p example.ini`

`-p` name of the parameter file in `sencast/parameters`

### Run Interactive Container

Sometimes it is desirable to interact directly with the container, this can be achieved with the following command:

`docker run -v /DIAS:/DIAS -v $(pwd):/sencast --rm -it --entrypoint /bin/bash eawag/sencast:0.0.1`

## CSCS

The following section provides details on how to run Sencast on the supercomputer Piz Daint at CSCS.

### Register for an account

Get access permission to Daint from your local IT Admin.
You will be required to set up multifactor authentication

### Access using Jupyter

- Login at https://jupyter.cscs.ch/
- Select `Node Type = Multicore` 
- Click `Launch Jupyterlab`
- Select `Terminal`

### Access using ssh
This access is only valid for 24 hours after which the process will need to be repeated. For details on how to automate see here: https://user.cscs.ch/access/auth/mfa and for Windows see here: https://user.cscs.ch/access/auth/mfa/windows

- Login at https://sshservice.cscs.ch/
- Click `Get a signed key` follow the instructions and download the private and public key
- Move the keys to your users `.ssh` directory
```commandline
mv /downloads/location/cscs-key-cert.pub ~/.ssh/cscs-key-cert.pub
mv /download/location/cscs-key ~/.ssh/cscs-key
chmod 0600 ~/.ssh/cscs-key
```
- Login to the CSCS entrance server
```commandline
ssh -A username@ela.cscs.ch
```
- Switch to Piz Daint
```commandline
ssh username@daint.cscs.ch
```

### Install Sencast

This step must be completed on the command line after logging into Piz Daint using one of the above methods.

Load the required modules
```commandline
module load daint-mc
module load sarus
```
Clone the repo for sencast to your user area:
```
cd ~
git clone https://github.com/eawag-surface-waters-research/sencast.git
```
Update the envrionment and parameters scripts that you want to run.

Pull the image you want from dockerhub:   
```
srun -C mc -A em09 sarus pull --login eawag/sencast:0.0.1
```
then enter your credentials for the repository (There is no prompt)

`<username>`
`<password>`

The docker image (now for sarus) is automatically saved in ${SCRATCH}/.sarus

If this fails try running the command again.

### Run Sencast

Move to the scratch drive and create an output folder **don't save large amounts of data to user area**
Data stored in the scratch drive is removed after 30 days.
```commandline
cd ${SCRATCH}
mkdir DIAS
```

Create a submission script containing the following (adjust details to match your user) - make sure you are writing to scratch.

`vim run.sh`
```
#!/bin/bash -l
#SBATCH --job-name="sencast"
#SBATCH --account="em09"
#SBATCH --mail-type=ALL
#SBATCH --mail-user=username@eawag.ch
#SBATCH --time=24:00:00
#SBATCH --nodes=1
#SBATCH --ntasks-per-core=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=36
#SBATCH --partition=normal
#SBATCH --constraint=mc
#SBATCH --hint=nomultithread

export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK

module load daint-mc
module load sarus

image='eawag/sencast:0.0.1'
envvars='docker.ini'
params='parameters.ini'
filepath="${SCRATCH}/DIAS"

cd ~/sencast

srun sarus run --mount=type=bind,source=${filepath},destination=/DIAS --mount=type=bind,source=$(pwd),dst=/sencast ${image} -e ${envvars} -p ${params}
```
`:w` save file

`:q` exit vim

Then you can run Sencast:

```
sbatch run.sh
```

See the status of your job:

```commandline
squeue -u username
```

You get an email when the job begins and if it fails. A live log is deposited in the directory from where you start the run.





