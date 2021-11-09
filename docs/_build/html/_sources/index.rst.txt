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
  conda env create -f environment.yml

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

Following flow chart illustrates how sencast works.

.. image:: flowchart.png
    :width: 800px
    :alt: Sencast Flow Chart
    :align: center

Sencast offers two interfaces to process data.

-  The file-based interface takes a parameter file and an optional
   environment file as input. It reads the file contents and calls the
   object based interface with the read configurations.
-  The object-based interface directly takes an environment and a
   parameters object as well as a path for the L1 (input) products and a
   path for the L2 (output) products.

From the command line only the file-based interface is available.
Use it as follows:

python main.py [parameters file] [(optional) environment file]

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

.. toctree::
   :maxdepth: 2
   :caption: Installation

   install/ubuntu18_install.rst
   install/centos8_install.rst
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
   processors/mph.rst
   processors/ndwi.rst
   processors/oc3.rst
   processors/polymer.rst
   processors/primaryproduction.rst
   processors/secchidepth.rst
   processors/sen2cor.rst

.. toctree::
   :maxdepth: 2
   :caption: Adapters

   adapters/merge.rst
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
