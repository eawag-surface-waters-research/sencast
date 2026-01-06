.. _cscs:

------------------------------------------------------------------------------------------
CSCS
------------------------------------------------------------------------------------------

The following section provides details on how to run Sencast on the supercomputer Alps Eiger at CSCS.

Register for an account
-------------------------

Get access permission from your local IT Admin.
You will be required to set up multifactor authentication

Access using Jupyter
-------------------------

- Login at https://jupyter.cscs.ch/
- Select `Node Type = Multicore`
- Click `Launch Jupyterlab`
- Select `Terminal`

Access using ssh
-------------------------
This access is only valid for 24 hours after which the process will need to be repeated.

- Login at https://sshservice.cscs.ch/
- Click `Get a signed key` follow the instructions and download the private and public key
- Move the keys to your users `.ssh` directory

.. code-block:: bash

   mv /downloads/location/cscs-key-cert.pub ~/.ssh/cscs-key-cert.pub
   mv /download/location/cscs-key ~/.ssh/cscs-key
   chmod 0600 ~/.ssh/cscs-key

- Login to the CSCS entrance server

.. code-block:: bash

   ssh -A username@ela.cscs.ch

- Switch to Alps Eiger

.. code-block:: bash

   ssh username@eiger.cscs.ch


Install Sencast
-------------------------

This step must be completed on the command line after logging in using one of the above methods. This only needs to be performed once.

Create environmental definition file (EDF)

Create file `${HOME}/.edf/sencast.toml`

.. code-block:: bash

    image = "eawag/sencast:latest"
    mounts = [
        "${SCRATCH}/DIAS:/DIAS",
        "${HOME}/sencast:/sencast"
    ]
    workdir = "/sencast"
    entrypoint = false

Clone the repo for sencast to your user area:

.. code-block:: bash

   cd ~
   git clone https://github.com/eawag-surface-waters-research/sencast.git

Add docker.ini environment file to sencast/environments/

Move to the scratch drive and create an output folder. **Don't save large amounts of data to user area**,
data stored in the scratch drive is removed after 30 days.

.. code-block:: bash

   cd ${SCRATCH}
   mkdir DIAS

Run Sencast
-------------

The first step is to check that the environment is working correctly by running the tests.

.. code-block:: bash

    srun --environment=sencast bash -c "source /opt/conda/etc/profile.d/conda.sh && conda activate sencast && python -u /sencast/main.py -e docker.ini -t"

Create a submission script containing the following (adjust details to match your user) - make sure you are writing to scratch.

.. code-block:: bash

   vim run.sh

.. code-block:: bash

    #!/bin/bash
    #SBATCH --job-name=sencast
    #SBATCH --time=01:00:00
    #SBATCH --nodes=1
    #SBATCH --ntasks=1
    #SBATCH --account=<your-account>
    srun --environment=sencast bash -c "source /opt/conda/etc/profile.d/conda.sh && conda activate sencast && python -u /sencast/main.py -e docker.ini -p example.ini"

Then you can run Sencast:

.. code-block:: bash

   sbatch run.sh


See the status of your job:

.. code-block:: bash

   squeue -u username

You get an email when the job begins and if it fails. A live log is deposited in the directory from where you start the run.


