from dask_jobqueue.pbs import PBSJob
from dask_jobqueue.slurm import SLURMJob


def job_type_from_scheduler(scheduler: str):
    if scheduler.lower() == "pbs":
        return PBSJob
    elif scheduler.lower() == "slurm":
        return SLURMJob
    else:
        raise ValueError(f"Unsupported scheduler: {scheduler}")


def remove_dask_command(dask_jobscript: str) -> str:
    """Formats dask job script to remove dask command

    Args:
        initial_jobscript (str): Initial job script produced by dask_jobqueue

    Returns:
        str: Formatted job script without dask command
    """
    
    script = []
    for line in dask_jobscript.split("\n")[:-2]:
        script.append(line)

    return "\n".join(script)

class Job:

    def __init__(self, scheduler: str, directives_dict: dict):

        self.scheduler = scheduler
        self.dask_job_object = job_type_from_scheduler(scheduler)(**directives_dict)
        self.directives = self.dask_job_object.job_header


    def __str__(self):
        return self.directives

    
    def to_file(self, filename: str):
        with open(filename, "w") as f:
            f.write(str(self))



slurm_job = Job("slurm", {"queue": "batch", "cores": 4, "memory": "16GB", "walltime": "00:30:00"})

print(slurm_job)

        

        



    