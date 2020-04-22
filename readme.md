Sentinel Hindcast
=
Sentinel Hindcast is a toolbox to derive water quality factors by processing images from the ESA satelites Sentinel 2 and Sentinel 3.
It is develeoped and maintained by the [SURF](https://www.eawag.ch/en/department/surf/) group at [EAWAG](https://www.eawag.ch/en/).

How to install
-
Sentinel Hindcast requires following python packages to be installed:
* gdal
* cartopy
* netcdf4
* cython
* pkgconfig
* statsmodels
* matplotlib
* haversine
* [jpy](https://github.com/bcdev/jpy/blob/master/README.md)
* [snappy](https://github.com/senbox-org/snap-engine/blob/master/snap-python/src/main/resources/README.md)
* [polymer](https://forum.hygeos.com/viewtopic.php?f=5&t=56)

It further needs [SNAP](http://step.esa.int/main/toolboxes/snap/) installed, the SeNtinel Application Platform project, funded by the [European Space Agency](http://www.esa.int/) (ESA).

For more detailed installation instructions, please contact [Daniel Odermatt](https://www.eawag.ch/de/ueberuns/portraet/organisation/mitarbeitende/profile/daniel-odermatt/show/).

Environment File
-
Environment files use the INI format and contain the configuration of the machine on which Sentinel Hindcast runs.
For documentation please refer to [example.ini](https://renkulab.io/gitlab/odermatt/sentinel-hindcast/blob/master/environments/example.ini).

You should create your own environment file for every machine you install Sentinel Hindcast on.

Parameter File
-
Parameter files use the INI format and contain the parameters for one execution of Sentinel Hindcast. For documentation please refer to [parameters_template_S3.ini](https://renkulab.io/gitlab/odermatt/sentinel-hindcast/blob/master/parameters/parameters_template_S3.ini).

Perimeter Definition
-
Perimeter definitions define a geographic area to be processed by Sentinel Hndacast. They are stored as polygons in [WKT](https://en.wikipedia.org/wiki/Well-known_text_representation_of_geometry) files, which are referenced from the parameter files.

Data Processing
-
Data is preprocessed by a build-in preprocessor which performs resampling, subsetting, idepix and reproject operations on the input products.
Several processors then process the data and save the results to disk.

Sentinel Hindcast offers to interfaces to process data.
- The file-based interface takes a parameter file and an optional environment file as input. It reads the file contents and calls the object based interface with the read configurations.
- The object-based interface directly takes an environment and a parameters object as well as a path for the L1 (input) products and a path for the L2 (output) products.


Adapters
-
Adapters can receive the output of processors and for example send it to another service.
