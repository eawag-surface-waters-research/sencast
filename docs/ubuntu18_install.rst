.. _ubuntu18install:

------------------------------------------------------------------------------------------
Ubuntu 18.04, 20.04
------------------------------------------------------------------------------------------

Prepare)

	Update repositories and installed packages:
		$ sudo apt update
		$ sudo apt upgrade
		$ sudo apt install default-jdk
		$ java -version
		$ echo export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64 >> ~/.bashrc
		$ sudo apt install maven
		$ mvn -version
		$ sudo apt install unzip zip
		$ mkdir -p ~/setup
	
	Restart your shell session


1.) Anaconda: https://problemsolvingwithpython.com/01-Orientation/01.05-Installing-Anaconda-on-Linux/

	In shell do following:
		$ curl https://repo.anaconda.com/archive/Anaconda3-2021.05-Linux-x86_64.sh -o ~/setup/Anaconda3-2021.05-Linux-x86_64.sh
		$ bash ~/setup/Anaconda3-2021.05-Linux-x86_64.sh
			>>> [Enter]
			[s]
			>>> yes
			>>> [Enter]
			>>> yes
		$ sudo reboot
		$ conda config --set auto_activate_base false
		$ echo export CONDA_HOME=~/anaconda3 >> ~/.bashrc
	
	Restart your shell session


2. Anaconda: create sencast environment

	In shell do following:
		$ conda config --add channels conda-forge
		$ conda config --append channels bioconda
		$ conda create --name sencast python=3 cartopy=0.19 cdsapi=0.5 colour-science=0.3 cython=0.29 ecmwfapi=1.4 gdal=3.2 glymur=0.9 h5py=3.3 haversine=2.5 matplotlib=3.4 netcdf4=1.5 pkgconfig=1.5 pyepr=1.1 pygrib=2.1 pyhdf=0.10.3 pyproj=3.1 pyresample=1.21 rasterio=1.2 scikit-learn=0.24 statsmodels=0.12 tensorflow=1.15 tensorflow-probability=0.7 wheel=0.37 xarray=0.19 xlrd=1.2
		$ echo export CONDA_ENV_HOME=$CONDA_HOME/envs/sencast >> ~/.bashrc
		$ echo export CONDA_ENV_SP=$CONDA_HOME/envs/sencast/lib/python3.9/site-packages >> ~/.bashrc
	
	Restart your shell session


3.) SNAP: http://step.esa.int/main/download/

	Uninstall all old versions of SNAP and remove associated data

	In shell do following:
		$ curl http://step.esa.int/downloads/8.0/installers/esa-snap_all_unix_8_0.sh -o ~/setup/esa-snap_all_unix_8_0.sh
		$ sudo chmod 755 ~/setup/esa-snap_all_unix_8_0.sh
		$ bash ~/setup/esa-snap_all_unix_8_0.sh
			[o, Enter]
			[1, Enter]
			[Enter]
			[Enter]
			[n, Enter]
			[n, Enter]
			[n, Enter]
		$ echo export SNAP_HOME=~/snap >> ~/.bashrc
		$ $SNAP_HOME/bin/snap --nosplash --nogui --modules --update-all
		$ $SNAP_HOME/bin/snap --nosplash --nogui --modules --install org.esa.snap.idepix.core org.esa.snap.idepix.probav org.esa.snap.idepix.modis org.esa.snap.idepix.spotvgt org.esa.snap.idepix.landsat8 org.esa.snap.idepix.viirs org.esa.snap.idepix.olci org.esa.snap.idepix.seawifs org.esa.snap.idepix.meris org.esa.snap.idepix.s2msi org.esa.chris.chris.noise.reduction org.esa.snap.snap.zarr org.esa.s2tbx.s2tbx.otb.adapters.kit org.esa.s2tbx.Pansharpening.bayes org.esa.s2tbx.s2tbx.gdal.reader.ui org.esa.chris.chris.atmospheric.correction org.esa.chris.chris.cloud.screening org.esa.s2tbx.sen2three org.esa.snap.snap.jython org.esa.s2tbx.Segmentation.cc org.esa.chris.chris.atmospheric.correction.lut org.esa.s2tbx.Pansharpening.rcs org.esa.chris.chris.toa.reflectance.computation org.esa.chris.chris.geometric.correction org.esa.s2tbx.MultivariateAlterationDetector org.esa.snap.core.gpf.operators.tooladapter.snaphu org.esa.s2tbx.Pansharpening.lmvm org.esa.chris.chris.util org.esa.s2tbx.Segmentation.meanshift org.esa.snap.snap.product.library.ui org.esa.chris.chris.kit org.esa.s2tbx.SFSTextureExtraction org.esa.sen2coral.sen2coral.algorithms.ui org.esa.s2tbx.Segmentation.watershed org.esa.s2tbx.Segmentation.mprofiles org.esa.chris.chris.reader
		$ echo "#SNAP configuration 's3tbx'" >> ~/.snap/etc/s3tbx.properties
		$ echo "#Fri Mar 27 12:55:00 CET 2020" >> ~/.snap/etc/s3tbx.properties
		$ echo "s3tbx.reader.olci.pixelGeoCoding=true" >> ~/.snap/etc/s3tbx.properties
		$ echo "s3tbx.reader.meris.pixelGeoCoding=true" >> ~/.snap/etc/s3tbx.properties
		$ echo "s3tbx.reader.slstrl1b.pixelGeoCodings=true" >> ~/.snap/etc/s3tbx.properties
		$ echo "s3tbx.landsat.readAs=reflectance" >> ~/.snap/etc/s3tbx.properties
	
	Restart your shell session

	Note: there are many strange error messages, but it seems to work in the end when updating and installing plugins

	To remove warning "WARNING: org.esa.snap.dataio.netcdf.util.MetadataUtils: Missing configuration property ‘snap.dataio.netcdf.metadataElementLimit’. Using default (100).":
		$ echo "" >> $SNAP_HOME/etc/snap.properties
		$ echo "# NetCDF options" >> $SNAP_HOME/etc/snap.properties
		$ echo "snap.dataio.netcdf.metadataElementLimit=10000" >> $SNAP_HOME/etc/snap.properties

	To remove warning "SEVERE: org.esa.s2tbx.dataio.gdal.activator.GDALDistributionInstaller: The environment variable LD_LIBRARY_PATH is not set. It must contain the current folder '.'."
		$ echo export LD_LIBRARY_PATH=. >> ~/.bashrc
	
	Restart your shell session


