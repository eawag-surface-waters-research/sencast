import os
import json
import time
import argparse
import subprocess
import configparser
from datetime import datetime, timedelta


def reprocess(parameters):
    job_file = "{}_{}_{}.json".format(parameters["parameters"], parameters["start"], parameters["end"])
    if not os.path.isfile(job_file):
        print("Creating job file")
        job_list = []
        start_date = datetime.strptime(parameters["start"], "%Y%m%d")
        end_date = datetime.strptime(parameters["end"], "%Y%m%d")
        current_date = end_date
        while current_date >= start_date:
            job_list.append(current_date.strftime("%Y%m%d"))
            current_date -= timedelta(days=1)
    else:
        print("Reading existing job file")
        with open(job_file, 'r') as f:
            job_list = json.load(f)

    params = configparser.ConfigParser()
    params.read("parameters/{}.ini".format(parameters["parameters"]))

    for job in job_list.copy():
        try:
            print("Running: {}".format(job))
            job_parameter_file = "{}_{}.ini".format(parameters["parameters"], job)
            formatted_date = datetime.strptime(job, "%Y%m%d").strftime("%Y-%m-%d")
            start = "{}T00:00:00.000Z".format(formatted_date)
            end = "{}T23:59:59.999Z".format(formatted_date)
            params['General']['start'] = start
            params['General']['end'] = end
            with open(os.path.join("parameters", job_parameter_file), "w") as f:
                params.write(f)

            cmd = ['docker', 'run', '-v', '{}:/DIAS'.format(parameters["dias"]), '-v', '{}:/sencast'.format(os.getcwd()),
                   '--rm', '-i', parameters["docker"], '-e', 'docker.ini', '-p', job_parameter_file, '-d',
                   str(parameters["downloads"]), '-r', str(parameters["processors"]), '-a', str(parameters["adapters"])]
            start_time = time.time()
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"Elapsed Time: {time.time() - start_time} seconds")

            if result.returncode == 0:
                job_list.remove(job)
                with open(job_file, 'w') as json_file:
                    json.dump(job_list, json_file)
                os.remove(os.path.join("parameters", job_parameter_file))
            else:
                print("Failed for {}".format(job))
        except Exception as e:
            print("Failed for {}".format(job))
            print(e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--parameters', '-p', help="Template parameter file", type=str)
    parser.add_argument('--environment', '-e', help="Absolute path to environment file", type=str, default=None)
    parser.add_argument('--downloads', '-d', help="Maximum number of parallel downloads of satellite images", type=int, default=1)
    parser.add_argument('--processors', '-r', help="Maximum number of processors to run in parallel", type=int, default=1)
    parser.add_argument('--adapters', '-a', help="Maximum number of adapters to run in parallel", type=int, default=1)
    parser.add_argument('--docker', '-de', help="Docker image", type=str, default="eawag/sencast:0.0.2")
    parser.add_argument('--start', '-s', help="Start date YYYYMMDD", type=str)
    parser.add_argument('--end', '-f', help="End date YYYYMMDD", type=str)
    parser.add_argument('--dias', '-ds', help="Absolute path to DIAS folder", type=str)
    args = parser.parse_args()
    reprocess(vars(args))
