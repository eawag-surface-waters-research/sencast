.. _centos8install:

------------------------------------------------------------------------------------------
CentOS 8
------------------------------------------------------------------------------------------
Prepare)

	Update repositories and installed packages:
		$ sudo apt update
		$ sudo apt upgrade
		
	Here we put the setup files:
		$ mkdir -p ~/setup


1.) OpenJdk (if not installed already):

	In shell do following:
		$ sudo yum install java-11-openjdk-devel
			> y
		$ sudo su -c 'echo "JAVA_HOME=/usr/lib/jvm/java-11-openjdk/" >> /etc/environment'
		$ java -version
		$ sudo reboot


2.) Maven: https://www.javahelps.com/2017/10/install-apache-maven-on-linux.html

	In shell do following:
		$ sudo yum install maven
		$ mvn -version


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
		$ echo export CONDA_HOME=~/anaconda3 >> ~/.bashrc
	
	Restart your shell session


4. Anaconda: create sencast-39 environment

	In shell do following:
		$ conda config --add channels conda-forge
		$ conda config --append channels bioconda
		$ conda create --name sencast-39 python=3.9 gdal cartopy netcdf4 cython pkgconfig statsmodels matplotlib haversine
		$ echo export CONDA_ENV_HOME=$CONDA_HOME/envs/sencast-39 >> ~/.bashrc


5.) SNAP: http://step.esa.int/main/download/

	Uninstall all old versions of SNAP and remove associated data

	In shell do following:
		$ curl http://step.esa.int/downloads/8.0/installers/esa-snap_all_unix_8_0.sh -o ~/setup/esa-snap_all_unix_8_0.sh
		$ bash ~/Downloads/esa-snap_all_unix_8_0.sh
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
		$ echo export SNAP_HOME=~/snap >> ~/.bashrc
	
	Restart your shell session

	Note: there are many strange error messages, but it seems to work in the end when updating and installing plugins

	To remove warning "WARNING: org.esa.snap.dataio.netcdf.util.MetadataUtils: Missing configuration property ‘snap.dataio.netcdf.metadataElementLimit’. Using default (100).":
		$ echo "" >> $SNAP_HOME/etc/snap.properties
		$ echo "# NetCDF options" >> $SNAP_HOME/etc/snap.properties
		$ echo "snap.dataio.netcdf.metadataElementLimit=10000" >> $SNAP_HOME/etc/snap.properties

	To remove warning "SEVERE: org.esa.s2tbx.dataio.gdal.activator.GDALDistributionInstaller: The environment variable LD_LIBRARY_PATH is not set. It must contain the current folder '.'."
		$ echo export LD_LIBRARY_PATH=. >> ~/.bashrc
	
	Restart your shell session


6.) Python - jpy: https://github.com/bcdev/jpy/blob/master/README.md

	In shell do following:
		$ cd $CONDA_ENV_HOME/lib/python3.9/site-packages
		$ git clone https://github.com/bcdev/jpy.git
		$ cd jpy
		$ conda activate sencast-39
		$ python get-pip.py
		$ python setup.py build maven bdist_wheel


7.) Python - snappy: https://github.com/senbox-org/snap-engine/blob/master/snap-python/src/main/resources/README.md

	In shell do following:
		$ sudo ln -s ../../lib64/libnsl.so.2 /usr/lib64/libnsl.so
		$ sudo ln -s ../../lib64/libnsl.so.2.0.0 /usr/lib64/libnsl.so.1
		$ mkdir -p ~/.snap/snap-python/snappy
		$ cp $CONDA_ENV_HOME/lib/python3.9/site-packages/jpy/dist/*.whl ~/.snap/snap-python/snappy
		$ bash /opt/snap/bin/snappy-conf $CONDA_ENV_HOME/bin/python ~/.snap/snap-python
		$ conda activate sencast-39
		$ python ~/.snap/snap-python/snappy/setup.py install --user
		$ cp -avr ~/.snap/snap-python/build/lib/snappy $CONDA_ENV_HOME/lib/python3.9/site-packages/snappy
		$ cp -avr ~/.snap/snap-python/snappy/tests $CONDA_ENV_HOME/lib/python3.9/site-packages/snappy/tests
		$ cd $CONDA_ENV_HOME/lib/python3.9/site-packages/snappy/tests
		$ curl https://raw.githubusercontent.com/bcdev/eo-child-gen/master/child-gen-N1/src/test/resources/com/bc/childgen/MER_RR__1P.N1 -o MER_RR__1P.N1
		$ python test_snappy_mem.py
		$ python test_snappy_perf.py
		$ python test_snappy_product.py


8.) Python - polymer: https://forum.hygeos.com/viewforum.php?f=5

	From a computer in the eawag network, copy the polymer zip file to the linux server:
		> scp -i .ssh\cloudferro.key \\eawag\Abteilungs-Projekte\Surf\surf-DD\RS\Software\Polymer\polymer-v4.13.tar.gz eouser@45.130.29.115:/home/eouser/setup/

	In shell do following:
		$ tar -xvzf ~/setup/polymer-v4.13.tar.gz --directory ~/setup
		$ cd ~/setup/polymer-v4.13
		$ conda activate sencast-39
		$ bash install-anaconda-deps.sh
			[y]
			[y]
		$ sudo yum install gcc
		$ sudo yum install wget
		$ make all
		$ cp -avr /opt/polymer-v4.13/polymer $CONDA_ENV_HOME/lib/python3.9/site-packages/polymer
		$ cp -avr /opt/polymer-v4.13/auxdata $CONDA_ENV_HOME/lib/python3.9/site-packages/auxdata


9.) sentinel-hindcast: https://renkulab.io/gitlab/odermatt/sentinel-hindcast

	In shell do following:
		$ mkdir ~/DIAS
		$ git clone https://renkulab.io/gitlab/odermatt/sentinel-hindcast.git
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
	conda activate sencast-39
	conda install -c conda-forge tensorflow==1.15.0
	conda install -c anaconda scikit-learn=0.23.2
	conda install -c conda-forge tensorflow-probability=0.7