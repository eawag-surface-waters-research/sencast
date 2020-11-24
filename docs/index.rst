Sencast
==================

.. image:: logo.png
    :width: 120px
    :alt: Eawag logo
    :align: left

Sencast is a python toolbox that forms a framework around existing packages for processing
Sentinel 2 & Sentinel 3 satellite images in order facilitates processing pipelines for deriving water
quality parameters such as Chlorophyll A, Turbidity, etc.

It is developed and maintained by the `SURF Remote Sensing group at Eawag`_.

.. warning::

  Sencast is under active development. The project team are working towards
  the release of a stable v1.0, however for the moment this project remains pre-v1.0.

Publications
-------------
| **SenCast: Copernicus Satellite Data on Demand**
| *D. Odermatt, J. Runnalls, J. Sturm, A. Damm*
| `German <https://www.dora.lib4ri.ch/eawag/islandora/object/eawag%3A21549/datastream/PDF4/Odermatt-2020-SenCast-%28accepted_version%29.pdf)>`_
 `English <https://www.dora.lib4ri.ch/eawag/islandora/object/eawag%3A21549/datastream/PDF3/Odermatt-2020-SenCast-%28unspecified_8a1c1609%29.pdf>`_

Installation
-------------

To install Sencast, run::

  git clone git@gitlab.com:eawag-rs/sencast.git
  pip install -r requirements.txt

Many of the Sencast'S processors reply on `SNAP`_ , the SeNtinel Application Platform
project, funded by the `European Space Agency`_ (ESA) or other 3rd party packages. In order to have
access to all of Sencast's processors follow the installation instructions below in order to
correctly configure your environment.

This process will require registering accounts with data providers.

- :ref:`ubuntu18install`
- :ref:`centos8install`
- :ref:`windows10install`

For issues with installation, please contact `Daniel
Odermatt`_.

Getting Started
---------------

Environment File
~~~~~~~~~~~~~~~~~~~~~~

Environment files use the INI format and contain the configuration of
the machine on which Sencast runs. Refer to :ref:`environments`
for details on how to set up your own environment file.

You should create your own environment file for every machine you
install Sencast on.

Parameter File
~~~~~~~~~~~~~~~~~~~~~~

Parameter files use the INI format and contain the parameters for one
execution of Sencast. Refer to :ref:`parameters`
for details on how to set up your own parameter file.

Perimeter Definition
~~~~~~~~~~~~~~~~~~~~~~

Perimeter definitions define a geographic area to be processed by
Sentinel Hndacast. They are stored as polygons in `WKT`_ files, which
are referenced from the parameter files. Some example perimeters are stored
in the wkt folder.

Data Processing
~~~~~~~~~~~~~~~~~~~~~~

Data is preprocessed by a build-in preprocessor which performs
resampling, subsetting, idepix and reproject operations on the input
products. Several processors then process the data and save the results
to disk.

Sencast offers to interfaces to process data.

-  The file-based interface takes a parameter file and an optional
   environment file as input. It reads the file contents and calls the
   object based interface with the read configurations.
-  The object-based interface directly takes an environment and a
   parameters object as well as a path for the L1 (input) products and a
   path for the L2 (output) products.

Adapters
~~~~~~~~~~~~~~~~~~~~~~

Adapters can receive the output of processors and for example send it to
another service.

.. toctree::
   :maxdepth: 2
   :caption: Installation

   ubuntu18_install.rst
   centos8_install.rst
   windows10_install.rst

.. toctree::
   :maxdepth: 2
   :caption: Configuration

   environment_config.rst
   parameters_config.rst

.. toctree::
   :maxdepth: 2
   :caption: Sencast

   main
   auxil
   product_fun

.. toctree::
   :maxdepth: 2
   :caption: Processors

   c2rcc.rst
   fluo.rst
   idepix.rst
   mosaic.rst
   mph.rst
   polymer.rst
   sen2cor.rst

.. toctree::
   :maxdepth: 2
   :caption: Adapters

   primaryproduction_code
   merge_code
   datalakes_code
   qlrgb_code
   qlsingleband_code

.. toctree::
   :maxdepth: 2
   :caption: External API's

   coah_api
   creodias_api
   earthdata_api
   hda_api

.. _SURF Remote Sensing group at Eawag: https://www.eawag.ch/en/department/surf/main-focus/remote-sensing/
.. _jpy: https://github.com/bcdev/jpy/blob/master/README.md
.. _snappy: https://github.com/senbox-org/snap-engine/blob/master/snap-python/src/main/resources/README.md
.. _polymer: https://forum.hygeos.com/viewtopic.php?f=5&t=56
.. _SNAP: http://step.esa.int/main/toolboxes/snap/
.. _European Space Agency: http://www.esa.int/
.. _Daniel Odermatt: https://www.eawag.ch/de/ueberuns/portraet/organisation/mitarbeitende/profile/daniel-odermatt/show/
.. _example.ini: https://renkulab.io/gitlab/odermatt/sentinel-hindcast/blob/master/environments/example.ini
.. _parameters_template_S3.ini: https://renkulab.io/gitlab/odermatt/sentinel-hindcast/blob/master/parameters/parameters_template_S3.ini
.. _WKT: https://en.wikipedia.org/wiki/Well-known_text_representation_of_geometry



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
