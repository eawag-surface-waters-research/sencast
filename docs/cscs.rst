.. _cscs:

------------------------------------------------------------------------------------------
CSCS
------------------------------------------------------------------------------------------

The following section provides details on how to run Sencast on the supercomputer Piz Daint at CSCS.

Register for an account
-------------------------

Get access permission to Daint from your local IT Admin.
You will be required to set up multifactor authentication

Access using Jupyter
-------------------------

- Login at https://jupyter.cscs.ch/
- Select `Node Type = Multicore`
- Click `Launch Jupyterlab`
- Select `Terminal`

Access using ssh
-------------------------
This access is only valid for 24 hours after which the process will need to be repeated. For details on how to automate see here: https://user.cscs.ch/access/auth/mfa and for Windows see here: https://user.cscs.ch/access/auth/mfa/windows

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

- Switch to Piz Daint

.. code-block:: bash

   ssh username@daint.cscs.ch


Install Sencast
-------------------------

This step must be completed on the command line after logging into Piz Daint using one of the above methods.

Load the required modules

.. code-block:: bash

   module load daint-mc
   module load sarus

Clone the repo for sencast to your user area:

.. code-block:: bash

   cd ~
   git clone https://github.com/eawag-surface-waters-research/sencast.git

Update the environment and parameters scripts that you want to run.

Pull the image you want from dockerhub:

.. code-block:: bash

   srun -C mc -A em09 sarus pull --login eawag/sencast:0.0.2

then enter your credentials for the repository (There is no prompt)

`<username>`
`<password>`

The docker image (now for sarus) is automatically saved in ${SCRATCH}/.sarus

If this fails try running the command again.

Run Sencast
-------------

Move to the scratch drive and create an output folder **don't save large amounts of data to user area**
Data stored in the scratch drive is removed after 30 days.

.. code-block:: bash

   cd ${SCRATCH}
   mkdir DIAS

Create a submission script containing the following (adjust details to match your user) - make sure you are writing to scratch.

.. code-block:: bash

   vim run.sh

.. code-block:: bash

   #!/bin/bash -l
   #SBATCH --job-name="sencast"
   #SBATCH --account="em09"
   #SBATCH --mail-type=ALL
   #SBATCH --mail-user=username@eawag.ch
   #SBATCH --time=24:00:00
   #SBATCH --nodes=1
   #SBATCH --ntasks-per-core=1
   #SBATCH --ntasks-per-node=1
   #SBATCH --cpus-per-task=36
   #SBATCH --partition=normal
   #SBATCH --constraint=mc
   #SBATCH --hint=nomultithread
   export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK
   module load daint-mc
   module load sarus
   image='eawag/sencast:0.0.2'
   envvars='docker.ini'
   params='parameters.ini'
   filepath="${SCRATCH}/DIAS"

.. code-block:: bash

   cd ~/sencast
   srun sarus run --mount=type=bind,source=${filepath},destination=/DIAS --mount=type=bind,source=$(pwd),dst=/sencast ${image} -e ${envvars} -p ${params}


`:w` save file

`:q` exit vim

Then you can run Sencast:

.. code-block:: bash

   sbatch run.sh


See the status of your job:

.. code-block:: bash

   squeue -u username

You get an email when the job begins and if it fails. A live log is deposited in the directory from where you start the run.


