import pytest
import os
import numpy as np
import abvio.structure as st
import abvio.aio as Io

from pymatgen.io.vasp import Poscar
from pymatgen.core import Structure, Lattice
from pathlib import Path

STRUCTURES_DIR = Path(__file__).parent / "structures"
FILES_DIR      = Path(__file__).parent / "files"


def matrix_close(a: np.ndarray, b: np.ndarray, tol: float = 1e-6) -> bool:
    return np.allclose(a, b, atol=tol)


class TestFormattingFunctions:
    def test_dict_species(self):
        assert st.format_species([{"Fe": 2}, {"O": 4}]) == ["Fe", "Fe", "O", "O", "O", "O"]

    def test_single_species(self):
        assert st.format_species(["Fe"]) == ["Fe"]

    def test_list_species(self):
        assert st.format_species(["Fe", "O"]) == ["Fe", "O"]

    @pytest.mark.parametrize("bad", ["Fe", 2, {4, 0}, {4: 0}, [{4: 0}]])
    def test_invalid_raises(self, bad):
        with pytest.raises(ValueError):
            st.format_species(bad)


class TestBaseStructure:
    @pytest.mark.parametrize("mode", ["external", "manual", "prototype"])
    def test_valid_modes(self, mode):
        st.BaseStructure(mode=mode)

    def test_external_with_file_and_code(self):
        st.BaseStructure(mode="external", file="POSCAR")
        st.BaseStructure(mode="external", code="mp-1234")
        st.BaseStructure(mode="external", code="1234")

    @pytest.mark.parametrize("mode", ["internal", "wrong", "JohnCena"])
    def test_invalid_modes(self, mode):
        with pytest.raises(ValueError):
            st.BaseStructure(mode=mode)


class TestManualStructure:
    def test_from_lattice_object(self):
        model = st.ManualStructure(
            lattice=Lattice.from_parameters(1,1,1,90,90,90),
            species=["Mg","O"], coords=[[0,0,0],[0.5,0.5,0.5]],
        )
        assert isinstance(model.structure, Structure)

    def test_from_list(self):
        model = st.ManualStructure(
            lattice=[[1,0,0],[0,1,0],[0,0,1]],
            species=["Mg","O"], coords=[[0,0,0],[0.5,0.5,0.5]],
        )
        assert isinstance(model.structure, Structure)

    def test_from_numpy(self):
        model = st.ManualStructure(
            lattice=np.eye(3),
            species=["Mg","O"], coords=[[0,0,0],[0.5,0.5,0.5]],
        )
        assert isinstance(model.structure, Structure)

    def test_mismatched_species_coords_raises(self):
        with pytest.raises(ValueError):
            st.ManualStructure(
                lattice=Lattice.from_parameters(1,1,1,90,90,120),
                species=["Mg","O","Ti"], coords=[[0,0,0],[0.5,0.5,0.5]],
            ).structure

    def test_mismatched_coords_species_raises(self):
        with pytest.raises(ValueError):
            st.ManualStructure(
                lattice=Lattice.from_parameters(1,1,1,90,40,90),
                species=["Mg","O"], coords=[[0,0,0],[0.5,0.5,0.5],[0.5,0.5,0.5]],
            ).structure

    def test_from_yaml(self):
        model = st.ManualStructure.model_validate(
            Io.load_abvio_yaml(FILES_DIR / "lattice_list.yaml")["structure"]
        )
        assert isinstance(model.structure, Structure)


class TestPrototypeStructure:
    @pytest.fixture(autouse=True)
    def _load(self):
        self.perovskite_dict = Io.load_abvio_yaml(FILES_DIR / "prototype_perovskite.yaml")["structure"]
        self.fluorite_dict   = Io.load_abvio_yaml(FILES_DIR / "prototype_fluorite.yaml")["structure"]
        self.perovskite_ref  = Structure.from_file(STRUCTURES_DIR / "CaTiO3.vasp")
        self.fluorite_ref    = Structure.from_file(STRUCTURES_DIR / "CaF2.vasp")

    def test_perovskite(self):
        d = self.perovskite_dict
        model = st.PrototypeStructure(species=d["species"], lattice=d["lattice"],
                                      prototype=d["prototype"])
        s = model.structure
        assert isinstance(s, Structure)
        assert matrix_close(s.lattice.matrix, self.perovskite_ref.lattice.matrix)

    def test_fluorite(self):
        d = self.fluorite_dict
        model = st.PrototypeStructure(species=d["species"], lattice=d["lattice"],
                                      prototype=d["prototype"])
        s = model.structure
        assert isinstance(s, Structure)
        assert matrix_close(s.lattice.matrix, self.fluorite_ref.lattice.matrix)


@pytest.mark.network
class TestStructureFromMaterialsProject:
    def test_valid_code(self):
        assert isinstance(st.structure_from_mpi_code("mp-5827"), Structure)


class TestExternalStructure:
    @pytest.mark.parametrize("fname", ["CaTiO3.vasp", "CaF2.vasp"])
    def test_from_file(self, fname):
        model = st.ExternalStructure(file=str(STRUCTURES_DIR / fname))
        assert isinstance(model.structure, Structure)

    def test_from_string(self):
        string = str(Poscar.from_file(STRUCTURES_DIR / "CaTiO3.vasp"))
        assert isinstance(st.ExternalStructure(string=string).structure, Structure)

    @pytest.mark.network
    def test_from_materials_project(self):
        assert isinstance(st.ExternalStructure(code="mp-5827").structure, Structure)


class TestStructureFromInputDict:
    def test_valid(self):
        model = st.structure_model_from_input_dict({
            "mode": "external", "file": str(STRUCTURES_DIR / "CaTiO3.vasp")
        })
        assert isinstance(model.structure, Structure)

    def test_conflicting_fields_raises(self):
        with pytest.raises(ValueError):
            st.structure_model_from_input_dict({
                "mode": "external",
                "file": str(STRUCTURES_DIR / "CaTiO3.vasp"),
                "string": "string",
            })


class TestStructureMeta:
    @pytest.fixture(autouse=True)
    def _ref(self):
        self.perovskite_ref = Structure.from_file(STRUCTURES_DIR / "CaTiO3.vasp")

    def test_external(self):
        model = st.StructureMeta.from_dict({
            "mode": "external", "file": str(STRUCTURES_DIR / "CaTiO3.vasp")
        })
        assert isinstance(model.structure, Structure)

    def test_prototype(self):
        model = st.StructureMeta.from_dict({
            "mode": "prototype", "species": ["Ca","Ti","O"],
            "lattice": {"a": 3.889471}, "prototype": "perovskite",
        })
        s = model.structure
        assert isinstance(s, Structure)
        assert matrix_close(s.lattice.matrix, self.perovskite_ref.lattice.matrix)

    def test_manual(self):
        model = st.StructureMeta.from_dict({
            "mode": "manual", "lattice": [[1,0,0],[0,1,0],[0,0,1]],
            "species": ["Mg","O"], "coords": [[0,0,0],[0.5,0.5,0.5]],
        })
        assert isinstance(model.structure, Structure)

    def test_conflicting_fields_raises(self):
        with pytest.raises(ValueError):
            st.StructureMeta.from_dict({
                "mode": "external",
                "file": str(STRUCTURES_DIR / "CaTiO3.vasp"),
                "string": "string",
            })
