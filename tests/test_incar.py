import abvio.incar as In
import abvio.io as Io

import unittest
import os
from pathlib import Path

from pymatgen.core import Structure
from pymatgen.io.vasp import Incar


base_path = Path(__file__).parent
structure_dir = os.path.join(base_path, 'structures')
files_dir = os.path.join(base_path, 'files')
vaspset_dir = os.path.join(base_path, 'vaspset')

perovskite_structure = Structure.from_file(os.path.join(structure_dir, 'CaTiO3.vasp'))
fluorite_structure = Structure.from_file(os.path.join(structure_dir, 'CaF2.vasp'))

class TestMagmom(unittest.TestCase):

    def test_assign_magnetic_moments_by_species(self):
        structure = perovskite_structure.copy()
        structure = In.assign_site_property_by_species(structure, 'Ti', 'magmom', 2.0)
        structure = In.assign_site_property_by_species(structure, 'O', 'magmom', 0.0)
        structure = In.assign_site_property_by_species(structure, 'Ca', 'magmom', 0.0)

        for site in structure.sites:
            if site.species_string == 'Ti':
                self.assertEqual(site.properties['magmom'], 2.0)
            else:
                self.assertEqual(site.properties['magmom'], 0.0)

    def test_assign_magnetic_moments_by_species_fluorite(self):
        structure = fluorite_structure.copy()
        structure = In.assign_site_property_by_species(structure, 'F', 'magmom', 1.0)
        structure = In.assign_site_property_by_species(structure, 'Ca', 'magmom', 2.0)
        for site in structure.sites:
            if site.species_string == 'Ca':
                self.assertEqual(site.properties['magmom'], 2.0)
            else:
                self.assertEqual(site.properties['magmom'], 1.0)
        
    def test_assign_magnetic_moments_by_index(self):
        structure = perovskite_structure.copy()

        sites_for_zero = [0, 2 ]
        sites_for_two = [1, 3]
        sites_for_one = [ 4 ]

        for site in sites_for_zero:
            structure = In.assign_site_property_by_index(structure, site, 'magmom', 0.0)
        for site in sites_for_two:
            structure = In.assign_site_property_by_index(structure, site, 'magmom', 2.0)
        for site in sites_for_one:
            structure = In.assign_site_property_by_index(structure, site, 'magmom', 1.0)

        for i, site in enumerate(structure.sites):
            if i in sites_for_zero:
                self.assertEqual(site.properties['magmom'], 0.0)
            elif i in sites_for_two:
                self.assertEqual(site.properties['magmom'], 2.0)
            else:
                self.assertEqual(site.properties['magmom'], 1.0)

    def test_assign_magnetic_moments_by_range(self):

        #fluorite structure has 12 sites (0-11)
        structure = fluorite_structure.copy()

        #every other site has a magmom of 2.0 while the rest have 0.0
        structure = In.assign_site_property_by_range(structure, slice(0, 12, 2), 'magmom', 2.0)
        structure = In.assign_site_property_by_range(structure, slice(1, 12, 2), 'magmom', 1.0)

        #check if magmoms alternate between 2.0 and 0.0
        for i, site in enumerate(structure.sites):
            if i % 2 == 0:
                self.assertEqual(site.properties['magmom'], 2.0)
            else:
                self.assertEqual(site.properties['magmom'], 1.0)


    def test_magnetic_moments_from_structure(self):
        structure = perovskite_structure.copy()
        structure = In.assign_site_property_by_species(structure, 'Ti', 'magmom',2.0)
        structure = In.assign_site_property_by_species(structure, 'O', 'magmom', 0.0)
        structure = In.assign_site_property_by_species(structure, 'Ca', 'magmom', 0.0)

        magmoms = In.site_properties_from_structure(structure, 'magmom')

        self.assertEqual(magmoms, [0.0, 2.0, 0.0, 0.0, 0.0])


