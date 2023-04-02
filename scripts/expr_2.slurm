#!/bin/bash
# Created by the University of Melbourne job script generator for SLURM
# Sun Apr 02 2023 17:14:31 GMT+1000 (Australian Eastern Standard Time)

# Partition for the job:
#SBATCH --partition=physical

# The name of the job:
#SBATCH --job-name="ronsuzy_1node_8core"

# The project ID which this job should run under:
#SBATCH --account="COMP90024"

# Maximum number of tasks/CPU cores used by the job:
#SBATCH --ntasks=8
#SBATCH --nodes=1-1

# The amount of memory in megabytes per cpu core:
#SBATCH --mem-per-cpu=8192

# Use this email address:
#SBATCH --mail-user=lachen1@student.unimelb.edu.au

# Send yourself an email when the job:
# aborts abnormally (fails)
#SBATCH --mail-type=FAIL
# begins
#SBATCH --mail-type=BEGIN
# ends successfully
#SBATCH --mail-type=END

# The maximum running time of the job in days-hours:mins:sec
#SBATCH --time=0-0:15:00

# check that the script is launched with sbatch
if [ "x$SLURM_JOB_ID" == "x" ]; then
   echo "You need to submit your job to the queuing system with sbatch"
   exit 1
fi

# Run the job from the directory where it was launched (default)

# The modules to load:
module load gcccore/10.2.0 python/3.7.4
module load mpi4py/3.0.2-timed-pingpong
virtualenv ~/venvs/venv-3.7.4
source ~/venvs/venv-3.7.4/bin/activate
pip install pandas


# The job command(s):
mpixec -n 8 python soln.py bigTwitter.json sal.json

##DO NOT ADD/EDIT BEYOND THIS LINE##
##Job monitor command to list the resource usage
my-job-stats -a -n -s
