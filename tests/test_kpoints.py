import pytest
import abvio.kpoints as kp

from pathlib import Path
from pymatgen.io.vasp import Kpoints
from pymatgen.core import Structure
from pydantic import ValidationError

STRUCTURES_DIR = Path(__file__).parent / "structures"
VASPSETS_DIR   = Path(__file__).parent / "vaspsets"


class TestBaseKpoints:
    def test_surface_and_autoline_require_structure(self):
        assert kp.BaseKpoints(mode="surface",  spacing=1).requires_structure
        assert kp.BaseKpoints(mode="autoline", spacing=1).requires_structure

    @pytest.mark.parametrize("alias", ["gamma", "Gamma", "GAMMA", "g", "G"])
    def test_gamma_aliases(self, alias):
        assert kp.BaseKpoints(mode=alias, spacing=1).mode == "gamma"

    @pytest.mark.parametrize("alias", ["monkhorst", "Monkhorst", "MONKHORST", "m", "M"])
    def test_monkhorst_aliases(self, alias):
        assert kp.BaseKpoints(mode=alias, spacing=1).mode == "monkhorst"

    def test_invalid_mode_int(self):
        with pytest.raises(ValueError):
            kp.BaseKpoints(mode=9, spacing=1, shift=(0,0,0))

    def test_invalid_mode_string(self):
        with pytest.raises(ValueError):
            kp.BaseKpoints(mode="wrong", spacing=1, shift=(0,0,0))


class TestLineModeKpoints:
    def test_valid_linemode_does_not_require_structure(self):
        model = kp.LineKpoints(spacing=30, paths=[[0,0,0],[0.5,0.5,0.5]], labels=["G","X"])
        assert not model.requires_structure
        assert isinstance(model.kpoints(), Kpoints)

    def test_invalid_2d_paths(self):
        with pytest.raises(ValueError):
            kp.LineKpoints(spacing=30, paths=[[0,0],[0.5,0.5]], labels=["G","X"])

    def test_mismatched_labels(self):
        with pytest.raises(ValueError):
            kp.LineKpoints(spacing=30, paths=[[0,0,0],[0.5,0.5,0.5]], labels=["G"])

    def test_too_many_labels(self):
        with pytest.raises(ValueError):
            kp.LineKpoints(spacing=30, paths=[[0,0,0],[0.5,0.5,0.5]], labels=["G","X","Y"]).kpoints()

    def test_fractional_spacing_invalid(self):
        with pytest.raises(ValueError):
            kp.LineKpoints(spacing=0.1, paths=[[0,0,0],[0.5,0.5,0.5]], labels=["G","X"]).kpoints()


class TestAutoLineKpoints:
    def test_fluorite(self, fluorite):
        model = kp.AutoLineKpoints(spacing=10)
        assert model.requires_structure
        kpoints = model.kpoints(fluorite)
        assert isinstance(kpoints, Kpoints)
        assert kpoints.num_kpts == 10

    def test_perovskite(self, perovskite):
        model = kp.AutoLineKpoints(spacing=35)
        kpoints = model.kpoints(perovskite)
        assert isinstance(kpoints, Kpoints)
        assert kpoints.num_kpts == 35

    def test_fractional_spacing_invalid(self):
        with pytest.raises(ValueError):
            kp.AutoLineKpoints(spacing=0.1).kpoints(None)


class TestSurfaceKpoints:
    def test_valid(self, fluorite):
        model = kp.SurfaceKpoints(spacing=80000)
        assert model.requires_structure
        assert isinstance(model.kpoints(fluorite), Kpoints)


class TestGammaKpoints:
    def test_does_not_require_structure(self):
        model = kp.GammaKpoints(spacing=[3,3,3])
        assert not model.requires_structure
        assert isinstance(model.kpoints(), Kpoints)

    def test_matches_file(self):
        model = kp.GammaKpoints(spacing=[7,7,7])
        kpts = [list(k) for k in model.kpoints().kpts]
        expected = [list(k) for k in Kpoints.from_file(VASPSETS_DIR / "fluorite" / "KPOINTS").kpts]
        assert kpts == expected

    def test_write(self, tmp_path):
        kp.GammaKpoints(spacing=[7,7,7]).kpoints().write_file(str(tmp_path / "KPOINTS"))


