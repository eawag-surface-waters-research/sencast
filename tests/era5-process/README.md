# Process ERA5 from CDS API

This notebook downloads ERA5 data from the CDS API in order to calculate PAR Irradiance for use in Primary Production calculations.

### Monthly Product

Product: reanalysis-era5-single-levels-monthly-means <br>
Product Type: monthly_averaged_reanalysis_by_hour_of_day <br>
Variable: mean_surface_downward_short_wave_radiation_flux

### Daily Product

Product: reanalysis-era5-single-levels <br>
Product Type: reanalysis <br>
Variable: mean_surface_downward_short_wave_radiation_flux

These products return mean surface downward short wave radiation flux (Wm-2) which is converted to PAR using the following equation:

PAR = DSR * 4.6 * 0.436

The downloaded products are for 9-12 in the morning and need to be averaged in order to produce daily/ monthly values. 

It is possible to compute the PAR for any location. In the example it is done for station SHL2 [46.4527, 6.58872].



