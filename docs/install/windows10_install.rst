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


6. Anaconda: sencast environment

	In cmd do following:
		> conda config --add channels conda-forge
		> conda config --append channels bioconda
		> conda create --name sencast python=3 cartopy=0.19 cdsapi=0.5 colour-science=0.3 cython=0.29 ecmwfapi=1.4 gdal=3.2 glymur=0.9 h5py=3.3 haversine=2.5 matplotlib=3.4 netcdf4=1.5 pkgconfig=1.5 pyepr=1.1 pygrib=2.1 pyhdf=0.10.3 pyproj=3.1 pyresample=1.21 rasterio=1.2 scikit-learn=0.24 statsmodels=0.12 tensorflow=1.15 tensorflow-probability=0.7 wheel=0.37 xarray=0.19 xlrd=1.2

	Set CONDA_ENV_HOME to "%CONDA_HOME%\\envs\\sencast"


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

	Set SNAP_HOME to "C:\\path_to_snap_installation\\" (e.g. C:\\Snap7)

	Close SNAP


8.) sencast: https://renkulab.io/gitlab/odermatt/sentinel-hindcast

	In cmd do following:
		> cd "C:\\Projects"
		> mkdir "DIAS"
		> mkdir "datalakes"
		> git clone https://renkulab.io/gitlab/odermatt/sentinel-hindcast.git


9. Local DIAS

	Create a folder which you want to use as your local DIAS folder.
	
	Configure your local DIAS path in your environment file.


10.) Python - jpy: https://github.com/jpy-consortium/jpy/blob/master/README.md

	In cmd do following:
		> cd "%CONDA_ENV_HOME%\\Lib\\site-packages"
		> git clone https://github.com/bcdev/jpy.git
		> cd jpy
		> conda activate sencast
		> python setup.py build maven bdist_wheel


11.) Python - snappy: https://github.com/senbox-org/snap-engine/blob/master/snap-python/src/main/resources/README.md

	In cmd do following:
		> cd "%SNAP_HOME%\\bin"
		> xcopy "%CONDA_ENV_HOME%\\Lib\\site-packages\\jpy\\dist\\*.whl" "%USERPROFILE%\\.snap\\snap-python\\snappy\\"
		> snappy-conf "%CONDA_ENV_HOME%\\python.exe" "%USERPROFILE%\\.snap\\snap-python"
		> (I had to end the process after about 30 seconds using "Ctrl+C" at this point)
		> cd "%USERPROFILE%\\.snap\\snap-python\\snappy"
		> conda activate sencast
		> python setup.py install
		> xcopy "%USERPROFILE%\\.snap\\snap-python\\snappy\\tests" "%CONDA_ENV_HOME%\\Lib\\site-packages\\snappy\\tests\\"
		> cd "%CONDA_ENV_HOME%\\Lib\\site-packages\\snappy\\tests"
		> curl --url "https://raw.githubusercontent.com/bcdev/eo-child-gen/master/child-gen-N1/src/test/resources/com/bc/childgen/MER_RR__1P.N1" --output "%CONDA_ENV_HOME%\\Lib\\site-packages\\snappy\\tests\\MER_RR__1P.N1"
		> python test_snappy_mem.py
		> python test_snappy_perf.py
		> python test_snappy_product.py


12.) Python - polymer: https://forum.hygeos.com/viewforum.php?f=5

	(Due to some internals of polymer it still does not work on Windows. However the part required for C2RCC (ancillary_era5.py) works on windows.)

	In cmd do following:
		> cd "%USERPROFILE%\\AppData\\Local\\Temp"
		> xcopy "Q:\\Abteilungsprojekte\\Surf\\surf-DD\\RS\\Software\\Polymer\\polymer-v4.13.zip" "%USERPROFILE%\\AppData\\Local\\Temp"
		> jar xf "polymer-v4.13.zip"
		> cd "polymer-v4.13"
		> conda activate sencast
		> python setup.py build_ext --inplace
		> xcopy "%USERPROFILE%\\AppData\\Local\\Temp\\polymer-v4.13\\polymer" "%CONDA_ENV_HOME%\\Lib\\site-packages\\polymer\\"
		> xcopy "%USERPROFILE%\\AppData\\Local\\Temp\\polymer-v4.13\\auxdata" "%CONDA_ENV_HOME%\\Lib\\site-packages\\auxdata\\"
		
	In the file site-packages\polymer\level1_landsat8.py replace line 13 "import osr" by "from osgeo import osr"


13.) CDS API: https://cds.climate.copernicus.eu/api-how-to

	In cmd do following:
		> echo url: https://cds.climate.copernicus.eu/api/v2 > %USERPROFILE%\\.cdsapirc
		> echo key: <uid>:<api-key> >> %USERPROFILE%\\.cdsapirc


14.) PyCharm CE: https://www.jetbrains.com/de-de/pycharm/download/#section=windows

	Download PyCharm CE from https://www.jetbrains.com/de-de/pycharm/download/download-thanks.html?platform=windows&code=PCC

	Install PyCharm CE with default settings

	Launch PyCharm CE

	Open -> C:\\Projects\\sentinel-hindcast

	Add a Project Interpreter:
		- File -> Settings -> Project: sencast -> Gearwheel in the upper right -> Show All...
		- Add (+) -> Conda Environment -> Existing environment -> Interpreter: C:\\Anaconda3\\envs\\sencast\\python.exe -> OK -> OK -> OK
		- Give it some time to index files (watch processes in the bottom line to finish)

	Define a running configuration:
		- In the top right "Add Configuration..."
		- In the top left Add (+) -> Python
		- Name: sencast
		- Script path: C:\\Projects\\sentinel-hindcast\\sencast.py
		- Python interpreter: Python 3.9 (sencast)
		- OK


16.) Acolite:

	Start a command prompt and do following:
		> cd C:\\Projects
		> git clone https://github.com/acolite/acolite.git
		
	Edit the file acolite_l2w.py and comment-out all usages (and import) of "skimage".
		Currently lines 23, 898, 909, 910, 911

    In acolite/config/defaults.txt, row 28 set setting geometry_type=gpt (to avoid a batch processing but as of Dec. '21)
	Configure your Acolite path in your environment file.


17.) FLUO:
	
	Install the operator in SNAP Desktop:
		- Tools -> Plugins -> Downloaded -> Add Plugins...
		- Choose your *.nbm file (Q:\Abteilungsprojekte\Surf\surf-DD\RS\Software\sentinel-hindcast\SNAP Plugins) -> OK
		- Select your new Plugin in the list -> Install -> Accept everything


18.) iCOR: https://remotesensing.vito.be/case/icor

	Download iCOR from https://remotesensing.vito.be/case/icor
	
	Execute downloaded .exe file.
	
	Installation of SNAP plugin only necessairy if you want to use iCOR from SNAP Desktop. For sencast it is not needed.



19.) LSWT:
	
	Install the operator in SNAP Desktop:
		- Tools -> Plugins -> Downloaded -> Add Plugins...
		- Choose your *.nbm file (Q:\Abteilungsprojekte\Surf\surf-DD\RS\Software\sentinel-hindcast\SNAP Plugins) -> OK
		- Select your new Plugin in the list -> Install -> Accept everything