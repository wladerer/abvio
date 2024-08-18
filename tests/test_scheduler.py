import unittest
from unittest.mock import patch, mock_open
from pydantic import ValidationError

from abvio.scheduler import Job, resolve_aliases, update_job_parameters_with_nodes, JOB_PARAMETERS

# Assume the Job class and other necessary functions have been imported
# from your_module import Job, JOB_PARAMETERS, resolve_aliases, update_job_parameters_with_nodes

class TestJob(unittest.TestCase):
    
    def test_valid_job_creation(self):
        directives_dict = {
            'shebang': '#!/bin/bash',
            'script': ['echo "Hello World"', 'echo "Goodbye"'],
            'cores': 4,
            'memory': '8G'
        }
        job = Job(scheduler='pbs', directives_dict=directives_dict)
        self.assertEqual(job.scheduler, 'pbs')
        self.assertEqual(job.shebang, '#!/bin/bash')
        self.assertEqual(job.script, ['echo "Hello World"', 'echo "Goodbye"'])
        self.assertIn('cores', job.directives_dict)
        self.assertIn('memory', job.directives_dict)
        
    def test_invalid_shebang(self):
        directives_dict = {
            'shebang': 'bin/bash',
            'script': ['echo "Hello World"']
        }
        with self.assertRaises(ValidationError) as context:
            Job(scheduler='slurm', directives_dict=directives_dict)

    def test_invalid_script(self):
        directives_dict = {
            'shebang': '#!/bin/bash',
            'script': 'echo "Hello World"'
        }
        with self.assertRaises(ValidationError) as context:
            Job(scheduler='pbs', directives_dict=directives_dict)

    def test_scheduler_validation(self):
        directives_dict = {
            'shebang': '#!/bin/bash',
            'script': ['echo "Hello World"']
        }
        with self.assertRaises(ValidationError) as context:
            Job(scheduler='invalid_scheduler', directives_dict=directives_dict)

    def test_alias_resolution(self):
        directives_dict = {
            'num_cores': 4,
            'mem': '8G',
            'script': ['echo "Hello World"']
        }
        resolved_dict = resolve_aliases(directives_dict, JOB_PARAMETERS)
        self.assertEqual(resolved_dict['cores'], 4)
        self.assertEqual(resolved_dict['memory'], '8G')

    def test_update_job_parameters_with_nodes_slurm(self):
        job_parameters = {}
        extra_parameters = {'nodes': 2}
        updated_parameters = update_job_parameters_with_nodes(job_parameters, extra_parameters, 'slurm')
        self.assertIn('job_extra_directives', updated_parameters)
        self.assertIn("--nodes=2", updated_parameters['job_extra_directives'])

    def test_update_job_parameters_with_nodes_pbs(self):
        job_parameters = {}
        extra_parameters = {'nodes': 2}
        updated_parameters = update_job_parameters_with_nodes(job_parameters, extra_parameters, 'pbs')
        self.assertIn('job_extra_directives', updated_parameters)
        self.assertIn("-l nodes=2", updated_parameters['job_extra_directives'])

    def test_str_method(self):
        directives_dict = {
            'cores': 4,
            'memory': '8G',
            'shebang': '#!/bin/bash',
            'script': ['echo "Hello World"']
        }
        job = Job(scheduler='pbs', directives_dict=directives_dict)
        expected_str = '#!/bin/bash\n' + job.directives + '\necho "Hello World"'
        self.assertEqual(str(job), expected_str)

    @patch('builtins.open', new_callable=mock_open)
    def test_to_file(self, mock_open):
        directives_dict = {
            'cores': 4,
            'memory': '8G',
            'shebang': '#!/bin/bash',
            'script': ['echo "Hello World"']
        }
        job = Job(scheduler='slurm', directives_dict=directives_dict)
        job.to_file('test_job.sh')
        mock_open.assert_called_once_with('test_job.sh', 'w')
        mock_open().write.assert_called_once_with(str(job))
    
    def test_from_dict(self):
        job_dict = {
            'scheduler': 'slurm',
            'directives_dict': {
                'nodes': 2,
                'cores': 4,
                'memory': '8G',
                'shebang': '#!/bin/bash',
                'script': ['echo "Hello World"', '"Goodbye World"']
            }
        }
        job = Job.from_dict(job_dict)
        self.assertEqual(job.scheduler, 'slurm')
        self.assertEqual(job.shebang, '#!/bin/bash')
        self.assertEqual(job.script, ['echo "Hello World"', '"Goodbye World"'])
        self.assertIn('cores', job.directives_dict)
        self.assertIn('memory', job.directives_dict)

if __name__ == '__main__':
    unittest.main()