class TestMonkhorstKpoints:
    def test_valid(self):
        spacing = [2,2,1]
        model = kp.MonkhorstKpoints(spacing=spacing)
        kpoints = model.kpoints()
        assert isinstance(kpoints, Kpoints)
        assert list(kpoints.kpts[0]) == spacing


class TestAutoLinemodeFromDict:
    def test_model_equality(self):
        manual = kp.AutoLineKpoints(spacing=20)
        parsed = kp.AutoLineKpoints.validate({"mode": "autoline", "spacing": 20})
        assert parsed == manual

    def test_kpoints_object(self, fluorite):
        model = kp.AutoLineKpoints.validate({"mode": "autoline", "spacing": 20})
        assert isinstance(model.kpoints(fluorite), Kpoints)

    def test_invalid_spacing(self):
        with pytest.raises(ValidationError):
            kp.AutoLineKpoints.validate({"mode": "autoline", "spacing": 0.1})

    def test_surface(self, fluorite):
        model = kp.SurfaceKpoints.validate({"mode": "surface", "spacing": 80000})
        assert isinstance(model.kpoints(fluorite), Kpoints)


class TestLinemodeFromDict:
    LINE_DICT = {"mode": "line", "spacing": 30,
                 "paths": [[0,0,0],[0.5,0.5,0.5]], "labels": ["G","X"]}

    def test_model_equality(self):
        manual = kp.LineKpoints(spacing=30, paths=[[0,0,0],[0.5,0.5,0.5]], labels=["G","X"])
        assert kp.LineKpoints.validate(self.LINE_DICT) == manual

    def test_kpoints_object(self):
        assert isinstance(kp.LineKpoints.validate(self.LINE_DICT).kpoints(), Kpoints)

    def test_invalid_2d_paths(self):
        with pytest.raises(ValidationError):
            kp.LineKpoints.validate({"mode": "line", "spacing": 30,
                                     "paths": [[0,0],[0.5,0.5]], "labels": ["G","X"]})

    def test_insufficient_labels(self):
        with pytest.raises(ValidationError):
            kp.LineKpoints.validate({"mode": "line", "spacing": 30,
                                     "paths": [[0,0,0],[0.5,0.5,0.5]], "labels": ["G"]})


class TestKpointsModeDetection:
    VALID_DICTS = [
        {"mode": "line",     "spacing": 30, "paths": [[0,0,0],[0.5,0.5,0.5]], "labels": ["G","X"]},
        {"mode": "autoline", "spacing": 20},
        {"mode": "surface",  "spacing": 80000},
        {"mode": "gamma",    "spacing": [3,3,3]},
        {"mode": "Monkhorst","spacing": [2,2,1]},
        {"mode": "monkhorst-pack", "spacing": [4,2,7]},
    ]

    def test_all_valid_modes(self, fluorite):
        for d in self.VALID_DICTS:
            assert isinstance(kp.kpoints_from_dictionary(d, structure=fluorite), Kpoints)

    def test_invalid_2d_paths_raises(self):
        with pytest.raises(ValidationError):
            kp.kpoints_from_dictionary({"mode": "line", "spacing": 30,
                                        "paths": [[0,0],[0.5,0.5]], "labels": ["G","X"]})


class TestKpointsMeta:
    DICTS = [
        {"mode": "gamma",    "spacing": [3,3,3]},
        {"mode": "Monkhorst","spacing": [2,2,1]},
        {"mode": "surface",  "spacing": 80000},
        {"mode": "line",     "spacing": 30, "paths": [[0,0,0],[0.5,0.5,0.5]], "labels": ["G","X"]},
        {"mode": "autoline", "spacing": 20},
    ]

    def test_all_modes_produce_kpoints(self, fluorite):
        for d in self.DICTS:
            model = kp.KpointsMeta.from_dict(d)
            kpoints = model.kpoints(fluorite) if model.requires_structure else model.kpoints()
            assert isinstance(kpoints, Kpoints)
            assert model.mode == d["mode"].lower()
