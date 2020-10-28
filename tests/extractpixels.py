from postprocess.pixelextraction.pixelextration import pixelextration

folder = "/media/jamesrunnalls/JamesSSD/Eawag/EawagRS/Sencast"
coords = [{"name": "A", "lat": 46.44829, "lng": 6.561426}]
files = ["/media/jamesrunnalls/JamesSSD/Eawag/EawagRS/Sencast/build/DIAS/output_data/datalakes_sui_S3_sui_2018-06-01_2018-06-07/L2PP/L2PP_L2SD_L2POLY_L1P_reproj_ERA5_S3A_OL_1_EFR____20180601T102022_20180601T102322_20180602T152636_0180_032_008_2160_LN1_O_NT_002.SEN3.nc",
          "/media/jamesrunnalls/JamesSSD/Eawag/EawagRS/Sencast/build/DIAS/output_data/datalakes_sui_S3_sui_2018-06-01_2018-06-07/L2PP/L2PP_L2SD_L2POLY_L1P_reproj_ERA5_S3A_OL_1_EFR____20180602T095411_20180602T095711_20180603T144256_0180_032_022_2160_LN1_O_NT_002.SEN3.nc",
          "/media/jamesrunnalls/JamesSSD/Eawag/EawagRS/Sencast/build/DIAS/output_data/datalakes_sui_S3_sui_2018-06-01_2018-06-07/L2PP/L2PP_L2SD_L2POLY_L1P_reproj_ERA5_S3A_OL_1_EFR____20180603T092800_20180603T093100_20180604T140652_0179_032_036_2160_LN1_O_NT_002.SEN3.nc"]

pixelextration(files, coords, folder)