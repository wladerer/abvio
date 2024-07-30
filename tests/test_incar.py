import abvio.incar as In

import unittest
import os
from pathlib import Path

from pymatgen.core import Structure


base_path = Path(__file__).parent
structure_dir = os.path.join(base_path, 'structures')
files_dir = os.path.join(base_path, 'files')
vaspset_dir = os.path.join(base_path, 'vaspset')

perovskite_structure = Structure.from_file(os.path.join(structure_dir, 'CaTiO3.vasp'))
fluorite_structure = Structure.from_file(os.path.join(structure_dir, 'CaF2.vasp'))

class TestMagmom(unittest.TestCase):

    def test_assign_magnetic_moments_by_species(self):
        structure = perovskite_structure.copy()
        structure = In.assign_magnetic_moments_by_species(structure, 'Ti', 2.0)
        structure = In.assign_magnetic_moments_by_species(structure, 'O', 0.0)
        structure = In.assign_magnetic_moments_by_species(structure, 'Ca', 0.0)

        for site in structure.sites:
            if site.species_string == 'Ti':
                self.assertEqual(site.properties['magmom'], 2.0)
            else:
                self.assertEqual(site.properties['magmom'], 0.0)

    def test_assign_magnetic_moments_by_species_fluorite(self):
        structure = fluorite_structure.copy()
        structure = In.assign_magnetic_moments_by_species(structure, 'F', 0.0)
        structure = In.assign_magnetic_moments_by_species(structure, 'Ca', 2.0)

        for site in structure.sites:
            if site.species_string == 'Ca':
                self.assertEqual(site.properties['magmom'], 2.0)
            else:
                self.assertEqual(site.properties['magmom'], 0.0)
        
    def test_assign_magnetic_moments_by_index(self):
        structure = perovskite_structure.copy()

        sites_for_zero = [0, 2 ]
        sites_for_two = [1, 3]
        sites_for_one = [ 4 ]

        for site in sites_for_zero:
            structure = In.assign_magnetic_moments_by_index(structure, site, 0.0)
        for site in sites_for_two:
            structure = In.assign_magnetic_moments_by_index(structure, site, 2.0)
        for site in sites_for_one:
            structure = In.assign_magnetic_moments_by_index(structure, site, 1.0)

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
        structure = In.assign_magnetic_moments_by_range(structure, slice(0, 12, 2), 2.0)
        structure = In.assign_magnetic_moments_by_range(structure, slice(1, 12, 2), 0.0)

        #check if magmoms alternate between 2.0 and 0.0
        for i, site in enumerate(structure.sites):
            if i % 2 == 0:
                self.assertEqual(site.properties['magmom'], 2.0)
            else:
                self.assertEqual(site.properties['magmom'], 0.0)

    def test_magnetic_moments_from_structure(self):
        structure = perovskite_structure.copy()
        structure = In.assign_magnetic_moments_by_species(structure, 'Ti', 2.0)
        structure = In.assign_magnetic_moments_by_species(structure, 'O', 0.0)
        structure = In.assign_magnetic_moments_by_species(structure, 'Ca', 0.0)

        magmoms = In.magnetic_moments_from_structure(structure)

        self.assertEqual(magmoms, [0.0, 2.0, 0.0, 0.0, 0.0])


class TestNoncollinearMagMom(unittest.TestCase):


    def test_assign_magnetic_moments_by_species(self):
        structure = perovskite_structure.copy()
        structure = In.assign_magnetic_moments_by_species(structure, 'Ti', [0, 0, 2.0])
        structure = In.assign_magnetic_moments_by_species(structure, 'O', [0, 0, 0])
        structure = In.assign_magnetic_moments_by_species(structure, 'Ca', [0, 0, 0])

        for site in structure.sites:
            if site.species_string == 'Ti':
                self.assertEqual(site.properties['magmom'], [0, 0, 2.0])
            else:
                self.assertEqual(site.properties['magmom'], [0, 0, 0])

    def test_magnetic_moments_from_structure(self):
        structure = fluorite_structure.copy()
        structure = In.assign_magnetic_moments_by_species(structure, 'Ca', [2.0, 0, -1])

        magmoms = In.magnetic_moments_from_structure(structure, default=[0, 0, 0])

        self.assertEqual(magmoms, [[2.0, 0, -1]] * 4 + [[0, 0, 0]] * 8)


    
    def test_assign_magnetic_moments_by_range(self):

        #fluorite structure has 12 sites (0-11)
        structure = fluorite_structure.copy()

        #every other site has a magmom of 2.0 while the rest have 0.0
        structure = In.assign_magnetic_moments_by_range(structure, slice(0, 12, 2), [2.0] * 3)
        structure = In.assign_magnetic_moments_by_range(structure, slice(1, 12, 2), [0.0] * 3)

        #check if magmoms alternate between 2.0 and 0.0
        for i, site in enumerate(structure.sites):
            if i % 2 == 0:
                self.assertEqual(site.properties['magmom'], [2.0] * 3)
            else:
                self.assertEqual(site.properties['magmom'], [0.0] * 3)


class TestLDAUUFunctions(unittest.TestCase):

    def test_assign_ldauu_by_species(self):
        structure = perovskite_structure.copy()
        structure = In.assign_ldauu_by_species(structure, 'Ti', 2.0)
        structure = In.assign_ldauu_by_species(structure, 'O', 0.0)
        structure = In.assign_ldauu_by_species(structure, 'Ca', 0.0)

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
            structure = In.assign_ldauu_by_index(structure, site, 0.0)
        for site in sites_for_two:
            structure = In.assign_ldauu_by_index(structure, site, 2.0)
        for site in sites_for_one:
            structure = In.assign_ldauu_by_index(structure, site, 1.0)

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
        structure = In.assign_ldauu_by_range(structure, slice(0, 12, 2), 2.0)
        structure = In.assign_ldauu_by_range(structure, slice(1, 12, 2), 0.0)

        #check if ldauu alternate between 2.0 and 0.0
        for i, site in enumerate(structure.sites):
            if i % 2 == 0:
                self.assertEqual(site.properties['ldauu'], 2.0)
            else:
                self.assertEqual(site.properties['ldauu'], 0.0)


    def test_ldauu_from_structure(self):
        structure = perovskite_structure.copy()
        structure = In.assign_ldauu_by_species(structure, 'Ti', 2.0)
        structure = In.assign_ldauu_by_species(structure, 'O', 0.0)
        structure = In.assign_ldauu_by_species(structure, 'Ca', 0.0)

        ldauu = In.ldauu_values_from_structure(structure)

        self.assertEqual(ldauu, [0.0, 2.0, 0.0, 0.0, 0.0])

if __name__ == '__main__':
    unittest.main()