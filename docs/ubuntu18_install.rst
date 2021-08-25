.. _ubuntu18install:

------------------------------------------------------------------------------------------
Ubuntu 18
------------------------------------------------------------------------------------------


1.) OpenJdk: https://dzone.com/articles/installing-openjdk-11-on-ubuntu-1804-for-real (if not installed already):

	In shell do following:
		$ sudo apt-get install default-jdk
			> y
		$ java -version
		  Needs to be version 11java

2.) Maven: https://www.javahelps.com/2017/10/install-apache-maven-on-linux.html

	In shell do following:
		$ mkdir -p ~/setup
		$ curl http://mirror.easyname.ch/apache/maven/maven-3/3.6.3/binaries/apache-maven-3.6.3-bin.tar.gz -o ~/setup/apache-maven-3.6.3-bin.tar.gz
		$ sudo tar -xvzf ~/setup/apache-maven-3.6.3-bin.tar.gz --directory /home/jamesrunnalls
		$ sudo su -c 'echo "M2_HOME=/home/jamesrunnalls/apache-maven-3.6.3/" >> /etc/environment'
		$ sudo update-alternatives --install "/usr/bin/mvn" "mvn" "/home/jamesrunnalls/apache-maven-3.6.3/bin/mvn" 0
		$ sudo update-alternatives --set mvn /home/jamesrunnalls/apache-maven-3.6.3/bin/mvn
		$ mvn -version
		$ sudo reboot


3.) Anaconda: https://problemsolvingwithpython.com/01-Orientation/01.05-Installing-Anaconda-on-Linux/

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


4. Anaconda: create sencast-39 environment

	In shell do following:
		$ conda config --add channels conda-forge
		$ conda create --name sencast-39 python=3.9 gdal cartopy netcdf4 cython pkgconfig statsmodels matplotlib haversine rasterio pyproj scikit-image pyresample h5py pyhdf pyepr glymur pygrib cdsapi xarray xlrd bioconda::ecmwfapi


5.) SNAP: http://step.esa.int/main/download/

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
		$ ~/snap/bin/snap --nosplash --nogui --modules --update-all
		$ ~/snap/bin/snap --nosplash --nogui --modules --install org.esa.snap.idepix.core org.esa.snap.idepix.probav org.esa.snap.idepix.modis org.esa.snap.idepix.spotvgt org.esa.snap.idepix.landsat8 org.esa.snap.idepix.viirs org.esa.snap.idepix.olci org.esa.snap.idepix.seawifs org.esa.snap.idepix.meris org.esa.snap.idepix.s2msi
		$ echo "#SNAP configuration 's3tbx'" >> ~/.snap/etc/s3tbx.properties
		$ echo "#Fri Mar 27 12:55:00 CET 2020" >> ~/.snap/etc/s3tbx.properties
		$ echo "s3tbx.reader.olci.pixelGeoCoding=true" >> ~/.snap/etc/s3tbx.properties
		$ echo "s3tbx.reader.meris.pixelGeoCoding=true" >> ~/.snap/etc/s3tbx.properties
		$ echo "s3tbx.reader.slstrl1b.pixelGeoCodings=true" >> ~/.snap/etc/s3tbx.properties
		$ echo "s3tbx.landsat.readAs=reflectance" >> ~/.snap/etc/s3tbx.properties

	Note: there are many strange error messages, but it seems to work in the end when updating and installing plugins

	To remove warning "WARNING: org.esa.snap.dataio.netcdf.util.MetadataUtils: Missing configuration property ‘snap.dataio.netcdf.metadataElementLimit’. Using default (100).":
		$ echo "" >> ~/snap/etc/snap.properties
		$ echo "# NetCDF options" >> ~/snap/etc/snap.properties
		$ echo "snap.dataio.netcdf.metadataElementLimit=10000" >> ~/snap/etc/snap.properties

	To remove warning "SEVERE: org.esa.s2tbx.dataio.gdal.activator.GDALDistributionInstaller: The environment variable LD_LIBRARY_PATH is not set. It must contain the current folder '.'."
		$ sudo su -c 'echo "LD_LIBRARY_PATH=." >> /etc/environment'


6.) Python - jpy: https://github.com/bcdev/jpy/blob/master/README.md

	In shell do following:
		$ sudo apt-get install python-setuptools
		$ cd ~/anaconda3/envs/sencast-39/lib/python3.9/site-packages
		$ git clone https://github.com/bcdev/jpy.git
		$ cd jpy
		$ conda activate sencast-39
		$ conda install -c conda-forge wheel
		$ python get-pip.py
		$ python setup.py build maven bdist_wheel


