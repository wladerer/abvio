import unittest
import yaml
import os
import abvio.io as io

from pathlib import Path



base_path = Path(__file__).parent
structure_dir = os.path.join(base_path, 'structures')
files_dir = os.path.join(base_path, 'files')
vaspset_dir = os.path.join(base_path, 'vaspset')



class TestLoadFunction(unittest.TestCase):
    """Contains tests that check if read can load files correctly"""

    def test_load_invalid_file(self):
        """Test if load can read an invalid yaml file"""

        invalid_file = os.path.join(files_dir, 'invalid.yaml')

        with self.assertRaises(yaml.scanner.ScannerError):
            io.load(invalid_file)

    def test_load_invalid_yaml(self):
        """Test if load can read an invalid yaml file"""

        invalid_file = os.path.join(files_dir, 'invalid.yaml')

        with self.assertRaises(yaml.YAMLError):
            io.load(invalid_file)
    




if __name__ == '__main__':
    unittest.main()