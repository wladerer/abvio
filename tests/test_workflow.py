"""
Tests for abvio.workflow and abvio.steps.

Strategy
--------
Parsl is never loaded. run_step is monkeypatched to return pre-resolved
concurrent.futures.Future objects. parsl.load and parsl.clear are no-ops.
All prep functions are replaced with a stub that creates the dst directory
and writes a CONTCAR so downstream steps can read a structure.
"""

from __future__ import annotations

import concurrent.futures as cf
import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from pymatgen.core import Structure
from pymatgen.io.vasp.inputs import Poscar

import abvio.workflow as wf
import abvio.steps as steps
from abvio.steps import check_convergence, ldau_for_structure
from abvio.workflow import (
    State,
    VaspWorkflow,
    _make_submit_script,
    make_parsl_config,
)

STRUCTURES_DIR = Path(__file__).parent / "structures"
STRUCTURE_FILE = str(STRUCTURES_DIR / "CaTiO3.vasp")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_yaml(tmp_path: Path, step_list: list[dict], **overrides) -> Path:
    cfg = {
        "name":          "test_wf",
        "root":          str(tmp_path / "root"),
        "poll_interval": 0,
        "slurm":         {"nodes": 1, "ntasks": 4, "time": "1:00:00",
                          "vasp_cmd": "mpirun vasp_std"},
        "potcar_map":    {"Ca": "Ca_pv", "Ti": "Ti_pv", "O": "O"},
        "steps":         step_list,
        **overrides,
    }
    p = tmp_path / "workflow.yaml"
    p.write_text(yaml.dump(cfg))
    return p


def _dummy_prep(dst: Path, cfg: dict, prev: Path | None, potcar_map: dict):
    """Create dst and write a CONTCAR so downstream steps can read a structure."""
    dst.mkdir(parents=True, exist_ok=True)
    contcar = dst / "CONTCAR"
    if prev and (prev / "CONTCAR").exists():
        shutil.copy(prev / "CONTCAR", contcar)
    else:
        Poscar(Structure.from_file(STRUCTURE_FILE)).write_file(str(contcar))


def _resolved(value=True) -> cf.Future:
    """Return an already-resolved Future."""
    f: cf.Future = cf.Future()
    f.set_result(value)
    return f


def _failed(exc: Exception | None = None) -> cf.Future:
    """Return an already-failed Future."""
    f: cf.Future = cf.Future()
    f.set_exception(exc or RuntimeError("step failed"))
    return f


# ─────────────────────────────────────────────────────────────────────────────
# Core fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_parsl(monkeypatch):
    """Patch parsl.load and parsl.clear to no-ops."""
    monkeypatch.setattr(wf.parsl, "load", lambda cfg: None)
    monkeypatch.setattr(wf.parsl, "clear", lambda: None)


@pytest.fixture
def mock_prep(monkeypatch):
    """Replace all PREP_FUNCTIONS with _dummy_prep."""
    for name in list(steps.PREP_FUNCTIONS):
        monkeypatch.setitem(steps.PREP_FUNCTIONS, name, _dummy_prep)


@pytest.fixture
def mock_run_step(monkeypatch):
    """
    Replace run_step with a synchronous callable returning pre-resolved futures.

    The returned controller has:
        .results     — dict[step_name, bool | Exception]; default True
        .call_log    — list of step_names in submission order
        .inputs_log  — dict[step_name, list[Future]] — inputs passed per step
    """
    ctrl = MagicMock()
    ctrl.results    = {}
    ctrl.call_log   = []
    ctrl.inputs_log = {}

    def fake_run_step(step_name, step_type, step_cfg, step_dir,
                      prev_dir, potcar_map, vasp_cmd, inputs=None):
        ctrl.call_log.append(step_name)
        ctrl.inputs_log[step_name] = list(inputs or [])

        # Propagate parent exception (mirrors Parsl behaviour)
        for dep in (inputs or []):
            if dep.done() and dep.exception():
                return _failed(dep.exception())

        outcome = ctrl.results.get(step_name, True)
        if isinstance(outcome, Exception):
            return _failed(outcome)
        return _resolved(outcome)

    monkeypatch.setattr(wf, "run_step", fake_run_step)
    return ctrl


