
import unittest
import os
from pathlib import Path
from dask_jobqueue.pbs import PBSJob
from dask_jobqueue.slurm import SLURMJob

import abvio.scheduler as scheduler

base_path = Path(__file__).parent
files_dir = os.path.join(base_path, "files")

class TestFileCreation(unittest.TestCase):
    def test_job_type_from_scheduler(self):
        """Tests if the job_type_from_scheduler function returns the correct job type"""
        self.assertEqual(scheduler.job_type_from_scheduler("pbs"), PBSJob)
        self.assertEqual(scheduler.job_type_from_scheduler("slurm"), SLURMJob)

    def test_job_creation(self):
        """Tests if the Job class can create a job object"""
        directives = {
            "queue": "regular",
            "walltime": "00:30:00",
            "cores": 3,
            "memory": "2GB",
            "job_name": "test_job"
        }

        pbs_job = scheduler.Job("pbs", directives)
        slurm_job = scheduler.Job("slurm", directives)
        self.assertIsInstance(pbs_job.dask_job_object, PBSJob)
        self.assertIsInstance(slurm_job.dask_job_object, SLURMJob)

    def test_write_to_file(self):
        """Tests if the Job class can write the job script to a file"""
        directives = {
            "queue": "regular",
            "walltime": "00:30:00",
            "cores": 3,
            "memory": "2GB",
            "job_name": "test_job"
        }

        pbs_job = scheduler.Job("pbs", directives)
        slurm_job = scheduler.Job("slurm", directives)

        pbs_job.to_file(os.path.join(files_dir, "pbs_job.sh"))
        slurm_job.to_file(os.path.join(files_dir, "slurm_job.sh"))

        self.assertTrue(os.path.exists(os.path.join(files_dir, "pbs_job.sh")))
        self.assertTrue(os.path.exists(os.path.join(files_dir, "slurm_job.sh")))
        
        os.remove(os.path.join(files_dir, "pbs_job.sh"))
        os.remove(os.path.join(files_dir, "slurm_job.sh"))





if __name__ == "__main__":
    unittest.main()        
    
