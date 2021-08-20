.. _windows10install:

------------------------------------------------------------------------------------------
Windows 10
------------------------------------------------------------------------------------------

1.) baramundi Kiosk: http://soft-prd:10080/Softwarekiosk/default.htm

	Get following programs from baramundi Kiosk:
	- Git
	- OpenJdk 1.8


2.) JAVA_HOME:

	Set JAVA_HOME to "C:\\path_to_jdk\\" (e.g. C:\\Program Files\\AdoptOpenJDK\\jdk-8.0.242.08-hotspot)

	Add "%JAVA_HOME%\\bin" to PATH

	Set JDK_HOME to "%JAVA_HOME%"


3.) Maven: http://maven.apache.org/download.cgi

	Download Maven 3.6.3

	Unzip installation folder and move it to the desired directory (preferred C:\\Program Files (x86)\\apache-maven-3.6.3)

	Set MAVEN_HOME to "C:\\path_to_maven_folder\\" (e.g. C:\\Program Files (x86)\\apache-maven-3.6.3)

	Add "%MAVEN_HOME%\\bin" to PATH

	Check with: mvn --version


4.) Visual C++ Build Tools 2015: https://go.microsoft.com/fwlink/?LinkId=691126


5.) Anaconda: https://www.anaconda.com/distribution/

	Download Anaconda3

	Install Anaconda3 (prefered to C:\\Anaconda3)

	Set CONDA_HOME to "C:\\path_to_anaconda_installation\\" (e.g. C:\\Anaconda3)

	Add "%CONDA_HOME%\\condabin" to PATH


6. Anaconda: sencast-37 environment

	Add conda-forge channel to environment:
		> conda config --add channels conda-forge

	Create a new environment named "sencast" using Anaconda
		> conda create --name sencast-37 python=3.7 gdal cartopy netcdf4 cython pkgconfig statsmodels matplotlib haversine rasterio pyproj scikit-image pyresample h5py

	Set CONDA_ENV_HOME to "%CONDA_HOME%\\envs\\sencast-37"


6.) Python - jpy: https://github.com/jpy-consortium/jpy/blob/master/README.md

	Start a command prompt and do following:
		> cd "%CONDA_ENV_HOME%\\Lib\\site-packages"
		> git clone https://github.com/bcdev/jpy.git
		> cd "jpy"
		> conda activate sencast-37
		> python get-pip.py
		> python setup.py build maven bdist_wheel


7.) SNAP: http://step.esa.int/main/download/

	Uninstall all old versions of SNAP:
		- Uninstall via "Control Panel -> Programs and Features"
		- Choose to delete all user data
		- Check that the SNAP installation folder has been removed completely by uninstalling. Otherwise delete it manually.
		- Delete snappy folder from all your python environments: %PYTHON_HOME%\\Lib\\site-packages
		- Delete .snap folder from all user accounts: %USERPROFILE%\\.snap
		- Delete SNAP Folder from all user accoutns: %USERPROFILE%\\AppData\\Roaming\\SNAP

	Download SNAP

	Install SNAP

	Do not configure SNAP for use with Python yet.

	Run SNAP and install available updates.

	Configure: Tools -> Options -> S3TBX -> Check: Read Sentinel-3 OLCI products with per pixel geo-coding instead of using tie-points

	Configure: Tools -> Plugins -> Available Plugins -> Install all IDEPIX Plugins

	Set SNAP_HOME to "C:\\path_to_snap_isntallation\\" (e.g. C:\\Snap7)

	Close SNAP


