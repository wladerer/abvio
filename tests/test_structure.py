import unittest
import os

import numpy as np
import abvio.structure as st
import abvio.io as io

from pymatgen.io.vasp import Poscar
from pymatgen.core import Structure, Lattice
from pathlib import Path

base_path = Path(__file__).parent
structure_dir = os.path.join(base_path, 'structures')
files_dir = os.path.join(base_path, 'files')

def matrix_similarity(matrix1: np.ndarray, matrix2: np.ndarray, tol: float = 1e-6) -> bool:
    """Check if two matrices are similar within a tolerance"""
    return np.allclose(matrix1, matrix2, atol=tol)


class TestFormatingFunctions(unittest.TestCase):
    """Contains tests that check if read can format species correctly"""

    def test_format_species_dict(self):
        """Test if format_species can format a list of dictionaries"""

        species = [{'Fe': 2}, {'O': 4}]
        formatted_species = st.format_species(species)

        self.assertEqual(formatted_species, ['Fe', 'Fe', 'O', 'O', 'O', 'O'])

    
    def test_single_species(self):
        """Test if format_species can format a single species"""

        species = ['Fe']
        formatted_species = st.format_species(species)

        self.assertEqual(formatted_species, ['Fe'])

    def test_format_species_list(self):
        """Test if format_species can format a list of strings"""

        species = ['Fe', 'O']
        formatted_species = st.format_species(species)

        self.assertEqual(formatted_species, ['Fe', 'O'])

    def test_format_species_invalid(self):
        """Test if format_species raises an error for invalid input"""

        invalid_species = ['Fe', 2, {4,0}, {4:0}, [{4:0}]]

        for species in invalid_species:
            with self.assertRaises(ValueError):
                st.format_species(species)


class TestBaseStructure(unittest.TestCase):

    def test_valid_base_structure(self):
        
        st.BaseStructure(mode="external")
        st.BaseStructure(mode="manual")
        st.BaseStructure(mode="prototype")

        st.BaseStructure(mode="external", file="POSCAR")
        st.BaseStructure(mode="external", code="mp-1234")
        st.BaseStructure(mode="external", code="1234")

    def test_invalid_base_structures(self):

        with self.assertRaises(ValueError):

            st.BaseStructure(mode="internal")

        with self.assertRaises(ValueError):
            st.BaseStructure(mode="wrong")

        with self.assertRaises(ValueError):
            st.BaseStructure(mode="JohnCena")


class TestManualStructure(unittest.TestCase):

    def test_valid_manual_structure(self):

        lattice = Lattice.from_parameters(a=1, b=1, c=1, alpha=90, beta=90, gamma=90)
        species = ["Mg", "O"]
        coords = [[0, 0, 0], [0.5, 0.5,0.5]]

        model = st.ManualStructure(lattice=lattice, species=species, coords=coords)
        structure = model.structure

        self.assertIsInstance(structure, Structure)

    def test_valid_manual_structure_from_array(self):

        lattice = [
            [1, 0, 0],
            [0, 1, 0],
            [0, 0, 1]
        ]
        species = ["Mg", "O"]
        coords = [[0, 0, 0], [0.5, 0.5,0.5]]

        model = st.ManualStructure(lattice=lattice, species=species, coords=coords)
        structure = model.structure

        self.assertIsInstance(structure, Structure)

    def test_valid_manual_structure_from_numpy(self):

        lattice = np.array([
            [1, 0, 0],
            [0, 1, 0],
            [0, 0, 1]
        ])
        species = ["Mg", "O"]
        coords = [[0, 0, 0], [0.5, 0.5,0.5]]

        model = st.ManualStructure(lattice=lattice, species=species, coords=coords)
        structure = model.structure

        self.assertIsInstance(structure, Structure)

    def test_invalid_manual_structure(self):

        with self.assertRaises(ValueError):

            lattice = Lattice.from_parameters(a=1, b=1, c=1, alpha=90, beta=90, gamma=120)
            species = ["Mg", "O", "Ti"]
            coords = [[0, 0, 0], [0.5, 0.5,0.5]]

            st.ManualStructure(lattice=lattice, species=species, coords=coords).structure

        with self.assertRaises(ValueError):
                
            lattice = Lattice.from_parameters(a=1, b=1, c=1, alpha=90, beta=40, gamma=90)
            species = ["Mg", "O"]
            coords = [[0, 0, 0], [0.5, 0.5,0.5], [0.5, 0.5,0.5]]

            st.ManualStructure(lattice=lattice, species=species, coords=coords).structure

    def test_manual_structure_from_file(self):
            
            filepath = os.path.join(files_dir, 'lattice_list.yaml')
            input_dict = io.load(filepath)['structure']

            model = st.ManualStructure.validate(input_dict)
            structure = model.structure

            self.assertIsInstance(structure, Structure)