class TestNoncollinearMagMom(unittest.TestCase):


    def test_assign_magnetic_moments_by_species(self):
        structure = perovskite_structure.copy()
        structure = In.assign_site_property_by_species(structure, 'Ti', 'magmom', [0, 0, 2.0])
        structure = In.assign_site_property_by_species(structure, 'O', 'magmom', [0, 0, 0])
        structure = In.assign_site_property_by_species(structure, 'Ca', 'magmom', [0, 0, 0])

        for site in structure.sites:
            if site.species_string == 'Ti':
                self.assertEqual(site.properties['magmom'], [0, 0, 2.0])
            else:
                self.assertEqual(site.properties['magmom'], [0, 0, 0])

    def test_magnetic_moments_from_structure(self):
        structure = fluorite_structure.copy()
        structure = In.assign_site_property_by_species(structure, 'Ca', 'magmom', [2.0, 0, -1])

        magmoms = In.site_properties_from_structure(structure, 'magmom', default=[0, 0, 0])
        print(structure)
        self.assertEqual(magmoms, [[2.0, 0, -1]] * 4 + [[0, 0, 0]] * 8)


    def test_assign_magnetic_moments_by_range(self):

        #fluorite structure has 12 sites (0-11)
        structure = fluorite_structure.copy()

        #every other site has a magmom of 2.0 while the rest have 0.0
        structure = In.assign_site_property_by_range(structure, slice(0, 12, 2), 'magmom', [2.0] * 3)
        structure = In.assign_site_property_by_range(structure, slice(1, 12, 2), 'magmom', [0.0] * 3)

        #check if magmoms alternate between 2.0 and 0.0
        for i, site in enumerate(structure.sites):
            if i % 2 == 0:
                self.assertEqual(site.properties['magmom'], [2.0] * 3)
            else:
                self.assertEqual(site.properties['magmom'], [0.0] * 3)


class TestLDAUUFunctions(unittest.TestCase):

    def test_assign_ldauu_by_species(self):
        structure = perovskite_structure.copy()
        structure = In.assign_site_property_by_species(structure, 'Ti', 'ldauu', 2.0)
        structure = In.assign_site_property_by_species(structure, 'O', 'ldauu', 0.0)
        structure = In.assign_site_property_by_species(structure, 'Ca', 'ldauu', 0.0)

        for site in structure.sites:
            if site.species_string == 'Ti':
                self.assertEqual(site.properties['ldauu'], 2.0)
            else:
                self.assertEqual(site.properties['ldauu'], 0.0)

    def test_assign_ldauu_by_index(self):
        structure = perovskite_structure.copy()

        sites_for_zero = [0, 2 ]
        sites_for_two = [1, 3]
        sites_for_one = [ 4 ]

        for site in sites_for_zero:
            structure = In.assign_site_property_by_index(structure, site, 'ldauu', 0.0)
        for site in sites_for_two:
            structure = In.assign_site_property_by_index(structure, site, 'ldauu', 2.0)
        for site in sites_for_one:
            structure = In.assign_site_property_by_index(structure, site, 'ldauu', 1.0)

        for i, site in enumerate(structure.sites):
            if i in sites_for_zero:
                self.assertEqual(site.properties['ldauu'], 0.0)
            elif i in sites_for_two:
                self.assertEqual(site.properties['ldauu'], 2.0)
            else:
                self.assertEqual(site.properties['ldauu'], 1.0)

    def test_assign_ldauu_by_range(self):

        #fluorite structure has 12 sites (0-11)
        structure = fluorite_structure.copy()

        #every other site has a ldauu of 2.0 while the rest have 0.0
        structure = In.assign_site_property_by_range(structure, slice(0, 12, 2), 'ldauu', 2.0)
        structure = In.assign_site_property_by_range(structure, slice(1, 12, 2), 'ldauu', 0.0)

        #check if ldauu alternate between 2.0 and 0.0
        for i, site in enumerate(structure.sites):
            if i % 2 == 0:
                self.assertEqual(site.properties['ldauu'], 2.0)
            else:
                self.assertEqual(site.properties['ldauu'], 0.0)


    def test_ldauu_from_structure(self):
        structure = perovskite_structure.copy()
        structure = In.assign_site_property_by_species(structure, 'Ti', 'ldauu', 2.0)
        structure = In.assign_site_property_by_species(structure, 'O', 'ldauu', 0.0)
        structure = In.assign_site_property_by_species(structure, 'Ca', 'ldauu', 0.0)

        ldauu = In.site_properties_from_structure(structure, 'ldauu')

        self.assertEqual(ldauu, [0.0, 2.0, 0.0, 0.0, 0.0])


