import boto3

s3 = boto3.resource('s3',
                    aws_access_key_id="",
                    aws_secret_access_key="",
                    endpoint_url="https://eodata.cloudferro.com", )
bucket = s3.Bucket("DIAS")
prefix = "Sentinel-2/MSI/L1C/2023/06/10/S2B_MSIL1C_20230610T101609_N0509_R065_T32TLS_20230610T122126.SAFE"
print(list(bucket.objects.filter(Prefix=prefix)))