7.) Python - snappy: https://github.com/senbox-org/snap-engine/blob/master/snap-python/src/main/resources/README.md

	In shell do following:
		a$ sudo ln -s ../../lib64/libnsl.so.2 /usr/lib64/libnsl.so
		a$ sudo ln -s ../../lib64/libnsl.so.2.0.0 /usr/lib64/libnsl.so.1
		$ mkdir -p ~/.snap/snap-python/snappy
		$ cp ~/anaconda3/envs/sencast-39/lib/python3.9/site-packages/jpy/dist/*.whl ~/.snap/snap-python/snappy
		$ bash ~/snap/bin/snappy-conf ~/anaconda3/envs/sencast-39/bin/python ~/.snap/snap-python
		$ conda activate sencast-39
		$ python ~/.snap/snap-python/snappy/setup.py install --user
		$ cp -avr ~/.snap/snap-python/build/lib/snappy ~/anaconda3/envs/sencast-39/lib/python3.9/site-packages/snappy
		$ cp -avr ~/.snap/snap-python/snappy/tests ~/anaconda3/envs/sencast-39/lib/python3.9/site-packages/snappy/tests
		$ cd ~/anaconda3/envs/sencast-39/lib/python3.9/site-packages/snappy/tests
		$ curl https://raw.githubusercontent.com/bcdev/eo-child-gen/master/child-gen-N1/src/test/resources/com/bc/childgen/MER_RR__1P.N1 -o MER_RR__1P.N1
		$ python test_snappy_mem.py
		$ python test_snappy_perf.py
		$ python test_snappy_product.py


8.) Python - polymer: https://forum.hygeos.com/viewforum.php?f=5

	From a computer in the eawag network, copy the polymer zip file to the linux server:
		> scp -i .ssh\cloudferro.key \\eawag\Abteilungs-Projekte\Surf\surf-DD\RS\Software\Polymer\polymer-v4.13.tar.gz eouser@45.130.29.115:/home/eouser/setup

	In shell do following:
		$ tar -xvzf ~/setup/polymer-v4.13.tar.gz --directory ~/setup/
		$ cd ~/setup/polymer-v4.13
		$ conda activate sencast-39
		$ sudo apt-get install wget
		$ make all
		$ cp -avr ~/setup/polymer-v4.13/polymer ~/anaconda3/envs/sencast-39/lib/python3.9/site-packages/polymer
		$ cp -avr ~/setup/polymer-v4.13/auxdata ~/anaconda3/envs/sencast-39/lib/python3.9/site-packages/auxdata


9.) sentinel-hindcast: https://renkulab.io/gitlab/odermatt/sentinel-hindcast

	In shell do following:
		$ cd /prj
		$ sudo chmod 777 /prj
		$ mkdir /prj/DIAS
		$ git clone https://renkulab.io/gitlab/odermatt/sentinel-hindcast.git
		$ sudo chmod 755 /prj
		$ cd sentinel-hindcast
		$ git checkout <branchname> (if not master)


10.) CDS API: https://cds.climate.copernicus.eu/api-how-to

	Have a Copernicus Climate account ready, otherwise create one: https://cds.climate.copernicus.eu/

	In shell do following:
		$ echo "url: https://cds.climate.copernicus.eu/api/v2" > ~/.cdsapirc
		$ echo key: [uid]:[api-key] >> ~/.cdsapirc (Note: replace [uid] and [api-key] by your actual credentials, see https://cds.climate.copernicus.eu/api-how-to )
		$ chmod 600 ~/.cdsapirc


11.) Cronjob for datalakes: https://linux4one.com/how-to-set-up-cron-job-on-centos-8/

	In shell do following:
		$ mkdir -p /prj/datalakes/log
		$ curl https://renkulab.io/gitlab/odermatt/sentinel-hindcast/raw/snap7compatibility/parameters/datalakes_sui_S3.ini?inline=false -o /prj/datalakes/datalakes_sui_S3.ini
		$ chmod 755 /prj/sentinel-hindcast/scripts/datalakes.sh
		$ crontab -l | { cat; echo "0 20 * * * nohup /prj/sentinel-hindcast/scripts/datalakes.sh &"; } | crontab -


12.) (not done yet) NASA Earthdata API: https://wiki.earthdata.nasa.gov/display/EL/How+To+Access+Data+With+cURL+And+Wget

	Have a NASA Earthdata account ready, otherwise create one: https://urs.earthdata.nasa.gov/

	In shell do following:
		$ touch ~/.netrc
		$ echo "machine urs.earthdata.nasa.gov login <earthdata user> password <earthdata password>" > ~/.netrc
		$ chmod 0600 ~/.netrc
		$ touch ~/.urs_cookies


14.) Optional - required for MDN

	In shell do following:
		$ conda activate sencast-39
		$ conda install -c conda-forge tensorflow==1.15.0
		$ conda install -c anaconda scikit-learn=0.23.2
		$ conda install -c conda-forge tensorflow-probability=0.7


15.) Optional - required for Acolite: https://github.com/acolite/acolite.git

	In shell do following:
		$ cd /prj
		$ git clone https://github.com/acolite/acolite.git
	
	Configure your Acolite path in you environment file.
		