class TestReadSiteProperties(unittest.TestCase):

    species_yaml_file = os.path.join(files_dir, 'magmom_species.yaml')
    index_yaml_file = os.path.join(files_dir, 'magmom_index.yaml')
    range_yaml_file = os.path.join(files_dir, 'magmom_range.yaml')

    species_test_dict = Io.load(species_yaml_file)['incar']
    index_test_dict = Io.load(index_yaml_file)['incar']
    range_test_dict = Io.load(range_yaml_file)['incar']

    noncollinear_species_yaml_file = os.path.join(files_dir, 'magmom_noncollinear_species.yaml')
    noncollinear_index_yaml_file = os.path.join(files_dir, 'magmom_noncollinear_index.yaml')
    noncollinear_range_yaml_file = os.path.join(files_dir, 'magmom_noncollinear_range.yaml')

    noncollinear_species_test_dict = Io.load(noncollinear_species_yaml_file)['incar']
    noncollinear_index_test_dict = Io.load(noncollinear_index_yaml_file)['incar']
    noncollinear_range_test_dict = Io.load(noncollinear_range_yaml_file)['incar']

    def test_read_magmom_by_species(self):
        magmom_dict = self.species_test_dict.get('magmom')
        self.assertIsInstance(magmom_dict, dict)

        for key, value in magmom_dict.items():
            self.assertIsInstance(key, str)
            self.assertIsInstance(value, (int, float))

    def test_read_magmom_by_index(self):

        magmom_dict = self.index_test_dict.get('magmom')
        self.assertIsInstance(magmom_dict, dict)

        for key, value in magmom_dict.items():
            self.assertIsInstance(key, int)
            self.assertIsInstance(value, (int, float))

    def test_read_magmom_by_range(self):
        magmom_dict_list = self.range_test_dict.get('magmom')

        self.assertIsInstance(magmom_dict_list, list)
        for magmom_dict in magmom_dict_list:
            self.assertIsInstance(magmom_dict, dict)

            for key, value in magmom_dict.items():
                self.assertIsInstance(key, str)
                self.assertIsInstance(value, (int, float))

    def test_read_noncollinear_magmom_by_species(self):
        magmom_dict = self.noncollinear_species_test_dict.get('magmom')
        self.assertIsInstance(magmom_dict, dict)

        for key, value in magmom_dict.items():
            self.assertIsInstance(key, str)
            self.assertIsInstance(value, list)

    def test_read_noncollinear_magmom_by_index(self):
            
            magmom_dict = self.noncollinear_index_test_dict.get('magmom')
            self.assertIsInstance(magmom_dict, dict)
    
            for key, value in magmom_dict.items():
                self.assertIsInstance(key, int)
                self.assertIsInstance(value, list)

    def test_read_noncollinear_magmom_by_range(self):

        magmom_dict_list = self.noncollinear_range_test_dict.get('magmom')

        self.assertIsInstance(magmom_dict_list, list)
        for magmom_dict in magmom_dict_list:
            self.assertIsInstance(magmom_dict, dict)

            for key, value in magmom_dict.items():
                self.assertIsInstance(key, str)
                self.assertIsInstance(value, (int,list))

    def test_is_index_dict(self):

        index_dicts = [self.index_test_dict, self.noncollinear_index_test_dict]
        non_index_dicts = [self.species_test_dict, self.range_test_dict, self.noncollinear_species_test_dict, self.noncollinear_range_test_dict]

        for index_dict in index_dicts:
            magmom_dict = index_dict.get('magmom')
            self.assertTrue(In.is_index_dict(magmom_dict))

        for non_index_dict in non_index_dicts:
            magmom_dict = non_index_dict.get('magmom')
            self.assertFalse(In.is_index_dict(magmom_dict))

    def test_is_species_dict(self):
            
        species_dicts = [self.species_test_dict, self.noncollinear_species_test_dict]
        non_species_dicts = [self.index_test_dict, self.range_test_dict, self.noncollinear_index_test_dict, self.noncollinear_range_test_dict]
    
        for species_dict in species_dicts:
            magmom_dict = species_dict.get('magmom')
            self.assertTrue(In.is_species_dict(magmom_dict))
    
        for non_species_dict in non_species_dicts:
            magmom_dict = non_species_dict.get('magmom')
            self.assertFalse(In.is_species_dict(magmom_dict))

    def test_is_range_list(self):
            
        range_dicts = [self.range_test_dict, self.noncollinear_range_test_dict]
        non_range_dicts = [self.species_test_dict, self.index_test_dict, self.noncollinear_species_test_dict, self.noncollinear_index_test_dict]
    
        for range_dict in range_dicts:
            magmom_dict_list = range_dict.get('magmom')
            self.assertTrue(In.is_range_list(magmom_dict_list))
    
        for non_range_dict in non_range_dicts:
            magmom_dict_list = non_range_dict.get('magmom')
            self.assertFalse(In.is_range_list(magmom_dict_list))


    def test_is_collinear(self):

        collinear_list = [self.species_test_dict, self.index_test_dict, self.range_test_dict]
        noncollinear_list = [self.noncollinear_species_test_dict, self.noncollinear_index_test_dict, self.noncollinear_range_test_dict]

        for collinear_dict in collinear_list:
            magmom_dict = collinear_dict.get('magmom')
            self.assertTrue(In.is_collinear(magmom_dict))

        for noncollinear_dict in noncollinear_list:
            magmom_dict = noncollinear_dict.get('magmom')
            self.assertFalse(In.is_collinear(magmom_dict))


