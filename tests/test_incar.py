import pytest
import abvio.incar as In
import abvio.aio as Io

from pathlib import Path
from pymatgen.io.vasp import Incar

FILES_DIR = Path(__file__).parent / "files"


class TestMagmom:
    def test_assign_by_species_perovskite(self, perovskite):
        s = perovskite.copy()
        s = In.assign_site_property_by_species(s, "Ti", "magmom", 2.0)
        s = In.assign_site_property_by_species(s, "O",  "magmom", 0.0)
        s = In.assign_site_property_by_species(s, "Ca", "magmom", 0.0)
        for site in s.sites:
            expected = 2.0 if site.species_string == "Ti" else 0.0
            assert site.properties["magmom"] == expected

    def test_assign_by_species_fluorite(self, fluorite):
        s = fluorite.copy()
        s = In.assign_site_property_by_species(s, "F",  "magmom", 1.0)
        s = In.assign_site_property_by_species(s, "Ca", "magmom", 2.0)
        for site in s.sites:
            expected = 2.0 if site.species_string == "Ca" else 1.0
            assert site.properties["magmom"] == expected

    def test_assign_by_index(self, perovskite):
        s = perovskite.copy()
        zeros = [0, 2]
        twos  = [1, 3]
        ones  = [4]
        for i in zeros: s = In.assign_site_property_by_index(s, i, "magmom", 0.0)
        for i in twos:  s = In.assign_site_property_by_index(s, i, "magmom", 2.0)
        for i in ones:  s = In.assign_site_property_by_index(s, i, "magmom", 1.0)
        for i, site in enumerate(s.sites):
            if i in zeros: assert site.properties["magmom"] == 0.0
            elif i in twos: assert site.properties["magmom"] == 2.0
            else: assert site.properties["magmom"] == 1.0

    def test_assign_by_range(self, fluorite):
        s = fluorite.copy()
        s = In.assign_site_property_by_range(s, slice(0, 12, 2), "magmom", 2.0)
        s = In.assign_site_property_by_range(s, slice(1, 12, 2), "magmom", 1.0)
        for i, site in enumerate(s.sites):
            assert site.properties["magmom"] == (2.0 if i % 2 == 0 else 1.0)

    def test_site_properties_from_structure(self, perovskite):
        s = perovskite.copy()
        s = In.assign_site_property_by_species(s, "Ti", "magmom", 2.0)
        s = In.assign_site_property_by_species(s, "O",  "magmom", 0.0)
        s = In.assign_site_property_by_species(s, "Ca", "magmom", 0.0)
        assert In.site_properties_from_structure(s, "magmom") == [0.0, 2.0, 0.0, 0.0, 0.0]


class TestNoncollinearMagMom:
    def test_assign_by_species(self, perovskite):
        s = perovskite.copy()
        s = In.assign_site_property_by_species(s, "Ti", "magmom", [0, 0, 2.0])
        s = In.assign_site_property_by_species(s, "O",  "magmom", [0, 0, 0])
        s = In.assign_site_property_by_species(s, "Ca", "magmom", [0, 0, 0])
        for site in s.sites:
            expected = [0, 0, 2.0] if site.species_string == "Ti" else [0, 0, 0]
            assert site.properties["magmom"] == expected

    def test_site_properties_from_structure(self, fluorite):
        s = fluorite.copy()
        s = In.assign_site_property_by_species(s, "Ca", "magmom", [2.0, 0, -1])
        magmoms = In.site_properties_from_structure(s, "magmom", default=[0, 0, 0])
        assert magmoms == [[2.0, 0, -1]] * 4 + [[0, 0, 0]] * 8

    def test_assign_by_range(self, fluorite):
        s = fluorite.copy()
        s = In.assign_site_property_by_range(s, slice(0, 12, 2), "magmom", [2.0] * 3)
        s = In.assign_site_property_by_range(s, slice(1, 12, 2), "magmom", [0.0] * 3)
        for i, site in enumerate(s.sites):
            expected = [2.0] * 3 if i % 2 == 0 else [0.0] * 3
            assert site.properties["magmom"] == expected


class TestLDAUU:
    def test_assign_by_species(self, perovskite):
        s = perovskite.copy()
        s = In.assign_site_property_by_species(s, "Ti", "ldauu", 2.0)
        s = In.assign_site_property_by_species(s, "O",  "ldauu", 0.0)
        s = In.assign_site_property_by_species(s, "Ca", "ldauu", 0.0)
        for site in s.sites:
            assert site.properties["ldauu"] == (2.0 if site.species_string == "Ti" else 0.0)

    def test_assign_by_index(self, perovskite):
        s = perovskite.copy()
        zeros = [0, 2]
        twos  = [1, 3]
        ones  = [4]
        for i in zeros: s = In.assign_site_property_by_index(s, i, "ldauu", 0.0)
        for i in twos:  s = In.assign_site_property_by_index(s, i, "ldauu", 2.0)
        for i in ones:  s = In.assign_site_property_by_index(s, i, "ldauu", 1.0)
        for i, site in enumerate(s.sites):
            if i in zeros: assert site.properties["ldauu"] == 0.0
            elif i in twos: assert site.properties["ldauu"] == 2.0
            else: assert site.properties["ldauu"] == 1.0

    def test_assign_by_range(self, fluorite):
        s = fluorite.copy()
        s = In.assign_site_property_by_range(s, slice(0, 12, 2), "ldauu", 2.0)
        s = In.assign_site_property_by_range(s, slice(1, 12, 2), "ldauu", 0.0)
        for i, site in enumerate(s.sites):
            assert site.properties["ldauu"] == (2.0 if i % 2 == 0 else 0.0)

    def test_from_structure(self, perovskite):
        s = perovskite.copy()
        s = In.assign_site_property_by_species(s, "Ti", "ldauu", 2.0)
        s = In.assign_site_property_by_species(s, "O",  "ldauu", 0.0)
        s = In.assign_site_property_by_species(s, "Ca", "ldauu", 0.0)
        assert In.site_properties_from_structure(s, "ldauu") == [0.0, 2.0, 0.0, 0.0, 0.0]