@pytest.fixture
def env(mock_parsl, mock_run_step, mock_prep):
    """Combined fixture: no Parsl, no VASP, no real prep. Returns run_step ctrl."""
    return mock_run_step


# ─────────────────────────────────────────────────────────────────────────────
# Unit — ldau_for_structure (moved to steps.py)
# ─────────────────────────────────────────────────────────────────────────────

class TestLdauForStructure:
    @pytest.fixture(autouse=True)
    def _struct(self):
        self.s = Structure.from_file(STRUCTURE_FILE)

    def test_known_species_ordered(self):
        result = ldau_for_structure(self.s, {"Ti": (2, 4.0, 0.0)})
        assert result["LDAUL"] == [-1,  2, -1]
        assert result["LDAUU"] == [0.0, 4.0, 0.0]
        assert result["LDAUJ"] == [0.0, 0.0, 0.0]

    def test_no_hubbard_gives_defaults(self):
        result = ldau_for_structure(self.s, {})
        assert result["LDAUL"] == [-1, -1, -1]
        assert all(u == 0.0 for u in result["LDAUU"])

    def test_list_length_matches_species_count(self):
        result = ldau_for_structure(self.s, {"Ca": (0, 1.0, 0.0)})
        n = len({str(s.specie) for s in self.s})
        assert len(result["LDAUL"]) == n
        assert len(result["LDAUU"]) == n
        assert len(result["LDAUJ"]) == n


# ─────────────────────────────────────────────────────────────────────────────
# Unit — _make_submit_script
# ─────────────────────────────────────────────────────────────────────────────

class TestMakeSubmitScript:
    def test_explicit_directives(self):
        script = _make_submit_script(Path("/fake"), {
            "partition": "gpu", "nodes": 2, "ntasks": 64,
            "time": "06:00:00", "vasp_cmd": "srun vasp_std",
        })
        assert "#SBATCH --partition=gpu" in script
        assert "#SBATCH --nodes=2"       in script
        assert "#SBATCH --ntasks=64"     in script
        assert "#SBATCH --time=06:00:00" in script
        assert "srun vasp_std"           in script

    def test_defaults_applied(self):
        script = _make_submit_script(Path("/fake"), {})
        assert "mpirun vasp_std" in script
        assert "--partition"     not in script

    def test_queue_flag(self):
        script = _make_submit_script(Path("/fake"), {"queue": "debug"})
        assert "#SBATCH -q debug" in script
        assert "--partition"      not in script

    def test_extra_directives_appended(self):
        script = _make_submit_script(Path("/fake"), {
            "extra": ["--account=myproject", "--constraint=knl", "-q debug"],
        })
        assert "#SBATCH --account=myproject" in script
        assert "#SBATCH --constraint=knl"    in script
        assert "#SBATCH -q debug"            in script

    def test_extra_directives_absent_when_not_set(self):
        script = _make_submit_script(Path("/fake"), {})
        assert "--account"    not in script
        assert "--constraint" not in script

    def test_modules_and_env(self):
        script = _make_submit_script(Path("/fake"), {
            "modules":  ["VASP/6.1.2", "intel/2023"],
            "env":      {"VASP_NPROCS": 128, "OMP_NUM_THREADS": 1},
            "vasp_cmd": "mpirun vasp_ncl",
        })
        assert "module load VASP/6.1.2"   in script
        assert "module load intel/2023"   in script
        assert "export VASP_NPROCS=128"   in script
        assert "export OMP_NUM_THREADS=1" in script
        assert script.index("module load") < script.index("mpirun vasp_ncl")
        assert script.index("export")     < script.index("mpirun vasp_ncl")


# ─────────────────────────────────────────────────────────────────────────────
# Unit — make_parsl_config
# ─────────────────────────────────────────────────────────────────────────────

