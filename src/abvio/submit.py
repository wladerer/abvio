from dask_jobqueue.pbs import PBSJob
from dask_jobqueue.slurm import SLURMJob


def job_type_from_scheduler(scheduler: str):
    if scheduler == "pbs":
        return PBSJob
    elif scheduler == "slurm":
        return SLURMJob
    else:
        raise ValueError(f"Unsupported scheduler: {scheduler}")

class Job:

    def __init__(self, scheduler: str, directives: dict):

        self.scheduler = scheduler
        self.job = job_type_from_scheduler(scheduler)(**directives)


    def to_file(self, filename: str = 'submit.sh'):
        """Writes the job script to a file"""

        with open(filename, "w") as f:
            #write each line except the last one
            for line in self.job.job_script().split("\n")[:-2]:
                f.write(line + "\n")
                


pbs_job = Job("slurm", {"cores": 3, "memory": "2GB", "queue": "regular", "walltime": "00:30:00", "job_name": "test_job"})
pbs_job.to_file("slurm_submit.sh")



    