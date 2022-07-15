.. _ubuntu18install:

------------------------------------------------------------------------------------------
Ubuntu 18.04, 20.04, 22.04
------------------------------------------------------------------------------------------

Prepare)

Update repositories and installed packages:
.. code-block::
    $ sudo add-apt-repository ppa:deadsnakes/ppa -y
    $ sudo add-apt-repository ppa:ubuntugis/ppa -y
    $ sudo apt update && sudo apt upgrade -y
    $ sudo apt install vim gcc make wget curl git -y
..

In case you have gzip version "jammy 1.10-4ubuntu4 amd64", do this to prevent problems:
.. code-block::
    $ wget http://archive.ubuntu.com/ubuntu/pool/main/g/gzip/gzip_1.10-4ubuntu1.1_amd64.deb && sudo dpkg -i gzip_1.10-4ubuntu1.1_amd64.deb && rm gzip_1.10-4ubuntu1.1_amd64.deb
..

If you want to use graphical tools with WSL1:
.. code-block::
    $ echo "export DISPLAY=:0" >> ~/.bashrc
    $ export DISPLAY=:0
..


1.) sencast: https://renkulab.io/gitlab/odermatt/sentinel-hindcast

In shell do following:
.. code-block::
    $ cd ~
    $ mkdir DIAS
    $ git clone https://renkulab.io/gitlab/odermatt/sentinel-hindcast.git sencast
    $ cd sencast
    $ git checkout <branchname> (if not master)
..

2.) Anaconda:

To install Anaconda, in your shell do following:
.. code-block::
    $ curl https://repo.anaconda.com/archive/Anaconda3-2022.05-Linux-x86_64.sh -o ~/Anaconda3-2022.05-Linux-x86_64.sh && sudo chmod 755 ~/Anaconda3-2022.05-Linux-x86_64.sh && ~/Anaconda3-2022.05-Linux-x86_64.sh && rm ~/Anaconda3-2022.05-Linux-x86_64.sh
        > [Enter]
        > s
        > yes
        > [Enter]
        > yes
    $ echo "export CONDA_HOME=/opt/conda" >> ~/.bashrc
    $ export CONDA_HOME=/opt/conda
..

Create sencast environment:
.. code-block::
    $ source ~/.bashrc
    $ conda env create -f ~/sencast/sencast-37.yml
    $ echo "export CONDA_ENV_HOME=$CONDA_HOME/envs/sencast-37" >> ~/.bashrc
    $ export CONDA_ENV_HOME=$CONDA_HOME/envs/sencast-37
..

3.) SNAP: http://step.esa.int/main/download/

First, uninstall all old versions of SNAP and remove associated data

Then do following:
.. code-block::
    $ cd ~
    $ curl -O http://step.esa.int/downloads/9.0/installers/esa-snap_all_unix_9_0_0.sh && chmod 755 esa-snap_all_unix_9_0_0.sh && bash esa-snap_all_unix_9_0_0.sh && rm esa-snap_all_unix_9_0_0.sh
        [o, Enter]
        [1, Enter]
        [Enter]
        [Enter]
        [n, Enter]
        [n, Enter]
        [n, Enter]
    $ echo "export SNAP_HOME=/opt/snap" >> ~/.bashrc
    $ export SNAP_HOME=/opt/snap
    $ $SNAP_HOME/bin/snap --nosplash --nogui --modules --update-all
    $ $SNAP_HOME/bin/snap --nosplash --nogui --modules --install org.esa.snap.idepix.core org.esa.snap.idepix.probav org.esa.snap.idepix.modis org.esa.snap.idepix.spotvgt org.esa.snap.idepix.landsat8 org.esa.snap.idepix.viirs org.esa.snap.idepix.olci org.esa.snap.idepix.seawifs org.esa.snap.idepix.meris org.esa.snap.idepix.s2msi
    $ echo "#SNAP configuration 's3tbx'" >> ~/.snap/etc/s3tbx.properties
    $ echo "#Fri Mar 27 12:55:00 CET 2020" >> ~/.snap/etc/s3tbx.properties
    $ echo "s3tbx.reader.olci.pixelGeoCoding=true" >> ~/.snap/etc/s3tbx.properties
    $ echo "s3tbx.reader.meris.pixelGeoCoding=true" >> ~/.snap/etc/s3tbx.properties
    $ echo "s3tbx.reader.slstrl1b.pixelGeoCodings=true" >> ~/.snap/etc/s3tbx.properties
..

Note: there are many strange error messages, but it seems to work in the end when updating and installing plugins

To remove warning "WARNING: org.esa.snap.dataio.netcdf.util.MetadataUtils: Missing configuration property ‘snap.dataio.netcdf.metadataElementLimit’. Using default (100).":
.. code-block::
    $ echo "" >> $SNAP_HOME/etc/snap.properties
    $ echo "# NetCDF options" >> $SNAP_HOME/etc/snap.properties
    $ echo "snap.dataio.netcdf.metadataElementLimit=10000" >> $SNAP_HOME/etc/snap.properties
..

To remove warning "SEVERE: org.esa.s2tbx.dataio.gdal.activator.GDALDistributionInstaller: The environment variable LD_LIBRARY_PATH is not set. It must contain the current folder '.'."
.. code-block::
    $ echo "export LD_LIBRARY_PATH=." >> ~/.bashrc
..


5.) polymer: https://forum.hygeos.com/viewforum.php?f=5

