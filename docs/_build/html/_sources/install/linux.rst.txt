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

In shell do following ::

    $ git clone --depth 1 --branch master https://github.com/hygeos/polymer.git
    $ cd polymer
    $ conda activate sencast
    $ make all
    $ cp -avr polymer $CONDA_ENV_HOME/lib/python3.7/site-packages/polymer
    $ cp -avr auxdata $CONDA_ENV_HOME/lib/python3.7/site-packages/auxdata



Acolite
--------

In shell do following::

    $ git clone --depth 1 --branch main https://github.com/acolite/acolite.git

Configure your Acolite path in you environment file.


OCSMART
--------

Download the OCSMART linux package from http://www.rtatmocn.com/oc-smart/

Unzip the package somewhere and then add a path the the folder that contains OCSMART.py to your environment file
