import abvio.kpoints as kp 

import unittest
import os
from pathlib import Path

from pymatgen.io.vasp import Kpoints
from pymatgen.core import Structure
from pydantic import ValidationError


base_path = Path(__file__).parent
structure_dir = os.path.join(base_path, 'structures')
files_dir = os.path.join(base_path, 'files')
vaspset_dir = os.path.join(base_path, 'vaspsets')

class TestKpointsBaseModel(unittest.TestCase):

    def test_base_kpoints_valid(self):
        kpoints = kp.BaseKpoints(mode="surface", spacing=1)
        self.assertTrue(kpoints.requires_structure)

        kpoints = kp.BaseKpoints(mode="autoline", spacing=1)
        self.assertTrue(kpoints.requires_structure)

    
    def test_variable_mesh_enums(self): 

        gamma_test_cases = ['gamma', 'Gamma', 'GAMMA', 'g', 'G']
        monkhorst_test_cases = ['monkhorst', 'Monkhorst', 'MONKHORST', 'm', 'M']

        for case in gamma_test_cases:
            kpoints = kp.BaseKpoints(mode=case, spacing=1)
            self.assertEqual(kpoints.mode, 'gamma')

        for case in monkhorst_test_cases:
            kpoints = kp.BaseKpoints(mode=case, spacing=1)
            self.assertEqual(kpoints.mode, 'monkhorst')


    def test_base_kpoints_invalid(self):
        with self.assertRaises(ValueError):
            kp.BaseKpoints(mode=9, spacing=1, shift=(0, 0, 0))

        with self.assertRaises(ValueError):
            kp.BaseKpoints(mode="wrong", spacing=1, shift=(0, 0, 0))


class TestLineModeKpoints(unittest.TestCase):
    """Tests if we can create a LineModeKpoints object correctly"""

    def test_valid_linemode(self):
        model = kp.LineKpoints(spacing=30, paths=[[0, 0, 0], [0.5, 0.5, 0.5]], labels=["G", "X"])
        self.assertFalse(model.requires_structure)
        
        kpoints = model.kpoints()
        self.assertIsInstance(kpoints, Kpoints)

    def test_invalid_linemode(self):
        
        with self.assertRaises(ValueError):
            model = kp.LineKpoints(spacing=30, paths=[[0, 0], [0.5, 0.5]], labels=["G", "X"])

        with self.assertRaises(ValueError):
            model = kp.LineKpoints(spacing=30, paths=[[0, 0, 0 ], [0.5, 0.5, 0.5]], labels=["G"])

        with self.assertRaises(ValueError):
            model = kp.LineKpoints(spacing=30, paths=[[0, 0, 0], [0.5, 0.5, 0.5]], labels=["G", "X", "Y"])
            model.kpoints()

        with self.assertRaises(ValueError):
            model = kp.LineKpoints(spacing=0.1, paths=[[0, 0, 0], [0.5, 0.5, 0.5]], labels=["G", "X"])
            model.kpoints()

class TestAutoLineKpoints(unittest.TestCase):
    """Tests if we can create an AutoLineKpoints object correctly"""

    def test_fluorite_autoline(self):
        kpoints_divisions = 10
        model = kp.AutoLineKpoints(spacing=kpoints_divisions)
        self.assertTrue(model.requires_structure)

        structure = Structure.from_file(os.path.join(structure_dir, 'CaF2.vasp'))
        kpoints = model.kpoints(structure)
        self.assertIsInstance(kpoints, Kpoints)
        self.assertEqual(kpoints.num_kpts, kpoints_divisions)

    def test_perovskite_auto_line(self):
        kpoints_divisions = 35
        model = kp.AutoLineKpoints(spacing=kpoints_divisions)
        structure = Structure.from_file(os.path.join(structure_dir, 'CaTiO3.vasp'))
        kpoints = model.kpoints(structure)
        self.assertIsInstance(kpoints, Kpoints)
        self.assertEqual(kpoints.num_kpts, kpoints_divisions)

    def test_invalid_autoline(self):
        with self.assertRaises(ValueError):
            model = kp.AutoLineKpoints(spacing=0.1)
            model.kpoints(None)


class TestSurfaceKpoints(unittest.TestCase):

    def test_valid_surface(self):
        model = kp.SurfaceKpoints(spacing=80000)
        structure = Structure.from_file(os.path.join(structure_dir, 'CaF2.vasp'))
        kpoints = model.kpoints(structure)
    
        self.assertTrue(model.requires_structure)
        self.assertIsInstance(kpoints, Kpoints)

class TestGammaKpoints(unittest.TestCase):

    def test_valid_gamma(self):
        model = kp.GammaKpoints(spacing=[3, 3, 3])
        self.assertFalse(model.requires_structure)
        kpoints = model.kpoints()
        self.assertIsInstance(kpoints, Kpoints)

    def test_compare_from_file(self):
        model = kp.GammaKpoints(spacing=[7, 7, 7])
        kpoints = [list(kpt) for kpt in  model.kpoints().kpts ]
        kpoints_from_file = Kpoints.from_file(os.path.join(vaspset_dir, 'fluorite', 'KPOINTS'))
        expected_kpoints = [list(kpt) for kpt in kpoints_from_file.kpts]
        self.assertEqual(kpoints, expected_kpoints)
    
    def test_write_kpoints(self):
        model = kp.GammaKpoints(spacing=[7, 7, 7])
        kpoints = model.kpoints()
        kpoints.write_file(os.path.join('/tmp', 'test.kpoints'))