4.) sencast: https://renkulab.io/gitlab/odermatt/sentinel-hindcast

	In shell do following:
		$ cd ~
		$ git clone https://renkulab.io/gitlab/odermatt/sentinel-hindcast.git
		$ cd sentinel-hindcast
		$ git checkout <branchname> (if not master)

5.) Local DIAS:

	In shell do following:
		$ sudo mkdir /opt/DIAS
		$ sudo chown sencast:sencast /opt/DIAS
	
	Configure your local DIAS path in your environment file.


5.) Python - jpy: https://github.com/jpy-consortium/jpy/blob/master/README.md

	In shell do following:
		$ cd $CONDA_ENV_SP
		$ git clone https://github.com/jpy-consortium/jpy
		$ cd jpy
		$ conda activate sencast
		$ python setup.py build maven bdist_wheel


6.) Python - snappy: https://github.com/senbox-org/snap-engine/blob/master/snap-python/src/main/resources/README.md

	In shell do following:
		($ sudo ln -s ../../lib64/libnsl.so.2 /usr/lib64/libnsl.so)
		($ sudo ln -s ../../lib64/libnsl.so.2.0.0 /usr/lib64/libnsl.so.1)
		$ mkdir -p ~/.snap/snap-python/snappy
		$ cp -v $CONDA_ENV_SP/jpy/dist/*.whl ~/.snap/snap-python/snappy
		$ bash $SNAP_HOME/bin/snappy-conf $CONDA_ENV_HOME/bin/python ~/.snap/snap-python
		$ conda activate sencast
		$ python ~/.snap/snap-python/snappy/setup.py install --user
		$ cp -avr ~/.snap/snap-python/build/lib/snappy $CONDA_ENV_SP/snappy
		$ cp -avr ~/.snap/snap-python/snappy/tests $CONDA_ENV_SP/snappy/tests
		$ cd $CONDA_ENV_SP/snappy/tests
		$ curl https://raw.githubusercontent.com/bcdev/eo-child-gen/master/child-gen-N1/src/test/resources/com/bc/childgen/MER_RR__1P.N1 -o MER_RR__1P.N1
		$ python test_snappy_mem.py
		$ python test_snappy_perf.py
		$ python test_snappy_product.py


7.) Python - polymer: https://forum.hygeos.com/viewforum.php?f=5

	From a computer in the eawag network, copy the polymer zip file to the linux server:
		> scp -i .ssh\cloudferro.key \\eawag\Abteilungs-Projekte\Surf\surf-DD\RS\Software\Polymer\polymer-v4.13.tar.gz eouser@45.130.29.115:/home/eouser/setup

	In shell do following:
		$ tar -xvzf ~/setup/polymer-v4.13.tar.gz --directory ~/setup/
		$ cd ~/setup/polymer-v4.13
		$ conda activate sencast
		($ sudo apt install wget)
		($ sudo apt install make)
		($ sudo apt install gcc)
		$ make all
		$ cp -avr ~/setup/polymer-v4.13/polymer $CONDA_ENV_SP/polymer
		$ cp -avr ~/setup/polymer-v4.13/auxdata $CONDA_ENV_SP/auxdata
		
	In the file $CONDA_ENV_SP/polymer/level1_landsat8.py replace line 13 "import osr" by "from osgeo import osr"
	

8.) l8_angles: https://www.usgs.gov/core-science-systems/nli/landsat/solar-illumination-and-sensor-viewing-angle-coefficient-files?qt-science_support_page_related_con=1#qt-science_support_page_related_con
	
	To use polymer with L8 data you must install l8_angles according to: https://forum.hygeos.com/viewtopic.php?f=7&t=136
	
	In shell do following:
		$ curl https://landsat.usgs.gov/sites/default/files/documents/L8_ANGLES_2_7_0.tgz -o ~/setup/L8_ANGLES_2_7_0.tgz
		$ tar -xvzf ~/setup/L8_ANGLES_2_7_0.tgz --directory ~/
		$ cd ~/l8_angles
		$ make
	
	Configure the l8_angles in your environment file.


8.) CDS API: https://cds.climate.copernicus.eu/api-how-to

	Have a Copernicus Climate account ready, otherwise create one: https://cds.climate.copernicus.eu/

	In shell do following:
		$ echo "url: https://cds.climate.copernicus.eu/api/v2" >> ~/.cdsapirc
		$ echo key: [uid]:[api-key] >> ~/.cdsapirc (Note: replace [uid] and [api-key] by your actual credentials, see https://cds.climate.copernicus.eu/api-how-to )
		$ chmod 600 ~/.cdsapirc


9.) NASA Earthdata API: https://wiki.earthdata.nasa.gov/display/EL/How+To+Access+Data+With+cURL+And+Wget

	Have a NASA Earthdata account ready, otherwise create one: https://urs.earthdata.nasa.gov/

	In shell do following:
		$ touch ~/.netrc
		$ echo "machine urs.earthdata.nasa.gov login <earthdata user> password <earthdata password>" >> ~/.netrc
		$ chmod 0600 ~/.netrc
		$ touch ~/.urs_cookies


10.) Cronjob for datalakes: https://linux4one.com/how-to-set-up-cron-job-on-centos-8/

	In shell do following:
		$ mkdir -p /prj/datalakes/log
		$ curl https://renkulab.io/gitlab/odermatt/sentinel-hindcast/raw/snap7compatibility/parameters/datalakes_sui_S3.ini?inline=false -o /prj/datalakes/datalakes_sui_S3.ini
		$ chmod 755 /prj/sentinel-hindcast/scripts/datalakes.sh
		$ crontab -l | { cat; echo "0 20 * * * nohup /prj/sentinel-hindcast/scripts/datalakes.sh &"; } | crontab -


12.) Acolite: https://github.com/acolite/acolite.git

	In shell do following:
		$ cd ~
		$ git clone https://github.com/acolite/acolite.git
	
	Edit the file acolite_l2w.py and comment-out all usages (and import) of "skimage".
		Currently lines 23, 898, 909, 910, 911
	
	Configure your Acolite path in you environment file.


13.) FLUO:

	Somehow bring the installation file snap-eum-fluo-1.0.nbm to the directory ~/setup/

	In shell do following:
		$ mkdir ~/setup/snap-eum-fluo-1.0
		$ unzip snap-eum-fluo-1.0.nbm -d ~/setup/snap-eum-fluo-1.0
		$ cp ~/setup/snap-eum-fluo-1.0/netbeans/* ~/.snap/system


14.) iCOR: https://remotesensing.vito.be/case/icor

	Somehow bring the installation file icor_install_ubuntu_20_04_x64_3.0.0.bin to the directory ~/setup/

	In shell do following:
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


15.) LSWT:

	Somehow bring the installation file snap-musenalp-processor-1.0.5.nbm to the directory ~/setup/

	In shell do following:
		$ ~/setup/snap-musenalp-processor-1.0.5
		$ unzip snap-musenalp-processor-1.0.5.nbm -d ~/setup/snap-musenalp-processor-1.0.5
		$ cp ~/setup/snap-musenalp-processor-1.0.5/netbeans/* ~/.snap/system
