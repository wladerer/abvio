import pytest
import abvio.check as check

from pymatgen.core.structure import Structure


class TestNumericalFunctions:
    @pytest.mark.parametrize("value,expected", [
        (0.063, -2), (0.1, -1), (0.99999, -1), (1, 0),
        (19, 1), (143, 2), (1097, 3), (30000, 4), (100000, 5), (1000000, 6),
    ])
    def test_magnitude(self, value, expected):
        assert check.magnitude(value) == expected

    def test_nacl_nbands(self):
        s = Structure([[5,0,0],[0,5,0],[0,0,5]], ["Na","Cl"], [[0,0,0],[0.5,0.5,0.5]])
        assert check.estimate_nbands(s) == 14

    def test_perovskite_nbands(self):
        s = Structure.from_prototype("perovskite", ["Ba","Ti","O"], a=4.3)
        assert check.estimate_nbands(s) == 72


class TestCheckIncar:
    def test_valid_magnitudes(self):
        incar = {"ISMEAR": 1, "SIGMA": 0.1, "LWAVE": False, "MAGMOM": [2,2,2], "ENCUT": 620}
        assert check.CheckIncar(incar).check_magnitudes() == []

    def test_invalid_magnitudes(self):
        incar = {"ISMEAR": 1, "SIGMA": 100, "LWAVE": False, "MAGMOM": [30,2,2], "ENCUT": 90}
        assert len(check.CheckIncar(incar).check_magnitudes()) == 3

    def test_valid_dependencies(self):
        assert check.CheckIncar({"ISPIN": 2, "MAGMOM": 2}).check_dependencies() == []

    def test_missing_dependency(self):
        assert len(check.CheckIncar({"ISPIN": 2}).check_dependencies()) == 1


class TestCheckStructure:
    def test_valid_structure(self):
        s = Structure([[5,0,0],[0,5,0],[0,0,5]], ["Na","Cl"], [[0,0,0],[0.5,0.5,0.5]])
        assert check.CheckStructure(s).check_all() == []

    def test_overlapping_atoms(self):
        s = Structure([[5,0,0],[0,5,0],[0,0,5]], ["Na","Na"], [[0,0,0],[0,0,0]])
        assert len(check.CheckStructure(s).check_all()) == 1

    def test_tiny_volume(self):
        s = Structure([[0.001,0,0],[0,0.001,0],[0,0,0.001]], ["Na","Cl"],
                      [[0,0,0],[0.5,0.5,0.5]])
        assert len(check.CheckStructure(s).check_volume()) == 1
