
import unittest
import os
from pathlib import Path
from dask_jobqueue.pbs import PBSJob
from dask_jobqueue.slurm import SLURMJob

import abvio.submit as submit

base_path = Path(__file__).parent
files_dir = os.path.join(base_path, "files")

class TestFileCreation(unittest.TestCase):
    def test_job_type_from_scheduler(self):
        """Tests if the job_type_from_scheduler function returns the correct job type"""
        self.assertEqual(submit.job_type_from_scheduler("pbs"), PBSJob)
        self.assertEqual(submit.job_type_from_scheduler("slurm"), SLURMJob)

    def test_job_creation(self):
        """Tests if the Job class can create a job object"""
        directives = {
            "queue": "regular",
            "walltime": "00:30:00",
            "cores": 3,
            "memory": "2GB",
            "job_name": "test_job"
        }

        pbs_job = submit.Job("pbs", directives)
        slurm_job = submit.Job("slurm", directives)
        self.assertIsInstance(pbs_job.job, PBSJob)
        self.assertIsInstance(slurm_job.job, SLURMJob)

        
    
