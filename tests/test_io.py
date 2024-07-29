import unittest
import yaml
import os
import abvio.io as io

from pymatgen.io.vasp import Poscar
from pymatgen.core import Lattice
from pathlib import Path


import numpy as np



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
    


class TestFormatingFunctions(unittest.TestCase):
    """Contains tests that check if read can format species correctly"""

    def test_format_species_dict(self):
        """Test if format_species can format a list of dictionaries"""

        species = [{'Fe': 2}, {'O': 4}]
        formatted_species = io.format_species(species)

        self.assertEqual(formatted_species, ['Fe', 'Fe', 'O', 'O', 'O', 'O'])

    
    def test_single_species(self):
        """Test if format_species can format a single species"""

        species = ['Fe']
        formatted_species = io.format_species(species)

        self.assertEqual(formatted_species, ['Fe'])

    def test_format_species_list(self):
        """Test if format_species can format a list of strings"""

        species = ['Fe', 'O']
        formatted_species = io.format_species(species)

        self.assertEqual(formatted_species, ['Fe', 'O'])

    def test_format_species_invalid(self):
        """Test if format_species raises an error for invalid input"""

        invalid_species = ['Fe', 2, {4,0}, {4:0}, [{4:0}]]

        for species in invalid_species:
            with self.assertRaises(ValueError):
                io.format_species(species)

    def test_format_poscar_info(self):
        """Test if format_poscar_info can format a dictionary"""

        poscar_dict = {
            'lattice': [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            'coords': [[0, 0, 0], [0.5, 0.5, 0.5]],
            'species': [{'Fe': 2}, {'O': 4}]
        }

        formatted_dict = io.format_poscar_info(poscar_dict)

        self.assertIsInstance(formatted_dict['lattice'], np.ndarray)
        self.assertIsInstance(formatted_dict['coords'], np.ndarray)
        self.assertIsInstance(formatted_dict['species'], list)

    def test_format_poscar_info_from_file(self):
        """Test if format_poscar_info can format a dictionary from a file"""

        poscar_file = os.path.join(files_dir, 'valid.yaml')
        poscar_dict = io.load(poscar_file)['poscar']

        formatted_dict = io.format_poscar_info(poscar_dict)

        self.assertIsInstance(formatted_dict['lattice'], np.ndarray)
        self.assertIsInstance(formatted_dict['coords'], np.ndarray)
        self.assertIsInstance(formatted_dict['species'], list)
    


class TestReadFunction(unittest.TestCase):

    def test_read_valid_file(self):
        """Test if load can read a valid yaml file"""

        valid_file = os.path.join(files_dir, 'valid.yaml')
        data = io.read(valid_file)

        self.assertIsInstance(data, dict)

    def test_read_valid_lattice_array(self):
        """Test if read can read a lattice array from file"""

        lattice_file = os.path.join(files_dir, 'lattice_array.yaml')
        structure_dict = io.read(lattice_file)['poscar']

        self.assertIsInstance(structure_dict['lattice'], np.ndarray)
        self.assertIsInstance(structure_dict['coords'], np.ndarray)
        self.assertIsInstance(structure_dict['species'], list)

        for specie in structure_dict['species']:
            self.assertIsInstance(specie, str)
    
    def test_read_valid_lattice_list(self):
        """Test if read can read a lattice list from file"""

        lattice_file = os.path.join(files_dir, 'lattice_list.yaml')
        structure_dict = io.read(lattice_file)['poscar']

        self.assertIsInstance(structure_dict['lattice'], np.ndarray)
        self.assertIsInstance(structure_dict['coords'], np.ndarray)
        self.assertIsInstance(structure_dict['species'], list)

        for specie in structure_dict['species']:
            self.assertIsInstance(specie, str)

if __name__ == '__main__':
    unittest.main()