class TestReadSiteProperties:
    @pytest.fixture(autouse=True)
    def _load_dicts(self):
        self.species_dict     = Io.load_abvio_yaml(FILES_DIR / "magmom_species.yaml")["incar"]
        self.index_dict       = Io.load_abvio_yaml(FILES_DIR / "magmom_index.yaml")["incar"]
        self.range_dict       = Io.load_abvio_yaml(FILES_DIR / "magmom_range.yaml")["incar"]
        self.nc_species_dict  = Io.load_abvio_yaml(FILES_DIR / "magmom_noncollinear_species.yaml")["incar"]
        self.nc_index_dict    = Io.load_abvio_yaml(FILES_DIR / "magmom_noncollinear_index.yaml")["incar"]
        self.nc_range_dict    = Io.load_abvio_yaml(FILES_DIR / "magmom_noncollinear_range.yaml")["incar"]

    def test_species_keys_are_strings(self):
        for k in self.species_dict["magmom"]:
            assert isinstance(k, str)

    def test_index_keys_are_ints(self):
        for k in self.index_dict["magmom"]:
            assert isinstance(k, int)

    def test_range_is_list_of_dicts(self):
        for d in self.range_dict["magmom"]:
            assert isinstance(d, dict)

    def test_nc_species_values_are_lists(self):
        for v in self.nc_species_dict["magmom"].values():
            assert isinstance(v, list)

    def test_nc_index_keys_are_ints(self):
        for k in self.nc_index_dict["magmom"]:
            assert isinstance(k, int)

    def test_is_index_dict(self):
        for d in [self.index_dict, self.nc_index_dict]:
            assert In.is_index_dict(d["magmom"])
        for d in [self.species_dict, self.range_dict, self.nc_species_dict, self.nc_range_dict]:
            assert not In.is_index_dict(d["magmom"])

    def test_is_species_dict(self):
        for d in [self.species_dict, self.nc_species_dict]:
            assert In.is_species_dict(d["magmom"])
        for d in [self.index_dict, self.range_dict, self.nc_index_dict, self.nc_range_dict]:
            assert not In.is_species_dict(d["magmom"])

    def test_is_range_list(self):
        for d in [self.range_dict, self.nc_range_dict]:
            assert In.is_range_list(d["magmom"])
        for d in [self.species_dict, self.index_dict, self.nc_species_dict, self.nc_index_dict]:
            assert not In.is_range_list(d["magmom"])

    def test_is_collinear(self):
        for d in [self.species_dict, self.index_dict, self.range_dict]:
            assert In.is_collinear(d["magmom"])
        for d in [self.nc_species_dict, self.nc_index_dict, self.nc_range_dict]:
            assert not In.is_collinear(d["magmom"])


class TestIncarModel:
    def test_valid_collinear(self, perovskite):
        incar_dict = {
            "magmom": {"Ti": 2.0, "O": 0.0, "Ca": 0.0},
            "ediff": 1e-4, "ismear": -5, "lreal": False,
            "ediffg": -0.01, "lwave": False,
        }
        model = In.IncarModel(incar_dict=incar_dict)
        incar = model.incar(perovskite)
        assert isinstance(incar, Incar)
        incar.check_params()

    def test_valid_noncollinear(self, perovskite):
        incar_dict = {
            "magmom": {"Ti": [0, 0, 2.0], "O": [0, 0, 0], "Ca": [0, 0, 0]},
            "ediff": 1e-4, "ismear": -5, "lreal": False,
            "ediffg": -0.01, "lwave": False,
        }
        model = In.IncarModel(incar_dict=incar_dict)
        incar = model.incar(perovskite)
        assert isinstance(incar, Incar)
        incar.check_params()
        assert incar["MAGMOM"] == [[0, 0, 0], [0, 0, 2.0], [0, 0, 0], [0, 0, 0], [0, 0, 0]]

    def test_invalid_magmom_raises(self, fluorite):
        incar_dict = {
            "magmom": [{"Ti": 2.0}, {"O": 0.0}, {"Ca": 0.0}],
            "ediff": 1e-4, "ismear": -5, "lreal": False,
        }
        with pytest.raises(ValueError):
            In.IncarModel(incar_dict=incar_dict).incar(fluorite)

    def test_range_magmom(self, fluorite):
        incar_dict = {
            "magmom": [
                {"start": 0, "stop": 12, "step": 2, "value": 50.0},
                {"start": 1, "stop": 12, "step": 2, "value":  7.0},
            ],
            "ediff": 1e-4, "ismear": -5, "lreal": False,
        }
        model = In.IncarModel(incar_dict=incar_dict)
        incar = model.incar(fluorite)
        incar.check_params()
        for i, m in enumerate(incar["MAGMOM"]):
            assert m == (50.0 if i % 2 == 0 else 7.0)
