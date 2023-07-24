.. _windows10install:

------------------------------------------------------------------------------------------
Windows 10
------------------------------------------------------------------------------------------

.. warning::

  The windows version of this installation has a number of issues, it is suggested to use linux or the
  windows subsystem for linux for installing and using Sencast.

1.) Install prerequisites

- Git: https://git-scm.com/downloads
- Visual C++ Build Tools 2015: https://go.microsoft.com/fwlink/?LinkId=691126


2.) sencast: https://renkulab.io/gitlab/odermatt/sentinel-hindcast

Start a command prompt and do following::

		> mkdir "%USERPROFILE%\Projects"
		> cd "%USERPROFILE%\Projects"
		> mkdir DIAS
		> mkdir ANCILLARY
		> mkdir datalakes
		> mkdir data_landmask_gsw
		> git clone https://gitlab.com/eawag-rs/sencast.git


3.) Anaconda: https://www.anaconda.com/distribution/

Download Anaconda3

Install Anaconda3 (prefered to C:\Program Files\Conda)

Set CONDA_HOME to "C:\path_to_anaconda_installation\" (e.g. C:\Program Files\Conda)

Add "%CONDA_HOME%\bin" to PATH  (could need to be "%CONDA_HOME%\condabin")

Start a new cmd sencast environment::

    > conda env create -f %USERPROFILE%\Projects\sencast\sencast.yml

Set CONDA_ENV_HOME to "%CONDA_HOME%\envs\sencast"


4.) SNAP: http://step.esa.int/main/download/

Uninstall all old versions of SNAP:
    - Uninstall via "Control Panel -> Programs and Features"
    - Choose to delete all user data
    - Check that the SNAP installation folder has been removed completely by uninstalling. Otherwise delete it manually.
    - Delete snappy folder from all your python environments: %PYTHON_HOME%\Lib\site-packages
    - Delete .snap folder from all user accounts: %USERPROFILE%\.snap
    - Delete SNAP Folder from all user accoutns: %USERPROFILE%\AppData\Roaming\SNAP

Download SNAP

Install SNAP

Do not configure SNAP for use with Python.

Run SNAP and install available updates.

Configure: Tools -> Options -> S3TBX -> Check: Read Sentinel-3 OLCI products with per pixel geo-coding instead of using tie-points

Configure: Tools -> Plugins -> Available Plugins -> Install all plugins

Wait for it to finish and close SNAP

Set SNAP_HOME to "C:\path_to_snap_isntallation\" (e.g. C:\Program Files\Snap)


5.) PyCharm CE: https://www.jetbrains.com/de-de/pycharm/download/#section=windows

Download PyCharm CE from https://www.jetbrains.com/de-de/pycharm/download/download-thanks.html?platform=windows&code=PCC

Install PyCharm CE with default settings

Launch PyCharm CE

Open -> %USERPROFILE%\Projects\sencast

Add a Project Interpreter:
    - File -> Settings -> Project: sencast -> Gearwheel in the upper right -> Show All...
    - Add (+) -> Conda Environment -> Existing environment -> Interpreter: C:\Program Files\Conda\envs\sencast\python.exe -> OK -> OK -> OK
    - Give it some time to index files (watch processes in the bottom line to finish)

Define a running configuration:
    - In the top right "Add Configuration..."
    - In the top left Add (+) -> Python
    - Name: sencast
    - Script path: %USERPROFILE%\Projects\sencast\main.py
    - Python interpreter: Python 3.7 (sencast)
    - OK


6.) Python - polymer: https://forum.hygeos.com/viewforum.php?f=5

Polymer will not fully work on Windows, but some parts of it are required by other processors.
Here is described why: https://github.com/pyansys/pymapdl/issues/14

Start a command prompt and do following::

    > cd "%USERPROFILE%\AppData\Local\Temp"
    > xcopy "Q:\Abteilungsprojekte\Surf\surf-DD\RS\Software\Polymer\polymer-v4.14.zip" "%USERPROFILE%\AppData\Local\Temp"
    > jar xf "polymer-v4.14.zip"
    > cd "polymer-v4.14"
    > conda activate sencast
    > python setup.py build_ext --inplace
    > xcopy "%USERPROFILE%\AppData\Local\Temp\polymer-v4.14\polymer" "%CONDA_ENV_HOME%\Lib\site-packages\polymer\"
    > xcopy "%USERPROFILE%\AppData\Local\Temp\polymer-v4.14\auxdata" "%CONDA_ENV_HOME%\Lib\site-packages\auxdata\"


7.) l8_angles: https://www.usgs.gov/core-science-systems/nli/landsat/solar-illumination-and-sensor-viewing-angle-coefficient-files?qt-science_support_page_related_con=1#qt-science_support_page_related_con

This is likely not used on Windows because Polymer will not run anyway


8.) CDS API: https://cds.climate.copernicus.eu/api-how-to

Start a command prompt and do following::

    > echo url: https://cds.climate.copernicus.eu/api/v2 > %USERPROFILE%\.cdsapirc
    > echo key: <uid>:<api-key> >> %USERPROFILE%\.cdsapirc


9.) NASA Earthdata API: https://wiki.earthdata.nasa.gov/display/EL/How+To+Access+Data+With+cURL+And+Wget

Have a NASA Earthdata account ready, otherwise create one: https://urs.earthdata.nasa.gov/

In cmd do following::

    > echo "machine urs.earthdata.nasa.gov login <earthdata user> password <earthdata password>" > %USERPROFILE%\.netrc
    > echo "" > %USERPROFILE%\.urs_cookies

10.) Acolite: https://github.com/acolite/acolite

In cmd do following::

    > cd "%USERPROFILE%\Projects"
    > git clone --depth 1 --branch python37 https://github.com/JamesRunnalls/acolite.git


11.) L/R_FLUO:

Extract the content of "Q:\Abteilungsprojekte\Surf\surf-DD\RS\Software\sentinel-hindcast\SNAP Plugins\snap-eum-fluo-1.0.nbm" to %USERPROFILE%\.snap\system


12.) iCOR: https://remotesensing.vito.be/case/icor

Execute the installer "Q:\Abteilungsprojekte\Surf\surf-DD\RS\Software\sentinel-hindcast\SNAP Plugins\iCOR_Setup_3.0.0.exe" and follow the instruction.
Configure your iCOR path in you environment file.


13.) Sen2Cor:

First you must try to run it from SNAP GUI. It will then prompt you to install some bundle. Only after that the processor will work from GPT. https://forum.step.esa.int/t/error-processing-template-after-execution-for-parameter-postexecutetemplate/6591


14.) LSWT:

Extract the content of "Q:\Abteilungsprojekte\Surf\surf-DD\RS\Software\sentinel-hindcast\SNAP Plugins\snap-musenalp-processor-1.0.8.nbm" to %USERPROFILE%\.snap\system

Install the operator in SNAP Desktop:
    - Tools -> Plugins -> Downloaded -> Add Plugins...
    - Choose your .nbm file (Q:\Abteilungsprojekte\Surf\surf-DD\RS\Software\sentinel-hindcast\SNAP Plugins) -> OK
    - Select your new Plugin in the list -> Install -> Accept everything