import pytest
from unittest.mock import patch, mock_open
from pydantic import ValidationError

from abvio.scheduler import Job, resolve_aliases, update_job_parameters_with_nodes, JOB_PARAMETERS


class TestJob:
    def test_valid_creation(self):
        job = Job(scheduler="pbs", directives_dict={
            "shebang": "#!/bin/bash",
            "script":  ['echo "Hello World"', 'echo "Goodbye"'],
            "cores":   4, "memory": "8G",
        })
        assert job.scheduler == "pbs"
        assert job.shebang   == "#!/bin/bash"
        assert job.script    == ['echo "Hello World"', 'echo "Goodbye"']
        assert "cores"  in job.directives_dict
        assert "memory" in job.directives_dict

    def test_invalid_shebang(self):
        with pytest.raises(ValidationError):
            Job(scheduler="slurm", directives_dict={
                "shebang": "bin/bash", "script": ['echo "Hello World"'],
            })

    def test_invalid_script_not_list(self):
        with pytest.raises(ValidationError):
            Job(scheduler="pbs", directives_dict={
                "shebang": "#!/bin/bash", "script": 'echo "Hello World"',
            })

    def test_invalid_scheduler(self):
        with pytest.raises(ValidationError):
            Job(scheduler="invalid_scheduler", directives_dict={
                "shebang": "#!/bin/bash", "script": ['echo "Hello World"'],
            })

    def test_alias_resolution(self):
        resolved = resolve_aliases({"num_cores": 4, "mem": "8G",
                                    "script": ['echo "Hello World"']},
                                   JOB_PARAMETERS)
        assert resolved["cores"]  == 4
        assert resolved["memory"] == "8G"

    def test_nodes_slurm(self):
        updated = update_job_parameters_with_nodes({}, {"nodes": 2}, "slurm")
        assert "job_extra_directives" in updated
        assert "--nodes=2" in updated["job_extra_directives"]

    def test_nodes_pbs(self):
        updated = update_job_parameters_with_nodes({}, {"nodes": 2}, "pbs")
        assert "job_extra_directives" in updated
        assert "-l nodes=2" in updated["job_extra_directives"]

    def test_str_method(self):
        job = Job(scheduler="pbs", directives_dict={
            "cores": 4, "memory": "8G",
            "shebang": "#!/bin/bash", "script": ['echo "Hello World"'],
        })
        expected = "#!/bin/bash\n" + job.directives + '\necho "Hello World"'
        assert str(job) == expected

    def test_to_file(self):
        job = Job(scheduler="slurm", directives_dict={
            "cores": 4, "memory": "8G",
            "shebang": "#!/bin/bash", "script": ['echo "Hello World"'],
        })
        with patch("builtins.open", mock_open()) as m:
            job.to_file("test_job.sh")
            m.assert_called_once_with("test_job.sh", "w")
            m().write.assert_called_once_with(str(job))

    def test_from_dict(self):
        job = Job.from_dict({
            "scheduler": "slurm",
            "directives_dict": {
                "nodes": 2, "cores": 4, "memory": "8G",
                "shebang": "#!/bin/bash",
                "script": ['echo "Hello World"', '"Goodbye World"'],
            },
        })
        assert job.scheduler == "slurm"
        assert job.shebang   == "#!/bin/bash"
        assert job.script    == ['echo "Hello World"', '"Goodbye World"']
        assert "cores"  in job.directives_dict
        assert "memory" in job.directives_dict