class TestIncarModel(unittest.TestCase):


    def test_valid_model(self):

        structure = perovskite_structure.copy()
        incar_dict = {
            'incar': {
                'magmom': {
                    'Ti': 2.0,
                    'O': 0.0,
                    'Ca': 0.0
                },
                'ediff': 1e-4,
                'ismear': -5,
                'lreal': False,
                'ediffg': -0.01,
                'lwave': False,
            }
        }

        model = In.IncarModel(incar_dict=incar_dict['incar'])
        self.assertIsInstance(model, In.IncarModel)
        incar = model.incar(structure)
        self.assertIsInstance(incar, Incar)

        incar.check_params()

    def test_valid_noncollinear_model(self):
        structure = perovskite_structure.copy()

        incar_dict = {
            'incar': {
                'magmom': {
                    'Ti': [0, 0, 2.0],
                    'O': [0, 0, 0],
                    'Ca': [0, 0, 0]
                },
                'ediff': 1e-4,
                'ismear': -5,
                'lreal': False,
                'ediffg': -0.01,
                'lwave': False,
            }
        }

        model = In.IncarModel(incar_dict=incar_dict['incar'])
        self.assertIsInstance(model, In.IncarModel)
        incar = model.incar(structure)
        self.assertIsInstance(incar, Incar)

        incar.check_params()
        
        self.assertEqual(incar['MAGMOM'], [[0, 0, 0], [0, 0, 2.0], [0, 0, 0], [0, 0, 0], [0, 0, 0]])

    def test_invalid_magmom_incar_model(self):
        incar_dict = {
            'incar': {
                'magmom': [
                    {'Ti': 2.0},
                    {'O': 0.0},
                    {'Ca': 0.0}
                ],
                'ediff': 1e-4,
                'ismear': -5,
                'lreal': False,
                'ediffg': -0.01,
                'lwave': False,
            }
        }

        with self.assertRaises(ValueError):
            model = In.IncarModel(incar_dict=incar_dict['incar'])        
            model.incar(fluorite_structure)

    def test_valid_model_magmom_range(self):

        structure = fluorite_structure.copy()
        incar_dict = {
            'incar': {
                'magmom': [
                    {'start': 0, 'stop': 12, 'step': 2, 'value': 50.0},
                    {'start': 1, 'stop': 12, 'step': 2, 'value': 7.0}
                ],
                'ediff': 1e-4,
                'ismear': -5,
                'lreal': False,
                'ediffg': -0.01,
                'lwave': False,
            }
        }

        model = In.IncarModel(incar_dict=incar_dict['incar'])
        incar = model.incar(structure)
        incar.check_params()

        self.assertIsInstance(model, In.IncarModel)
        self.assertIsInstance(incar, Incar)

        #check if magmoms alternate between 50.0 and 7.0
        generated_magmom_list = incar['MAGMOM']
        for i, magmom in enumerate(generated_magmom_list):
            if i % 2 == 0:
                self.assertEqual(magmom, 50.0)
            else:
                self.assertEqual(magmom, 7.0)
        



if __name__ == '__main__':
    unittest.main()