class TestMakeParslConfig:
    def test_returns_config_object(self, tmp_path):
        from parsl.config import Config
        cfg = make_parsl_config({"nodes": 1, "ntasks": 4, "time": "1:00:00"},
                                run_dir=tmp_path)
        assert isinstance(cfg, Config)

    def test_single_htex_executor(self, tmp_path):
        from parsl.executors import HighThroughputExecutor
        cfg = make_parsl_config({}, run_dir=tmp_path)
        assert len(cfg.executors) == 1
        assert isinstance(cfg.executors[0], HighThroughputExecutor)

    def test_scheduler_options_include_account(self, tmp_path):
        cfg = make_parsl_config({"account": "proj123"}, run_dir=tmp_path)
        opts = cfg.executors[0].provider.scheduler_options
        assert "--account=proj123" in opts

    def test_scheduler_options_include_queue(self, tmp_path):
        cfg = make_parsl_config({"queue": "debug"}, run_dir=tmp_path)
        opts = cfg.executors[0].provider.scheduler_options
        assert "-q debug" in opts

    def test_worker_init_includes_modules(self, tmp_path):
        cfg = make_parsl_config({"modules": ["VASP/6.4", "intel/2023"]},
                                run_dir=tmp_path)
        init = cfg.executors[0].provider.worker_init
        assert "module load VASP/6.4"   in init
        assert "module load intel/2023" in init

    def test_worker_init_includes_env(self, tmp_path):
        cfg = make_parsl_config({"env": {"OMP_NUM_THREADS": 1}},
                                run_dir=tmp_path)
        init = cfg.executors[0].provider.worker_init
        assert "export OMP_NUM_THREADS=1" in init

    def test_run_dir_set(self, tmp_path):
        cfg = make_parsl_config({}, run_dir=tmp_path / "parsl")
        assert cfg.run_dir == str(tmp_path / "parsl")


# ─────────────────────────────────────────────────────────────────────────────
# Unit — check_convergence
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckConvergence:
    def test_returns_false_for_missing_directory(self, tmp_path):
        assert check_convergence(tmp_path / "nonexistent") is False

    def test_returns_false_for_missing_vasprun(self, tmp_path):
        (tmp_path / "step").mkdir()
        assert check_convergence(tmp_path / "step") is False


# ─────────────────────────────────────────────────────────────────────────────
# Unit — user slurm config merging
# ─────────────────────────────────────────────────────────────────────────────

class TestUserSlurmConfig:
    def test_user_cfg_merged_over_yaml(self, tmp_path, env, monkeypatch):
        user_cfg = tmp_path / "config.yaml"
        user_cfg.write_text("account: secret\npartition: special\n")
        monkeypatch.setattr(wf, "_USER_SLURM_CFG", user_cfg)

        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
        ]))
        assert wflow.slurm_cfg["account"]   == "secret"
        assert wflow.slurm_cfg["partition"] == "special"

    def test_missing_user_cfg_is_silent(self, tmp_path, env, monkeypatch):
        monkeypatch.setattr(wf, "_USER_SLURM_CFG", tmp_path / "nonexistent.yaml")
        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
        ]))
        assert "account" not in wflow.slurm_cfg

    def test_extra_directives_from_user_cfg(self, tmp_path, env, monkeypatch):
        user_cfg = tmp_path / "config.yaml"
        user_cfg.write_text("extra:\n  - '--account=myproject'\n  - '-q high'\n")
        monkeypatch.setattr(wf, "_USER_SLURM_CFG", user_cfg)

        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
        ]))
        assert "--account=myproject" in wflow.slurm_cfg["extra"]
        script = _make_submit_script(Path("/fake"), wflow.slurm_cfg)
        assert "#SBATCH --account=myproject" in script
        assert "#SBATCH -q high"             in script


# ─────────────────────────────────────────────────────────────────────────────
# Graph readiness
# ─────────────────────────────────────────────────────────────────────────────

