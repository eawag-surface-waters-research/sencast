import sys
import shutil
import os.path

sys.path.append("/sencast")

from main import hindcast
from utils.auxil import init_hindcast

MIN_EXPETED_FILE_SIZE_BYTES = 4 * 1024


def report(l2product_files, params, report_name):
    with open(report_name, 'w') as report_file:
        print('Report:')
        report_file.write('Report:\n')
        for group in l2product_files:
            print('Group: {}'.format(group))
            report_file.write('Group: {}\n'.format(group))
            for processor in params['General']['processors'].split(','):
                if processor not in l2product_files[group]:
                    print('Processor: {} failed! (no output)'.format(processor))
                    report_file.write('Processor: {} failed! (no output)\n'.format(processor))
                elif not os.path.isfile(l2product_files[group][processor]):
                    print('Processor: {} failed! (no output)'.format(processor))
                    report_file.write('Processor: {} failed! (no output)\n'.format(processor))
                elif os.stat(l2product_files[group][processor]).st_size < MIN_EXPETED_FILE_SIZE_BYTES:
                    print('Processor: {} failed! (empty output)'.format(processor))
                    report_file.write('Processor: {} failed! (empty output)\n'.format(processor))
                else:
                    print('Processor: {} successful'.format(processor))
                    report_file.write('Processor: {} successful!\n'.format(processor))


_, params_s3, l2_path_s3 = init_hindcast(None, 'test_S3_processors.ini')
shutil.rmtree(l2_path_s3)
os.mkdir(l2_path_s3)
l2product_files_s3 = hindcast('test_S3_processors.ini')
report(l2product_files_s3, params_s3, 'ReportS3.log')

_, params_s2, l2_path_s2 = init_hindcast(None, 'test_S2_processors.ini')
shutil.rmtree(l2_path_s2)
os.mkdir(l2_path_s2)
l2product_files_s2 = hindcast('test_S2_processors.ini')
report(l2product_files_s2, params_s2, 'ReportS2.log')

_, params_l8, l2_path_l8 = init_hindcast(None, 'test_L8_processors.ini')
shutil.rmtree(l2_path_l8)
os.mkdir(l2_path_l8)
l2product_files_l8 = hindcast('test_L8_processors.ini')
report(l2product_files_l8, params_l8, 'ReportL8.log')

