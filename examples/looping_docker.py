#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Import libs, some of them might be unused here, but something magical happens when they are imported
# which causes geos_c.dll and objectify.pyx errors to disappear in windows.

import os
import sys
import configparser
from datetime import datetime, timedelta
import subprocess
sys.path.append("/sencast")

ini_file = '/home/jrunnalls/sencast/parameters/datalakes_sui_S2.ini'
dias = "/home/jrunnalls/DIAS"
sencast = "/home/jrunnalls/sencast"

wkts = ["alplakes"]
start_date = datetime(2023, 6, 1)
end_date = datetime(2023, 7, 1)
dates = [(start_date + timedelta(days=x)).strftime("%Y-%m-%d") for x in range((end_date - start_date).days + 1)]

config = configparser.ConfigParser()
config.read(ini_file)

for date in dates:
    for wkt in wkts:
        try:
            print("Running Sencast for {} on {}".format(wkt, date))
            config["General"]["wkt_name"] = wkt
            config["General"]["start"] = "{}T00:00:00.000Z".format(date)
            config["General"]["end"] = "{}T23:59:59.999Z".format(date)

            with open(ini_file, 'w') as configfile:
                config.write(configfile)

            docker_command = ["docker", "run", "-v", "{}:/DIAS".format(dias), "-v", "{}:/sencast".format(sencast),
                              "--rm", "eawag/sencast:0.0.1", "-e", "docker.ini", "-p", os.path.basename(ini_file)]
            print(" ".join(docker_command))

            with subprocess.Popen(docker_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1,
                                  universal_newlines=True) as proc:
                for line in proc.stdout:
                    print(line, end='')
                proc.wait()
                print(f"Process finished with exit code {proc.returncode}")
                if proc.returncode != 0:
                    print("Error output:", proc.stderr.read())
        except Exception as e:
            print(f"An error occurred: {e}")