class TestPrototypeStructure(unittest.TestCase):

    perovskite_dict = io.load(os.path.join(files_dir, 'prototype_perovskite.yaml'))['structure']
    fluorite_dict = io.load(os.path.join(files_dir, 'prototype_fluorite.yaml'))['structure']

    pervoskite_structure = Structure.from_file(os.path.join(structure_dir, 'CaTiO3.vasp'))
    fluorite_structure = Structure.from_file(os.path.join(structure_dir, 'CaF2.vasp'))

    def test_valid_pervoskite_structure(self):
        """Compares a known structure with the one generated by the prototype structure"""

        species = self.perovskite_dict['species']
        lattice = self.perovskite_dict['lattice']
        prototype = self.perovskite_dict['prototype']

        model = st.PrototypeStructure(species=species, lattice=lattice, prototype=prototype)
        structure = model.structure

        self.assertIsInstance(structure, Structure)
        self.assertTrue(matrix_similarity(structure.lattice.matrix, self.pervoskite_structure.lattice.matrix))

    def test_valid_fluorite_structure(self):
        """Compares a known structure with the one generated by the prototype structure"""

        species = self.fluorite_dict['species']
        lattice = self.fluorite_dict['lattice']
        prototype = self.fluorite_dict['prototype']

        model = st.PrototypeStructure(species=species, lattice=lattice, prototype=prototype)
        structure = model.structure

        self.assertIsInstance(structure, Structure)
        self.assertTrue(matrix_similarity(structure.lattice.matrix, self.fluorite_structure.lattice.matrix))


class TestStructureFromMaterialProject(unittest.TestCase):

    def test_valid_code(self):
    
        stucture = st.structure_from_mpi_code("mp-5827")
        self.assertIsInstance(stucture, Structure)

class TestExternalStructure(unittest.TestCase):

    def test_model_from_file(self):

        files = [ 'CaTiO3.vasp', 'CaF2.vasp'] 

        for file in files:
            model = st.ExternalStructure(file=os.path.join(structure_dir, file))
            structure = model.structure

            self.assertIsInstance(structure, Structure)


    def test_model_from_string(self):

        string = Poscar.from_file(os.path.join(structure_dir, 'CaTiO3.vasp')).__str__()

        model = st.ExternalStructure(string=string)
        structure = model.structure

        self.assertIsInstance(structure, Structure)


    def test_model_from_materials_project(self):

        model = st.ExternalStructure(code="mp-5827")
        structure = model.structure
        
        self.assertIsInstance(structure, Structure)


class TestStructureFromInputDict(unittest.TestCase):

    def test_valid_input_dict(self):

        input_dict = {
            "mode": "external",
            "file": os.path.join(structure_dir, 'CaTiO3.vasp')
        }

        model = st.structure_model_from_input_dict(input_dict)
        structure = model.structure
        self.assertIsInstance(structure, Structure)

    def test_invalid_input_dict(self):

        input_dict = {
            "mode": "external",
            "file": os.path.join(structure_dir, 'CaTiO3.vasp'),
            "string": "string"
        }

        with self.assertRaises(ValueError):
            st.structure_model_from_input_dict(input_dict)


if __name__ == "__main__":
    unittest.main()