8.) Python - snappy: https://github.com/senbox-org/snap-engine/blob/master/snap-python/src/main/resources/README.md

	Start a command prompt and do following:
		> cd "%SNAP_HOME%\\bin"
		> xcopy "%CONDA_ENV_HOME%\\Lib\\site-packages\\jpy\\dist\\*.whl" "%USERPROFILE%\\.snap\\snap-python\\snappy\\"
		> snappy-conf "%CONDA_ENV_HOME%\\python.exe" "%USERPROFILE%\\.snap\\snap-python"
		> (I had to end the process after about 30 seconds using "Ctrl+C" at this point)
		> cd "%USERPROFILE%\\.snap\\snap-python\\snappy"
		> conda activate sencast-37
		> python setup.py install
		> xcopy "%USERPROFILE%\\.snap\\snap-python\\snappy\\tests" "%CONDA_ENV_HOME%\\Lib\\site-packages\\snappy\\tests\\"
		> cd "%CONDA_ENV_HOME%\\Lib\\site-packages\\snappy\\tests"
		> curl --url "https://raw.githubusercontent.com/bcdev/eo-child-gen/master/child-gen-N1/src/test/resources/com/bc/childgen/MER_RR__1P.N1" --output "%CONDA_ENV_HOME%\\Lib\\site-packages\\snappy\\tests\\MER_RR__1P.N1"
		> python test_snappy_mem.py
		> python test_snappy_perf.py
		> python test_snappy_product.py


9.) Python - polymer: https://forum.hygeos.com/viewforum.php?f=5

	Start a command prompt and do following:
		> cd "%USERPROFILE%\\AppData\\Local\\Temp"
		> xcopy "Q:\\Abteilungsprojekte\\Surf\\surf-DD\\RS\\Software\\Polymer\\polymer-v4.13.zip" "%USERPROFILE%\\AppData\\Local\\Temp"
		> jar xf "polymer-v4.13.zip"
		> cd "polymer-v4.13"
		> conda activate sencast-37
		> conda install pyhdf pyepr glymur pygrib cdsapi xarray bioconda::ecmwfapi
		> python setup.py build_ext --inplace
		> xcopy "%USERPROFILE%\\AppData\\Local\\Temp\\polymer-v4.13\\polymer" "%CONDA_ENV_HOME%\\Lib\\site-packages\\polymer\\"
		> xcopy "%USERPROFILE%\\AppData\\Local\\Temp\\polymer-v4.13\\auxdata" "%CONDA_ENV_HOME%\\Lib\\site-packages\\auxdata\\"


10.) sencast: https://renkulab.io/gitlab/odermatt/sentinel-hindcast

	Start a command prompt and do following:
		> cd "C:\\Projects"
		> mkdir "DIAS"
		> mkdir "datalakes"
		> git clone https://renkulab.io/gitlab/odermatt/sentinel-hindcast.git


11.) CDS API: https://cds.climate.copernicus.eu/api-how-to

	Start a command prompt and do following:
		> echo url: https://cds.climate.copernicus.eu/api/v2 > %USERPROFILE%\\.cdsapirc
		> echo key: <uid>:<api-key> >> %USERPROFILE%\\.cdsapirc


12.) PyCharm CE: https://www.jetbrains.com/de-de/pycharm/download/#section=windows

	Download PyCharm CE from https://www.jetbrains.com/de-de/pycharm/download/download-thanks.html?platform=windows&code=PCC

	Install PyCharm CE with default settings

	Launch PyCharm CE

	Open -> C:\\Projects\\sentinel-hindcast

	Add a Project Interpreter
		- File -> Settings -> Project: sencast -> Gearwheel in the upper right -> Show All...
		- Add (+) -> Conda Environment -> Existing environment -> Interpreter: C:\\Anaconda3\\envs\\sencast-37\\python.exe -> OK -> OK -> OK
		- Give it some time to index files (watch processes in the bottom line to finish)

	Define a running configuration:
		- In the top right "Add Configuration..."
		- In the top left Add (+) -> Python
		- Name: sencast-37
		- Script path: C:\\Projects\\sentinel-hindcast\\sencast.py
		- Python interpreter: Python 3.7 (sencast-37)
		- OK

14.) Optional - required for MDN
	conda activate sencast-37
	conda install -c conda-forge tensorflow==1.15.0
	conda install -c anaconda scikit-learn=0.23.2
	conda install -c conda-forge tensorflow-probability=0.7

You are now set up and ready to start coding as well as running sencast
