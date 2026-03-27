import pytest
import yaml
import os
import abvio.aio as Io

from pathlib import Path
from pymatgen.core import Structure
from pymatgen.io.vasp import Incar, Kpoints, Poscar

FILES_DIR   = Path(__file__).parent / "files"
VASPSETS_DIR = Path(__file__).parent / "vaspsets"


class TestLoadFunction:
    def test_invalid_yaml_raises_scanner_error(self):
        with pytest.raises(yaml.scanner.ScannerError):
            Io.load_abvio_yaml(FILES_DIR / "invalid.yaml")

    def test_invalid_yaml_raises_yaml_error(self):
        with pytest.raises(yaml.YAMLError):
            Io.load_abvio_yaml(FILES_DIR / "invalid.yaml")


class TestCreateInput:
    @pytest.fixture(autouse=True)
    def _input(self):
        self.obj = Io.Input.from_file(FILES_DIR / "valid.yaml")

    def test_from_file_returns_input(self):
        assert isinstance(self.obj, Io.Input)

    def test_kpoints(self):
        kpoints = self.obj.kpoints
        assert isinstance(kpoints, Kpoints)
        for kpt in kpoints.kpts:
            assert kpt == (5, 5, 5)

    def test_incar(self):
        incar = self.obj.incar
        assert isinstance(incar, Incar)
        assert float(incar["EDIFF"]) == 1e-6
        assert incar["EDIFFG"] == -0.01
        assert incar["ISIF"]   == 3
        assert incar["NSW"]    == 4
        assert incar["IBRION"] == 2
        assert incar["MAGMOM"] == [2] * 4 + [0.6] * 8

    def test_structure(self):
        assert isinstance(self.obj.structure, Structure)

    def test_write(self, tmp_path):
        self.obj.write_inputs(str(tmp_path))
        assert (tmp_path / "POSCAR").exists()
        assert (tmp_path / "INCAR").exists()
        assert (tmp_path / "KPOINTS").exists()
        Poscar.from_file(tmp_path / "POSCAR")
        Incar.from_file(tmp_path / "INCAR")
        Kpoints.from_file(tmp_path / "KPOINTS")


class TestSiBandStructure:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.si_dir = VASPSETS_DIR / "band"
        self.obj = Io.Input.from_file(self.si_dir / "equivalent.yaml")

    def test_incar(self):
        assert self.obj.incar == Incar.from_file(self.si_dir / "INCAR")

    def test_kpoints(self):
        expected = Kpoints.from_file(self.si_dir / "KPOINTS")
        assert set(self.obj.kpoints.kpts) == set(expected.kpts)

    def test_structure(self):
        expected = Poscar.from_file(self.si_dir / "POSCAR").structure
        assert self.obj.structure.reduced_formula == expected.reduced_formula


class TestPerovskiteSet:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.pv_dir = VASPSETS_DIR / "perovskite"
        self.obj = Io.Input.from_file(self.pv_dir / "equivalent.yaml")

    def test_incar(self):
        expected = Incar.from_file(self.pv_dir / "INCAR")
        assert self.obj.incar["MAGMOM"] == expected["MAGMOM"]
        assert self.obj.incar["LWAVE"]  == expected["LWAVE"]
        assert self.obj.incar["ENCUT"]  == expected["ENCUT"]

    def test_kpoints(self):
        expected = Kpoints.from_file(self.pv_dir / "KPOINTS")
        assert set(self.obj.kpoints.kpts) == set(expected.kpts)

    def test_structure(self):
        expected = Poscar.from_file(self.pv_dir / "POSCAR").structure
        assert self.obj.structure.reduced_formula == expected.reduced_formula

    def test_slurm_job(self, tmp_path):
        job = self.obj.job
        assert job.scheduler == "slurm"
        assert job.shebang   == "#!/bin/bash"
        assert job.script    == ['echo "Hello World"', 'echo "Goodbye World"']
        assert "cores"  in job.directives_dict
        assert "memory" in job.directives_dict

        out = tmp_path / "submit.sh"
        job.to_file(str(out))
        content = out.read_text()
        assert "#!/bin/bash" in content
        assert "--cpus-per-task=4" in content
        assert "--mem=8G" in content
        assert 'echo "Hello World"' in content

    def test_pbs_job(self, tmp_path):
        obj = Io.Input.from_file(self.pv_dir / "equivalent_pbs.yaml")
        job = obj.job
        job.scheduler = "pbs"

        out = tmp_path / "submit.sh"
        job.to_file(str(out))
        content = out.read_text()
        assert "#!/bin/bash" in content
        assert "#PBS -l select=1:ncpus=4:mem=7630MB" in content
        assert "#PBS -l walltime=00:30:00" in content
        assert "#PBS -l nodes=2" in content