Somehow bring the polymer install tar.gz file to your system
.. code-block::
    $ tar -xvzf ~/polymer-v4.14.tar.gz
    $ cd polymer-v4.14
    $ conda activate sencast-37
    $ make all
    $ cp -avr ~/polymer-v4.14/polymer $CONDA_ENV_HOME/lib/python3.7/site-packages/polymer
    $ cp -avr ~/polymer-v4.14/auxdata $CONDA_ENV_HOME/lib/python3.7/site-packages/auxdata
..

Note: On some systems you will need following change: In the file $CONDA_ENV_HOME/lib/python3.7/site-packages/polymer/level1_landsat8.py replace line 13 "import osr" by "from osgeo import osr"
	

6.) l8_angles: https://www.usgs.gov/core-science-systems/nli/landsat/solar-illumination-and-sensor-viewing-angle-coefficient-files?qt-science_support_page_related_con=1#qt-science_support_page_related_con
	
To use polymer with L8 data you must install l8_angles according to: https://forum.hygeos.com/viewtopic.php?f=7&t=136

In shell do following:
.. code-block::
    $ curl https://landsat.usgs.gov/sites/default/files/documents/L8_ANGLES_2_7_0.tgz -o ~/setup/L8_ANGLES_2_7_0.tgz
    $ tar -xvzf ~/setup/L8_ANGLES_2_7_0.tgz --directory ~/
    $ cd ~/l8_angles
    $ make
..

Configure path to l8_angles in your environment file.


7.) CDS API: https://cds.climate.copernicus.eu/api-how-to
.. code-block::
	$ echo "url: https://cds.climate.copernicus.eu/api/v2" > ~/.cdsapirc
	$ echo key: [uid]:[api-key] >> ~/.cdsapirc (Note: replace [uid] and [api-key] by your actual credentials, see https://cds.climate.copernicus.eu/api-how-to )
	$ chmod 600 ~/.cdsapirc
..

8.) NASA Earthdata API: https://wiki.earthdata.nasa.gov/display/EL/How+To+Access+Data+With+cURL+And+Wget

Have a NASA Earthdata account ready, otherwise create one: https://urs.earthdata.nasa.gov/

In shell do following:
    $ touch ~/.netrc
    $ touch ~/.urs_cookies
    $ echo "machine urs.earthdata.nasa.gov login <earthdata user> password <earthdata password>" >> ~/.netrc
    $ chmod 0600 ~/.netrc

9.) Acolite: https://github.com/acolite/acolite.git

In shell do following:
    $ cd $CONDA_ENV_HOME/lib/python3.7/site-packages
    $ git clone https://github.com/acolite/acolite.git

Edit the file acolite_l2w.py and comment-out all usages (and import) of "skimage".
    Currently lines 23, 898, 909, 910, 911

In acolite/config/defaults.txt, row 28 set setting geometry_type=gpt (to avoid a batch processing but as of Dec. '21)
Configure your Acolite path in you environment file.


10.) FLUO:

Somehow bring the installation file snap-eum-fluo-1.0.nbm to the directory ~/setup/

In shell do following:
    $ mkdir ~/setup/snap-eum-fluo-1.0
    $ unzip snap-eum-fluo-1.0.nbm -d ~/setup/snap-eum-fluo-1.0
    $ cp ~/setup/snap-eum-fluo-1.0/netbeans/* ~/.snap/system


11.) iCOR: https://remotesensing.vito.be/case/icor

In shell do following:
    $ wget https://ext.vito.be/icor/icor_install_ubuntu_20_04_x64_3.0.0.bin
    $ chmod 755 icor_install_ubuntu_20_04_x64_3.0.0.bin
    $ sudo mkdir /opt/vito
    $ sudo chown sencast:sencast /opt/vito
    $ ./icor_install_ubuntu_20_04_x64_3.0.0.bin

Installation of SNAP plugin only necessairy if you want to use iCOR from SNAP Desktop:
    $ mkdir ~/setup/iCOR-landsat8-sta-3.0.0-LINUX
    $ mkdir ~/setup/iCOR-sentinel2-sta-3.0.0-LINUX
    $ mkdir ~/setup/iCOR-sentinel3-sta-3.0.0-LINUX
    $ unzip /opt/vito/icor/sta/iCOR-landsat8-sta-3.0.0-LINUX.nbm -d ~/setup/iCOR-landsat8-sta-3.0.0-LINUX
    $ unzip /opt/vito/icor/sta/iCOR-sentinel2-sta-3.0.0-LINUX.nbm -d ~/setup/iCOR-sentinel2-sta-3.0.0-LINUX
    $ unzip /opt/vito/icor/sta/iCOR-sentinel3-sta-3.0.0-LINUX.nbm -d ~/setup/iCOR-sentinel3-sta-3.0.0-LINUX
    $ cp -r ~/setup/iCOR-landsat8-sta-3.0.0-LINUX/netbeans/* ~/.snap/system
    $ cp -r ~/setup/iCOR-sentinel2-sta-3.0.0-LINUX/netbeans/* ~/.snap/system
    $ cp -r ~/setup/iCOR-sentinel3-sta-3.0.0-LINUX/netbeans/* ~/.snap/system

Configure your iCOR path in you environment file.


12.) LSWT:

Somehow bring the installation file snap-musenalp-processor-1.0.5.nbm to the directory ~/setup/

In shell do following:
    $ ~/setup/snap-musenalp-processor-1.0.5
    $ unzip snap-musenalp-processor-1.0.5.nbm -d ~/setup/snap-musenalp-processor-1.0.5
    $ cp ~/setup/snap-musenalp-processor-1.0.5/netbeans/* ~/.snap/system