class TestMonkhorstKpoints(unittest.TestCase):

    def test_valid_monkhorst(self):
        input_spacing = [2, 2, 1]
        model = kp.MonkhorstKpoints(spacing=input_spacing)
        kpoints = model.kpoints()
        self.assertIsInstance(kpoints, Kpoints)

        for kpoint,expected_value in zip(kpoints.kpts[0], input_spacing):
            self.assertEqual(kpoint, expected_value)
                    

class TestAutoLinemodeFromInputDictionary(unittest.TestCase):

    def test_automatic_linemode_kpoints(self):
        """This test mimics the following yaml input

        kpoints:
            mode: autoline
            spacing: 20

        """
        manual_model = kp.AutoLineKpoints(spacing=20)

        test_dict = {
            'kpoints': {'mode': 'autoline', 'spacing': 20}
        }
        test_model = kp.AutoLineKpoints.validate(test_dict['kpoints'])

        self.assertEqual(test_model, manual_model)

    def test_automatic_linemode_kpoint_gen(self):
        """Test creating Kpoints object from the input dictionary"""

        test_dict = {
            'kpoints': {'mode': 'autoline', 'spacing': 20}
        }
        test_model = kp.AutoLineKpoints.validate(test_dict['kpoints'])

        structure = Structure.from_file(os.path.join(structure_dir, 'CaF2.vasp'))
        kpoints = test_model.kpoints(structure)

        self.assertIsInstance(kpoints, Kpoints)

    def test_invalid_autoline_kpoints(self):
        test_dict = {
            'kpoints': {'mode': 'autoline', 'spacing': 0.1}
        }

        with self.assertRaises(ValidationError):
            kp.AutoLineKpoints.validate(test_dict['kpoints'])

    def test_surface_kpoints(self):
        test_dict = {
            'kpoints': {'mode': 'surface', 'spacing': 80000}
        }
        test_model = kp.SurfaceKpoints.validate(test_dict['kpoints'])
        structure = Structure.from_file(os.path.join(structure_dir, 'CaF2.vasp'))
        kpoints = test_model.kpoints(structure)

        self.assertIsInstance(test_model, kp.SurfaceKpoints)
        self.assertIsInstance(kpoints, Kpoints)

    
class TestLinemodeFromInputDictionary(unittest.TestCase):
    
    def test_linemode_kpoints(self):
        """This test mimics the following yaml input
    
        kpoints:
            mode: line
            spacing: 30
            paths: [[0, 0, 0], [0.5, 0.5, 0.5]]
            labels: ["G", "X"]
    
        """
        manual_model = kp.LineKpoints(spacing=30, paths=[[0, 0, 0], [0.5, 0.5, 0.5]], labels=["G", "X"])
    
        test_dict = {
            'kpoints': {'mode': 'line', 'spacing': 30, 'paths': [[0, 0, 0], [0.5, 0.5, 0.5]], 'labels': ["G", "X"]}
        }
        test_model = kp.LineKpoints.validate(test_dict['kpoints'])
    
        self.assertEqual(test_model, manual_model)
    
    def test_linemode_kpoint_gen(self):
        """Test creating Kpoints object from the input dictionary"""
    
        test_dict = {
            'kpoints': {'mode': 'line', 'spacing': 30, 'paths': [[0, 0, 0], [0.5, 0.5, 0.5]], 'labels': ["G", "X"]}
        }
        test_model = kp.LineKpoints.validate(test_dict['kpoints'])
        kpoints = test_model.kpoints()
    
        self.assertIsInstance(kpoints, Kpoints)
    
    def test_invalid_linemode_kpoints(self):
        test_dict = {
            'kpoints': {'mode': 'line', 'spacing': 30, 'paths': [[0, 0], [0.5, 0.5]], 'labels': ["G", "X"]}
        }
    
        with self.assertRaises(ValidationError):
            kp.LineKpoints.validate(test_dict['kpoints'])
    
    def test_invalid_linemode_kpoints_labels(self):
        test_dict = {
            'kpoints': {'mode': 'line', 'spacing': 30, 'paths': [[0, 0, 0], [0.5, 0.5, 0.5]], 'labels': ["G"]}
        }
    
        with self.assertRaises(ValidationError):
            kp.LineKpoints.validate(test_dict['kpoints'])
    

class TestKpointsModeDetection(unittest.TestCase):

    valid_test_dicts = [
        {
            'kpoints': {'mode': 'line', 'spacing': 30, 'paths': [[0, 0, 0], [0.5, 0.5, 0.5]], 'labels': ["G", "X"]}
        },
        {
            'kpoints': {'mode': 'autoline', 'spacing': 20}
        },
        {
            'kpoints': {'mode': 'surface', 'spacing': 80000}
        },
        {
            'kpoints': {'mode': 'gamma', 'spacing': [3, 3, 3]}
        },
        {
            'kpoints': {'mode': 'Monkhorst', 'spacing': [2, 2, 1]}
        },
        {
            'kpoints': {'mode': 'monkhorst-pack', 'spacing': [4, 2, 7]}
        }
    ]

    def test_valid_kpoints_mode_detection(self):
        test_structure = Structure.from_file(os.path.join(structure_dir, 'CaF2.vasp'))
        for test_dict in self.valid_test_dicts:
            kpoints = kp.kpoints_from_dictionary(test_dict['kpoints'], structure=test_structure)
            self.assertIsInstance(kpoints, Kpoints)
            



if __name__ == "__main__":
    unittest.main()