class TestGraphReadiness:
    def test_no_dep_step_is_ready(self, tmp_path, env):
        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
        ]))
        assert wflow._ready(wflow.steps["relax"])

    def test_dep_step_not_ready_while_parent_pending(self, tmp_path, env):
        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
            {"name": "scf",   "type": "scf",   "depends": "relax"},
        ]))
        assert not wflow._ready(wflow.steps["scf"])

    def test_dep_step_ready_after_parent_done(self, tmp_path, env):
        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
            {"name": "scf",   "type": "scf",   "depends": "relax"},
        ]))
        wflow.steps["relax"].state = State.DONE
        assert wflow._ready(wflow.steps["scf"])


# ─────────────────────────────────────────────────────────────────────────────
# DAG construction
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildDag:
    def test_single_step_submitted(self, tmp_path, env):
        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
        ]))
        futures = wflow._build_dag()
        assert "relax" in futures
        assert env.call_log == ["relax"]

    def test_chain_submitted_in_order(self, tmp_path, env):
        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
            {"name": "scf",   "type": "scf",   "depends": "relax"},
        ]))
        futures = wflow._build_dag()
        assert env.call_log == ["relax", "scf"]
        assert futures["relax"] in env.inputs_log["scf"]

    def test_branching_dag_all_submitted(self, tmp_path, env):
        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax",  "type": "relax",  "structure": STRUCTURE_FILE},
            {"name": "scf",    "type": "scf",    "depends": "relax"},
            {"name": "phonon", "type": "phonon", "depends": "relax",
             "supercell": [2, 2, 1]},
        ]))
        wflow._build_dag()
        assert set(env.call_log) == {"relax", "scf", "phonon"}
        # Both children receive relax's future as input
        relax_fut = env.inputs_log["scf"][0]
        assert relax_fut is env.inputs_log["phonon"][0]

    def test_done_step_skipped_not_resubmitted(self, tmp_path, env):
        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
            {"name": "scf",   "type": "scf",   "depends": "relax"},
        ]))
        wflow.steps["relax"].state = State.DONE
        wflow._build_dag()
        assert "relax" not in env.call_log
        assert "scf"   in env.call_log

    def test_unknown_step_type_raises(self, tmp_path, env):
        """_build_dag doesn't validate types; run_step raises inside the future."""
        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "mystery", "type": "does_not_exist",
             "structure": STRUCTURE_FILE},
        ]))
        # fake_run_step records the call; the type check happens inside run_step
        wflow._build_dag()
        assert "mystery" in env.call_log


# ─────────────────────────────────────────────────────────────────────────────
# Monitor — state transitions
# ─────────────────────────────────────────────────────────────────────────────

class TestMonitor:
    def test_converged_step_becomes_done(self, tmp_path, env):
        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
        ]))
        futures = wflow._build_dag()
        wflow._monitor(futures)
        assert wflow.steps["relax"].state == State.DONE

    def test_not_converged_step_becomes_failed(self, tmp_path, env):
        env.results["relax"] = False   # run_step returns False
        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
        ]))
        futures = wflow._build_dag()
        wflow._monitor(futures)
        assert wflow.steps["relax"].state == State.FAILED

    def test_exception_in_step_becomes_failed(self, tmp_path, env):
        env.results["relax"] = RuntimeError("POTCAR missing")
        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
        ]))
        futures = wflow._build_dag()
        wflow._monitor(futures)
        assert wflow.steps["relax"].state == State.FAILED

    def test_failed_parent_propagates_to_child(self, tmp_path, env):
        env.results["relax"] = RuntimeError("failed")
        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
            {"name": "scf",   "type": "scf",   "depends": "relax"},
        ]))
        futures = wflow._build_dag()
        wflow._monitor(futures)
        assert wflow.steps["relax"].state == State.FAILED
        assert wflow.steps["scf"].state   == State.FAILED

    def test_failed_step_does_not_block_independent_branch(self, tmp_path, env):
        env.results["relax"] = RuntimeError("failed")
        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax",  "type": "relax", "structure": STRUCTURE_FILE},
            {"name": "relax2", "type": "relax", "structure": STRUCTURE_FILE},
            {"name": "scf",    "type": "scf",   "depends": "relax2"},
        ]))
        futures = wflow._build_dag()
        wflow._monitor(futures)
        assert wflow.steps["relax"].state  == State.FAILED
        assert wflow.steps["relax2"].state == State.DONE
        assert wflow.steps["scf"].state    == State.DONE


