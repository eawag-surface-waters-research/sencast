Sencast
==================

.. image:: logo.png
    :width: 120px
    :alt: Eawag logo
    :align: left

Sencast is a toolbox to download and derive water quality parameters from satellite images. It acts as a framework for
the use a variety of processors such as Idepix, Polymer, Sen2Cor and Acolite. It supports ESA satellites Sentinel 2 and
Sentinel 3 and USGS satellite Landsat 8.

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

To install Sencast, run

.. code-block:: bash

  git clone https://gitlab.com/eawag-rs/sencast.git
  conda env create -f ~/sencast/sencast.yml

Many of the Sencast'S processors reply on `SNAP`_ , the SeNtinel Application Platform
project, funded by the `European Space Agency`_ (ESA) or other 3rd party packages. In order to have
access to all of Sencast's processors follow the installation instructions below in order to
correctly configure your environment.

This process will require registering accounts with data providers.

.. toctree::
   :maxdepth: 2

   install/ubuntu18_install.rst
   install/windows10_install.rst

For issues with installation, please contact `Daniel
Odermatt`_.

Getting Started
---------------

Sencast can be run in two ways:

1. By calling the ``main.py`` script with command line arguments

.. code-block:: python

    python main.py -p parameters.ini -e environment.ini


+-------------------+---------------------+-------------------------------------------------------------------+
| Parameters        | Default             | Description                                                       |
+===================+=====================+===================================================================+
| -t --tests        | False               | run test processing to check setup                                |
+-------------------+---------------------+-------------------------------------------------------------------+
| -x --delete_tests | False               | delete previous test run                                          |
+-------------------+---------------------+-------------------------------------------------------------------+
| -p --parameters   | Required            | link to the parameters.ini file (required except for tests)       |
+-------------------+---------------------+-------------------------------------------------------------------+
| -e  --environment | ${machine-name}.ini | link to the environment.ini file                                  |
+-------------------+---------------------+-------------------------------------------------------------------+
| -d -–downloads    | 1                   | number of parallell downloads                                     |
+-------------------+---------------------+-------------------------------------------------------------------+
| -p --processors   | 1                   | number of parallell processors                                    |
+-------------------+---------------------+-------------------------------------------------------------------+
| -a --adapters     | 1                   | number of parallell adapters                                      |
+-------------------+---------------------+-------------------------------------------------------------------+

2. By importing Sencast as a function

.. code-block:: python

    from sencast.main import sencast

    sencast(params_file, env_file=None, max_parallel_downloads=1, max_parallel_processors=1, max_parallel_adapters=1)

For this options you can pass objects as the params_file and env_file as well as links to the text files.

Following flow chart illustrates how Sencast works.

.. image:: flowchart.png
    :width: 800px
    :alt: Sencast Flow Chart
    :align: center

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

Processors
~~~~~~~~~~~~~~~~~~~~~~

Data is processed by a sequence of processors defined in the
parameters file. Subsequent processors have all outputs of preceding
processors available and might process these outputs further.
The user is responsible to ensure that he specifies the processors
in the parameters file in the correct order.

Adapters
~~~~~~~~~~~~~~~~~~~~~~

The purpose of an adapter is to perform some action after the processors
have finished. Possible actions include but are not limited to
validating outputs, sending processed outputs to some webservice,
creating quicklooks, notifying some webservice about the finished
sencast run.

Adapter usually do not produce any new output products.

Testing
--------

To test your installation run::

  cd ~/sencast
  conda activate sencast
  python main.py -t

This will report which processors are successfully installed and producing meaning-full outputs.

.. toctree::
   :maxdepth: 2
   :caption: Installation

   install/ubuntu18_install.rst
   install/windows10_install.rst

.. toctree::
   :maxdepth: 2
   :caption: Configuration

   environment_config.rst
   parameters_config.rst

.. toctree::
   :maxdepth: 2
   :caption: Sencast

   main.rst

.. toctree::
   :maxdepth: 2
   :caption: Utilities

   utils/auxil.rst
   utils/earthdata.rst
   utils/product_fun.rst

.. toctree::
   :maxdepth: 2
   :caption: Processors

   processors/acolite.rst
   processors/c2rcc.rst
   processors/fluo.rst
   processors/forelule.rst
   processors/icor.rst
   processors/idepix.rst
   processors/lswt.rst
   processors/mdn.rst
   processors/merge.rst
   processors/mph.rst
   processors/ndwi.rst
   processors/oc3.rst
   processors/polymer.rst
   processors/primaryproduction.rst
   processors/s2res.rst
   processors/secchidepth.rst
   processors/sen2cor.rst
   processors/whiting.rst

.. toctree::
   :maxdepth: 2
   :caption: Adapters

   adapters/datalakes.rst
   adapters/qlrgb.rst
   adapters/qlsingleband.rst

.. toctree::
   :maxdepth: 2
   :caption: DIAS API's

   apis/coah.rst
   apis/creodias.rst
   apis/hda.rst

.. _SURF Remote Sensing group at Eawag: https://www.eawag.ch/en/department/surf/main-focus/remote-sensing/
.. _polymer: https://forum.hygeos.com/viewtopic.php?f=5&t=56
.. _SNAP: http://step.esa.int/main/toolboxes/snap/
.. _European Space Agency: http://www.esa.int/
.. _Daniel Odermatt: https://www.eawag.ch/de/ueberuns/portraet/organisation/mitarbeitende/profile/daniel-odermatt/show/
.. _example.ini: https://renkulab.io/gitlab/odermatt/sentinel-hindcast/blob/master/environments/example.ini
.. _WKT: https://en.wikipedia.org/wiki/Well-known_text_representation_of_geometry



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
