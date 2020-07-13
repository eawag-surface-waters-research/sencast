.. _parameters:

------------------------------------------------------------------------------------------
Parameter File
------------------------------------------------------------------------------------------

Parameter files use the INI format and contain the parameters for one
execution of Sencast.

Example parameter files for processing data from Sentinel 2 and Sentinel 3 are provided below:

- https://gitlab.com/eawag-rs/sencast/-/blob/master/parameters/parameters_template_S2.ini
- https://gitlab.com/eawag-rs/sencast/-/blob/master/parameters/parameters_template_S3.ini

Environment files use the INI format and contain the configuration of the machine on which Sencast runs.

You should create your own environment file for every machine you install Sencast on.

The file should be place in the environments folder and name "your computer name".ini if for some reason this is not
possible you should pass the location of your environment file to the sencast main function.

The following example environment file should be adaptable for any use cases.

https://gitlab.com/eawag-rs/sencast/-/blob/master/environments/example.ini