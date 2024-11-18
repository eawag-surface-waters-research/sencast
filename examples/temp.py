import rioxarray # for the extension to load
import xarray
import rasterio

xds = xarray.open_dataset("/home/runnalja/Desktop/DIAS/output_data/test_Collection_processors_geneva_2022-05-21_2022-05-21/L2C/L2C_LC09_L2SP_195028_20220521_20230416_02_T1.nc", decode_coords="all")
xds = xds.rio.set_spatial_dims(x_dim='lon', y_dim='lat')
xds = xds.rio.write_crs("EPSG:32632", inplace=True)
xds_lonlat = xds.rio.reproject("EPSG:4326")
print(xds_lonlat)