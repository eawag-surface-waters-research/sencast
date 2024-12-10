.. _windows:

------------------------------------------------------------------------------------------
Windows
------------------------------------------------------------------------------------------

.. warning::

  The windows version of this installation has a number of issues, it is suggested to use linux or the
  windows subsystem for linux. Processors such as Polymer cannot be used in Windows.

Install prerequisites
-----------------------

- Git: https://git-scm.com/downloads
- Visual C++ Build Tools 2015: https://go.microsoft.com/fwlink/?LinkId=691126


Clone Sencast
--------------

Start a command prompt and do following::

		> mkdir "%USERPROFILE%\Projects"
		> cd "%USERPROFILE%\Projects"
		> mkdir DIAS
		> mkdir ANCILLARY
		> mkdir datalakes
		> mkdir data_landmask_gsw
		> git clone https://github.com/eawag-surface-waters-research/sencast.git

Install Python Environment
---------------------------

Download Anaconda3

Install Anaconda3 (prefered to C:\Program Files\Conda)

Set CONDA_HOME to "C:\path_to_anaconda_installation\" (e.g. C:\Program Files\Conda)

Add "%CONDA_HOME%\bin" to PATH  (could need to be "%CONDA_HOME%\condabin")

Start a new cmd sencast environment::

    > conda env create -f %USERPROFILE%\Projects\sencast\sencast.yml

Set CONDA_ENV_HOME to "%CONDA_HOME%\envs\sencast"


SNAP
-----
http://step.esa.int/main/download/

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

Set SNAP_HOME to "C:\path_to_snap_installation\" (e.g. C:\Program Files\Snap)


CDS API
----------

Start a command prompt and do following::

    > echo url: https://cds.climate.copernicus.eu/api/v2 > %USERPROFILE%\.cdsapirc
    > echo key: <uid>:<api-key> >> %USERPROFILE%\.cdsapirc


NASA Earthdata API
-------------------

Have a NASA Earthdata account ready, otherwise create one: https://urs.earthdata.nasa.gov/

In cmd do following::

    > echo "machine urs.earthdata.nasa.gov login <earthdata user> password <earthdata password>" > %USERPROFILE%\.netrc
    > echo "" > %USERPROFILE%\.urs_cookies

Acolite
--------
In cmd do following::

    > cd "%USERPROFILE%\Projects"
    > git clone --depth 1 --branch main https://github.com/acolite/acolite.git
    > cd acolite
    > git reset --hard e7cb944


Sen2Cor
--------

First you must try to run it from SNAP GUI. It will then prompt you to install some bundle. Only after that the processor will work from GPT. https://forum.step.esa.int/t/error-processing-template-after-execution-for-parameter-postexecutetemplate/6591
