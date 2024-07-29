import unittest
import yaml
import os

from pymatgen.io.vasp import Poscar
from pathlib import Path
from abvio.io import read

import abvio.structure as astruct
import numpy as np

import logging 



base_path = Path(__file__).parent
structure_dir = os.path.join(base_path, 'structures')
files_dir = os.path.join(base_path, 'files')

def matrix_similarity(matrix1: np.ndarray, matrix2: np.ndarray, tol: float = 1e-6) -> bool:
    """Check if two matrices are similar within a tolerance"""
    return np.allclose(matrix1, matrix2, atol=tol)


class TestManualStructureFunctions(unittest.TestCase):
    """Contains tests that check if read can handle structural informaiton correctly"""
    
    def test_read_valid_lattice_array(self):
        """Test if structure_from_lattice can read a lattice array from file"""

        lattice_file = os.path.join(files_dir, 'lattice_array.yaml')
        structure_dict = read(lattice_file)['poscar']


        lattice = structure_dict['lattice']
        coords = structure_dict['coords']
        species = structure_dict['species']
        
        structure = astruct.structure_from_lattice(lattice, species, coords)


        self.assertEqual([str(specie) for specie in structure.species], species)
        self.assertTrue(matrix_similarity(structure.lattice.matrix, lattice))
        self.assertTrue(matrix_similarity(structure.cart_coords, coords))

    def test_read_valid_lattice_list(self):
        """Test if structure_from_lattice can read a lattice list from file"""

        lattice_file = os.path.join(files_dir, 'lattice_list.yaml')
        structure_dict = read(lattice_file)['poscar']


        lattice = structure_dict['lattice']
        coords = structure_dict['coords']
        species = structure_dict['species']
        
        structure = astruct.structure_from_lattice(lattice, species, coords)


        self.assertEqual([str(specie) for specie in structure.species], species)
        self.assertTrue(matrix_similarity(structure.lattice.matrix, lattice))
        self.assertTrue(matrix_similarity(structure.cart_coords, coords))

    def test_poscar_and_input_structure(self):
        """Test if structure produced from input file is the same as a POSCAR file"""
        expected_structure = Poscar.from_file(os.path.join(structure_dir, 'CaF2.poscar')).structure

        lattice_array = os.path.join(files_dir, 'lattice_array.yaml')
        structure_dict = read(lattice_array)['poscar']

        lattice = structure_dict['lattice']
        coords = structure_dict['coords']
        species = structure_dict['species']

        structure = astruct.structure_from_lattice(lattice, species, coords)

        self.assertEqual(structure, expected_structure, msg="Lattice array routine failed")

        lattice_list = os.path.join(files_dir, 'lattice_list.yaml')
        structure_dict = read(lattice_list)['poscar']

        lattice = structure_dict['lattice']
        coords = structure_dict['coords']
        species = structure_dict['species']

        structure = astruct.structure_from_lattice(lattice, species, coords)
        self.assertEqual(structure, expected_structure, msg="Lattice list routine failed")


class TestPrototypeStructureFunctions(unittest.TestCase):
    """Test if a structure can be generated from a prototype"""

    def test_fluorite_structure(self):
        """Test if structure_from_prototype can generate a fluorite structure"""

        expected_structure = Poscar.from_file(os.path.join(structure_dir, 'CaF2.poscar')).structure
        expected_species_set = set([str(specie) for specie in expected_structure.species])


        input_dict = read(os.path.join(files_dir, 'prototype_fluorite.yaml'))
        poscar_dict = input_dict['poscar']
        prototype = poscar_dict['prototype']
        species = poscar_dict['species']
        species_set = set(species)

        structure = astruct.structure_from_prototype(prototype, species)

        self.assertTrue(matrix_similarity(structure.lattice.matrix, expected_structure.lattice.matrix))
        self.assertEqual(species_set, expected_species_set)

    def test_perovskite_structure(self):
        """Test if structure_from_prototype can generate a perovskite structure"""

        expected_structure = Poscar.from_file(os.path.join(structure_dir, 'CaTiO3.poscar')).structure
        expected_species_set = set([str(specie) for specie in expected_structure.species])

        input_dict = read(os.path.join(files_dir, 'prototype_perovskite.yaml'))
        poscar_dict = input_dict['poscar']
        prototype = poscar_dict['prototype']
        species = poscar_dict['species']
        species_set = set(species)

        structure = astruct.structure_from_prototype(prototype, species)

        self.assertTrue(matrix_similarity(structure.lattice.matrix, expected_structure.lattice.matrix))
        self.assertEqual(species_set, expected_species_set)





if __name__ == '__main__':
    unittest.main()



