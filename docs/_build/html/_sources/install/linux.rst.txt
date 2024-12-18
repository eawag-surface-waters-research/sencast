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
        [o, Enter]
        [1, Enter]
        [Enter]
        [Enter]
        [n, Enter]
        [n, Enter]
        [n, Enter]
    $ echo "export SNAP_HOME=/home/username/snap" >> ~/.bashrc
    $ export SNAP_HOME=/home/username/snap
    $ $SNAP_HOME/bin/snap --nosplash --nogui --modules --update-all
    $ $SNAP_HOME/bin/snap --nosplash --nogui --modules --install org.esa.snap.idepix.core org.esa.snap.idepix.probav org.esa.snap.idepix.modis org.esa.snap.idepix.spotvgt org.esa.snap.idepix.landsat8 org.esa.snap.idepix.viirs org.esa.snap.idepix.olci org.esa.snap.idepix.seawifs org.esa.snap.idepix.meris org.esa.snap.idepix.s2msi
    $ echo "#SNAP configuration 's3tbx'" >> ~/.snap/etc/s3tbx.properties
    $ echo "#Fri Mar 27 12:55:00 CET 2020" >> ~/.snap/etc/s3tbx.properties
    $ echo "s3tbx.reader.olci.pixelGeoCoding=true" >> ~/.snap/etc/s3tbx.properties
    $ echo "s3tbx.reader.meris.pixelGeoCoding=true" >> ~/.snap/etc/s3tbx.properties
    $ echo "s3tbx.reader.slstrl1b.pixelGeoCodings=true" >> ~/.snap/etc/s3tbx.properties

Note: if you encounter any strange error message with X11GraphicsEnvironment, try unsetting the DISPLAY variable (and don't question why)

Note: there are many strange error messages, but it seems to work in the end when updating and installing plugins

To remove warning "WARNING: org.esa.snap.dataio.netcdf.util.MetadataUtils: Missing configuration property ‘snap.dataio.netcdf.metadataElementLimit’. Using default (100)."::

    $ echo "" >> $SNAP_HOME/etc/snap.properties
    $ echo "# NetCDF options" >> $SNAP_HOME/etc/snap.properties
    $ echo "snap.dataio.netcdf.metadataElementLimit=10000" >> $SNAP_HOME/etc/snap.properties

To remove warning "SEVERE: org.esa.s2tbx.dataio.gdal.activator.GDALDistributionInstaller: The environment variable LD_LIBRARY_PATH is not set. It must contain the current folder '.'."::

    $ echo "export LD_LIBRARY_PATH=." >> ~/.bashrc

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


CDS API
________

Setup credentials for CDS API::

	$ echo "url: https://cds.climate.copernicus.eu/api/v2" > ~/.cdsapirc
	$ echo key: [uid]:[api-key] >> ~/.cdsapirc (Note: replace [uid] and [api-key] by your actual credentials, see https://cds.climate.copernicus.eu/api-how-to )
	$ chmod 600 ~/.cdsapirc


NASA Earthdata API
--------------------

Have a NASA Earthdata account ready, otherwise create one: https://urs.earthdata.nasa.gov/

In shell do following::

    $ touch ~/.netrc
    $ touch ~/.urs_cookies
    $ echo "machine urs.earthdata.nasa.gov login <earthdata user> password <earthdata password>" >> ~/.netrc
    $ chmod 0600 ~/.netrc


Acolite
--------

In shell do following::

    $ cd $CONDA_ENV_HOME/lib/python3.7/site-packages
    $ git clone --depth 1 --branch main https://github.com/acolite/acolite.git
    $ cd acolite
    $ git reset --hard e7cb944

Configure your Acolite path in you environment file.


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

