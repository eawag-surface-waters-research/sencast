.. _linux:

------------------------------------------------------------------------------------------
Linux
------------------------------------------------------------------------------------------

Clone Sencast
----------------

In shell do following::

    $ cd ~
    $ mkdir DIAS
    $ git clone https://github.com/eawag-surface-waters-research/sencast.git
    $ cd sencast
    $ git checkout <branchname> (if not master)


Install Python Environment
---------------------------

We use Anaconda because it delivers all packages with required external libraries. With PIP you would have to install some GDAL requirements manually.

If you do not already have Anaconda installed you can find installation instructions here: https://docs.anaconda.com/anaconda/install/

Create sencast environment::

    $ cd sencast
    $ conda env create -f sencast.yml
    $ echo "export CONDA_ENV_HOME=$CONDA_HOME/envs/sencast" >> ~/.bashrc
    $ export CONDA_ENV_HOME=$CONDA_HOME/envs/sencast

Install SNAP
-------------

You can find installation instructions for SNAP here: https://step.esa.int/main/download/snap-download/

For command line instructions see below:

First, uninstall all old versions of SNAP and remove associated data. You may need to update the version of SNAP to the latest one in the code below. ::

    $ cd ~
    $ curl -O http://step.esa.int/downloads/9.0/installers/esa-snap_all_unix_9_0_0.sh && chmod 755 esa-snap_all_unix_9_0_0.sh && bash esa-snap_all_unix_9_0_0.sh && rm esa-snap_all_unix_9_0_0.sh

This will launch a interactive window where you can install the SNAP software.

You need to add the path to gpt to the environment file it is typically something like /home/username/snap/bin/gpt

IDEPIX
--------

Idepix is a plugin from SNAP that can be installed by opening SNAP and going Tools -> Plugins. From the available
plugins download all the Idepix plugins. They will be available in Sencast once you restart SNAP.

POLYMER
--------

Request a polymer install tar.gz file from Hygeos, then do following::

    $ git clone --depth 1 --branch master https://github.com/hygeos/polymer.git
    $ cd polymer
    $ conda activate sencast
    $ make all
    $ cp -avr polymer $CONDA_ENV_HOME/lib/python3.7/site-packages/polymer
    $ cp -avr auxdata $CONDA_ENV_HOME/lib/python3.7/site-packages/auxdata

Note: On some systems you will need following change: In the file $CONDA_ENV_HOME/lib/python3.7/site-packages/polymer/level1_landsat8.py replace line 13 "import osr" by "from osgeo import osr"

To use polymer with L8 data you must install l8_angles according to: https://forum.hygeos.com/viewtopic.php?f=7&t=136

In shell do following::

    $ cd ~
    $ wget https://landsat.usgs.gov/sites/default/files/documents/L8_ANGLES_2_7_0.tgz
    $ tar -xvzf ~/setup/L8_ANGLES_2_7_0.tgz
    $ cd ~/l8_angles
    $ make

Configure path to l8_angles in your environment file.


Acolite
--------

In shell do following::

    $ cd $CONDA_ENV_HOME/lib/python3.7/site-packages
    $ git clone --depth 1 --branch main https://github.com/acolite/acolite.git
    $ cd acolite
    $ git reset --hard e7cb944

Configure your Acolite path in you environment file.


OCSMART
--------

Download the OCSMART linux package from http://www.rtatmocn.com/oc-smart/

Unzip the package somewhere and then add a path the the folder that contains OCSMART.py to your environment file

FLUO
-----

Somehow bring the installation file snap-eum-fluo-1.0.nbm to the directory ~/setup/

In shell do following::

    $ wget https://www.dropbox.com/s/ub3i66l4zqw51cs/snap-eum-fluo-1.0.nbm && unzip ~/snap-eum-fluo-1.0.nbm -d ~/snap-eum-fluo-1.0 && rm ~/snap-eum-fluo-1.0.nbm
    $ cp -r ~/snap-eum-fluo-1.0/netbeans/* ~/.snap/system
    $ rm -rf ~/snap-eum-fluo-1.0


iCOR
-----

In shell do following::

    $ cd ~
    $ wget https://ext.vito.be/icor/icor_install_ubuntu_20_04_x64_3.0.0.bin && chmod 755 icor_install_ubuntu_20_04_x64_3.0.0.bin && sudo mkdir /home/username/vito && sudo ./icor_install_ubuntu_20_04_x64_3.0.0.bin && rm icor_install_ubuntu_20_04_x64_3.0.0.bin

Installation of SNAP plugin only necessary if you want to use iCOR from SNAP Desktop::

    $ mkdir ~/setup/iCOR-landsat8-sta-3.0.0-LINUX
    $ mkdir ~/setup/iCOR-sentinel2-sta-3.0.0-LINUX
    $ mkdir ~/setup/iCOR-sentinel3-sta-3.0.0-LINUX
    $ unzip /home/username/vito/icor/sta/iCOR-landsat8-sta-3.0.0-LINUX.nbm -d ~/setup/iCOR-landsat8-sta-3.0.0-LINUX
    $ unzip /home/username/vito/icor/sta/iCOR-sentinel2-sta-3.0.0-LINUX.nbm -d ~/setup/iCOR-sentinel2-sta-3.0.0-LINUX
    $ unzip /home/username/vito/icor/sta/iCOR-sentinel3-sta-3.0.0-LINUX.nbm -d ~/setup/iCOR-sentinel3-sta-3.0.0-LINUX
    $ cp -r ~/setup/iCOR-landsat8-sta-3.0.0-LINUX/netbeans/* ~/.snap/system
    $ cp -r ~/setup/iCOR-sentinel2-sta-3.0.0-LINUX/netbeans/* ~/.snap/system
    $ cp -r ~/setup/iCOR-sentinel3-sta-3.0.0-LINUX/netbeans/* ~/.snap/system

Configure your iCOR path in you environment file.

Sen2Cor
---------

First you must try to run it from SNAP GUI. It will then prompt you to install some bundle. Only after that the processor will work from GPT. https://forum.step.esa.int/t/error-processing-template-after-execution-for-parameter-postexecutetemplate/6591


LSWT
-----

Somehow bring the installation file snap-musenalp-processor-1.0.5.nbm to the directory ~/setup/

In shell do following::

    $ ~/setup/snap-musenalp-processor-1.0.5
    $ unzip snap-musenalp-processor-1.0.5.nbm -d ~/setup/snap-musenalp-processor-1.0.5
    $ cp ~/setup/snap-musenalp-processor-1.0.5/netbeans/* ~/.snap/system

