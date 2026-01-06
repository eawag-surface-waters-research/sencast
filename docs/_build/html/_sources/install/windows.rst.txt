.. _windows:

------------------------------------------------------------------------------------------
Windows
------------------------------------------------------------------------------------------

.. warning::

  The windows version of this installation has a number of issues, it is suggested to use linux or the
  windows subsystem for linux. Processors such as Polymer cannot be used in Windows.

Clone Sencast
--------------

Start a command prompt and do following::

    > git clone https://github.com/eawag-surface-waters-research/sencast.git

Install Python Environment
---------------------------

Start a new cmd sencast environment::

    > conda env create -f sencast.yml

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

Acolite
--------
In cmd do following::

    > git clone --depth 1 --branch main https://github.com/acolite/acolite.git