# ─────────────────────────────────────────────────────────────────────────────
# Full run()
# ─────────────────────────────────────────────────────────────────────────────

class TestRun:
    def test_run_completes_single_step(self, tmp_path, env):
        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
        ]))
        wflow.run()
        assert wflow.steps["relax"].state == State.DONE

    def test_run_completes_chain(self, tmp_path, env):
        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
            {"name": "scf",   "type": "scf",   "depends": "relax"},
        ]))
        wflow.run()
        assert wflow.steps["relax"].state == State.DONE
        assert wflow.steps["scf"].state   == State.DONE

    def test_run_completes_branching_dag(self, tmp_path, env):
        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax",  "type": "relax",  "structure": STRUCTURE_FILE},
            {"name": "scf",    "type": "scf",    "depends": "relax"},
            {"name": "phonon", "type": "phonon", "depends": "relax",
             "supercell": [2, 2, 1]},
        ]))
        wflow.run()
        assert wflow.steps["relax"].state  == State.DONE
        assert wflow.steps["scf"].state    == State.DONE
        assert wflow.steps["phonon"].state == State.DONE

    def test_run_marks_failed_step(self, tmp_path, env):
        env.results["relax"] = False
        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
        ]))
        wflow.run()
        assert wflow.steps["relax"].state == State.FAILED

    def test_parsl_cleared_after_run(self, tmp_path, env, monkeypatch):
        cleared = []
        monkeypatch.setattr(wf.parsl, "clear", lambda: cleared.append(True))
        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
        ]))
        wflow.run()
        assert cleared, "parsl.clear() was not called"

    def test_parsl_cleared_even_on_exception(self, tmp_path, mock_parsl,
                                             mock_prep, monkeypatch):
        cleared = []
        monkeypatch.setattr(wf.parsl, "clear", lambda: cleared.append(True))

        def exploding_run_step(*a, **kw):
            raise RuntimeError("unexpected")
        monkeypatch.setattr(wf, "run_step", exploding_run_step)

        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
        ]))
        with pytest.raises(Exception):
            wflow.run()
        assert cleared, "parsl.clear() was not called after exception"


# ─────────────────────────────────────────────────────────────────────────────
# State persistence
# ─────────────────────────────────────────────────────────────────────────────

class TestStatePersistence:
    def test_state_written_after_run(self, tmp_path, env):
        yaml_path = _make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
        ])
        VaspWorkflow(yaml_path).run()
        state_file = Path(tmp_path / "root") / VaspWorkflow.STATE_FILE
        assert state_file.exists()
        data = json.loads(state_file.read_text())
        assert data["relax"]["state"] == "done"

    def test_done_steps_not_resubmitted_on_reload(self, tmp_path, env):
        yaml_path = _make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
            {"name": "scf",   "type": "scf",   "depends": "relax"},
        ])
        # First run — complete relax only (scf fails)
        env.results["scf"] = RuntimeError("failed first time")
        VaspWorkflow(yaml_path).run()

        # Reset and re-run — relax should not be resubmitted
        env.call_log.clear()
        env.results.pop("scf")
        VaspWorkflow(yaml_path).run()

        assert "relax" not in env.call_log
        assert "scf"   in env.call_log

    def test_state_restored_correctly(self, tmp_path, env):
        yaml_path = _make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
        ])
        wf1 = VaspWorkflow(yaml_path)
        wf1.run()

        wf2 = VaspWorkflow(yaml_path)
        assert wf2.steps["relax"].state == State.DONE
