import unittest
import yaml
import os 

import abvio.check as check
import abvio.io as io

from pymatgen.core.structure import Structure
from pathlib import Path

base_path = Path(__file__).parent
files_dir = os.path.join(base_path, "files")

class TestNumericalFunctions(unittest.TestCase):
    def test_magnitude(self):
        """Tests if the magnitude function returns the correct magnitude of a number"""

        test_values = [0.063, 0.1, 0.99999, 1, 19, 143, 1097, 30000, 100000, 1000000]
        expected_magnitudes = [-2, -1, -1, 0, 1, 2, 3, 4, 5, 6]

        for value, expected_magnitude in zip(test_values, expected_magnitudes):
            self.assertEqual(check.magnitude(value), expected_magnitude)

    def test_nacl_bands_estimate(self):
        """Tests if estimate_bands returns the correct number of bands for NaCl"""

        species = ["Na", "Cl"]
        coords = [[0, 0, 0], [0.5, 0.5, 0.5]]
        lattice = [[5, 0, 0], [0, 5, 0], [0, 0, 5]]
        structure = Structure(lattice, species, coords)

        self.assertEqual(check.estimate_nbands(structure), 14)

    def test_perovskite_nbands_count(self):
        """Tests if estimate_nbands returns the correct number of bands for a perovskite"""

        species = ["Ba", "Ti", "O"]
        structure = Structure.from_prototype("perovskite", species, a=4.3)

        nbands = check.estimate_nbands(structure)

        self.assertEqual(nbands, 72)


class TestCheckIncar(unittest.TestCase):
    def test_check_magnitudes(self):
        """Tests if the magnitudes of the INCAR file are checked correctly"""

        test_incar_dict = {
            "ISMEAR": 1,
            "SIGMA": 0.1,
            "LWAVE": False,
            "MAGMOM": [2, 2, 2],
            "ENCUT": 620,
        }

        incar_checker = check.CheckIncar(test_incar_dict)
        messages = incar_checker.check_magnitudes()
        self.assertEqual(messages, [])

    def test_check_magnitudes_fail(self):
        """Tests if the magnitudes of the INCAR file are checked correctly"""

        test_incar_dict = {
            "ISMEAR": 1,
            "SIGMA": 100,
            "LWAVE": False,
            "MAGMOM": [30, 2, 2],
            "ENCUT": 90,
        }

        incar_checker = check.CheckIncar(test_incar_dict)
        messages = incar_checker.check_magnitudes()
        self.assertEqual(len(messages), 3)

    def test_check_dependencies(self):
        """Tests if the dependencies of the INCAR file are checked correctly"""

        valid_incar_dependencies = {"ISPIN": 2, "MAGMOM": 2}

        incar_checker = check.CheckIncar(valid_incar_dependencies)
        messages = incar_checker.check_dependencies()
        self.assertEqual(messages, [])

    def test_check_dependencies_fail(self):
        invalid_incar_dependencies = {"ISPIN": 2}
        incar_checker = check.CheckIncar(invalid_incar_dependencies)
        messages = incar_checker.check_dependencies()

        self.assertEqual(len(messages), 1)


class TestCheckStructure(unittest.TestCase):
    def test_valid_structure(self):
        """Tests if the structure is checked correctly"""

        species = ["Na", "Cl"]
        coords = [[0, 0, 0], [0.5, 0.5, 0.5]]
        lattice = [[5, 0, 0], [0, 5, 0], [0, 0, 5]]
        structure = Structure(lattice, species, coords)

        structure_checker = check.CheckStructure(structure)
        messages = structure_checker.check_all()
        self.assertEqual(messages, [])

    def test_invalid_structure_atoms(self):
        """Tests if overlapping atoms are detected"""

        species = ["Na", "Na"]
        coords = [[0, 0, 0], [0.0, 0.0, 0.0]]
        lattice = [[5, 0, 0], [0, 5, 0], [0, 0, 5]]
        structure = Structure(lattice, species, coords)

        structure_checker = check.CheckStructure(structure)
        messages = structure_checker.check_all()
        self.assertEqual(len(messages), 1)

    def test_invalid_structure_volume(self):
        """Tests if small volumes are detected"""

        species = ["Na", "Cl"]
        coords = [[0, 0, 0], [0.5, 0.5, 0.5]]
        lattice = [[0.001, 0, 0], [0, 0.001, 0], [0, 0, 0.001]]
        structure = Structure(lattice, species, coords)

        structure_checker = check.CheckStructure(structure)
        messages = structure_checker.check_volume()
        self.assertEqual(len(messages), 1)


# class TestCheckFullInput(unittest.TestCase):

#     def test_valid_input(self):
#         """creates an Input object and validates it"""
            
#         InputObject = io.Input.from_file(os.path.join(files_dir, "valid.yaml"))
#         messages = InputObject.check()


if __name__ == "__main__":
    unittest.main()
