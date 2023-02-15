import sys
import shutil
import os.path
import argparse
from main import sencast
from utils.auxil import init_hindcast


def test_installation(env, delete):
    if delete:
        _, params_s3, l2_path_s3 = init_hindcast(env, 'test_S3_processors.ini')
        shutil.rmtree(l2_path_s3)
    try:
        sencast('test_S3_processors.ini', env_file=env)
    except Exception as e:
        print("Some S3 processors failed")
        print(e)

    if delete:
        _, params_s2, l2_path_s2 = init_hindcast(env, 'test_S2_processors.ini')
        shutil.rmtree(l2_path_s2)
    try:
        sencast('test_S2_processors.ini', env_file=env)
    except Exception as e:
        print("Some S2 processors failed")
        print(e)

    if delete:
        _, params_l8, l2_path_l8 = init_hindcast(env, 'test_L8_processors.ini')
        shutil.rmtree(l2_path_l8)
    try:
        sencast('test_L8_processors.ini', env_file=env)
    except Exception as e:
        print("Some L8 processors failed.")
        print(e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--environment', '-e', help="Absolute path to environment file", type=str, default=None)
    parser.add_argument('--delete_tests', '-x', help="Delete previous test run.", action='store_true')
    args = parser.parse_args()
    variables = vars(args)
    if variables["environment"] is None:
        raise ValueError("Sencast test FAILED. Link to environment file must be provided.")
    test_installation(variables["environment"], variables["delete_tests"])
