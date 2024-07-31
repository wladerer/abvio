import unittest
import yaml
import os
import abvio.io as io
import numpy as np

from pathlib import Path
from pymatgen.core import Structure
from pymatgen.io.vasp import Incar, Kpoints, Poscar

from pymatgen.symmetry.analyzer import SpacegroupAnalyzer


base_path = Path(__file__).parent
structure_dir = os.path.join(base_path, 'structures')
files_dir = os.path.join(base_path, 'files')
vaspset_dir = os.path.join(base_path, 'vaspsets')



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
    

class TestCreateInput(unittest.TestCase):
    """Tests if the input class can create a valid VASP input set"""

    def test_Input_from_file(self):
        """Tests if the input class can create a valid VASP input set"""

        InputObject = io.Input.from_file(os.path.join(files_dir, 'valid.yaml'))
        self.assertIsInstance(InputObject, io.Input)

    def test_kpoints_method(self):
        """Tests if the kpoints method returns a Kpoints object"""

        InputObject = io.Input.from_file(os.path.join(files_dir, 'valid.yaml'))
        kpoints = InputObject.kpoints
        self.assertIsInstance(kpoints, Kpoints)

        for kpt in kpoints.kpts:
            self.assertEqual(kpt, (5, 5, 5))

    def test_incar_method(self):
        """Tests if the incar method returns an Incar object
        
        Incar section looks like the following 
        incar:
            ediff: 1e-6
            ediffg: -0.01
            isif: 3
            nsw: 4
            ibrion: 2
            magmom:
                Ca: 2.0
                F: 0.6
        """

        InputObject = io.Input.from_file(os.path.join(files_dir, 'valid.yaml'))
        incar = InputObject.incar
        self.assertIsInstance(incar, Incar)

        self.assertEqual(float(incar['EDIFF']), 1e-6)
        self.assertEqual(incar['EDIFFG'], -0.01)
        self.assertEqual(incar['ISIF'], 3)
        self.assertEqual(incar['NSW'], 4)
        self.assertEqual(incar['IBRION'], 2)
        self.assertEqual(incar['MAGMOM'], [2] * 4 + [0.6] * 8)

    
    def test_structure_method(self):
        """Tests if the structure method returns a Structure object"""

        InputObject = io.Input.from_file(os.path.join(files_dir, 'valid.yaml'))
        structure = InputObject.structure
        self.assertIsInstance(structure, Structure)

    def test_write_method(self):
        """Tests if the write method writes the input files to the directory"""

        InputObject = io.Input.from_file(os.path.join(files_dir, 'valid.yaml'))
        InputObject.write_inputs('/tmp')

        self.assertTrue(os.path.exists('/tmp/POSCAR'))
        self.assertTrue(os.path.exists('/tmp/INCAR'))
        self.assertTrue(os.path.exists('/tmp/KPOINTS'))

        #check if all files are valid
        Poscar.from_file('/tmp/POSCAR')
        Incar.from_file('/tmp/INCAR')
        Kpoints.from_file('/tmp/KPOINTS')

        os.remove('/tmp/POSCAR')
        os.remove('/tmp/INCAR')
        os.remove('/tmp/KPOINTS')


class TestSiBandStructure(unittest.TestCase):
    """Tests if the Si band structure is generated correctly"""

    def test_incar(self):
        """Tests if the INCAR file is generated correctly"""

        si_band_dir = os.path.join(vaspset_dir, 'band')
        input_file = os.path.join(si_band_dir, 'equivalent.yaml')
        InputObject = io.Input.from_file(input_file)
        
        expected_incar = Incar.from_file(os.path.join(si_band_dir, 'INCAR'))

        self.assertEqual(InputObject.incar, expected_incar)

    def test_kpoints(self):
        """Tests if the KPOINTS file is generated correctly"""

        si_band_dir = os.path.join(vaspset_dir, 'band')
        input_file = os.path.join(si_band_dir, 'equivalent.yaml')
        InputObject = io.Input.from_file(input_file)
        
        expected_kpoints = Kpoints.from_file(os.path.join(si_band_dir, 'KPOINTS'))

        self.assertEqual(set(InputObject.kpoints.kpts), set(expected_kpoints.kpts))

    def test_structure(self):
        """Tests if the structure is generated correctly"""

        si_band_dir = os.path.join(vaspset_dir, 'band')
        input_file = os.path.join(si_band_dir, 'equivalent.yaml')
        InputObject = io.Input.from_file(input_file)
        
        expected_structure = Poscar.from_file(os.path.join(si_band_dir, 'POSCAR')).structure

        self.assertEqual(InputObject.structure.reduced_formula, expected_structure.reduced_formula)

    
class TestPerovskiteSet(unittest.TestCase):
    """Tests if the Perovskite set is generated correctly"""

    def test_incar(self):
        """Tests if the INCAR file is generated correctly"""

        perovskite_dir = os.path.join(vaspset_dir, 'perovskite')
        input_file = os.path.join(perovskite_dir, 'equivalent.yaml')
        InputObject = io.Input.from_file(input_file)
        
        expected_incar = Incar.from_file(os.path.join(perovskite_dir, 'INCAR'))

        #check only magmom, lwave, and encut
        self.assertEqual(InputObject.incar['MAGMOM'], expected_incar['MAGMOM'])
        self.assertEqual(InputObject.incar['LWAVE'], expected_incar['LWAVE'])
        self.assertEqual(InputObject.incar['ENCUT'], expected_incar['ENCUT'])

    def test_kpoints(self):
        """Tests if the KPOINTS file is generated correctly"""

        perovskite_dir = os.path.join(vaspset_dir, 'perovskite')
        input_file = os.path.join(perovskite_dir, 'equivalent.yaml')
        InputObject = io.Input.from_file(input_file)
        
        expected_kpoints = Kpoints.from_file(os.path.join(perovskite_dir, 'KPOINTS'))

        self.assertEqual(set(InputObject.kpoints.kpts), set(expected_kpoints.kpts))

    def test_structure(self):
        """Tests if the structure is generated correctly"""

        perovskite_dir = os.path.join(vaspset_dir, 'perovskite')
        input_file = os.path.join(perovskite_dir, 'equivalent.yaml')
        InputObject = io.Input.from_file(input_file)
        
        expected_structure = Poscar.from_file(os.path.join(perovskite_dir, 'POSCAR')).structure

        self.assertEqual(InputObject.structure.reduced_formula, expected_structure.reduced_formula)
        



if __name__ == '__main__':
    unittest.main()