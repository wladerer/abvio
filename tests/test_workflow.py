"""
Tests for abvio.workflow.

Strategy
--------
All SLURM calls (sbatch, squeue_states) are monkeypatched so no real cluster
is needed. All prep_* functions are replaced with a trivial stub that creates
the destination directory and writes a CONTCAR so downstream steps can read a
structure. check_convergence is patched per-test to control pass/fail outcomes.
time.sleep is patched where run() is exercised.
"""

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml
from pymatgen.core import Structure
from pymatgen.io.vasp.inputs import Poscar

import abvio.workflow as wf
from abvio.workflow import (
    State,
    VaspWorkflow,
    _make_submit_script,
    check_convergence,
    ldau_for_structure,
)

STRUCTURES_DIR = Path(__file__).parent / "structures"
STRUCTURE_FILE = str(STRUCTURES_DIR / "CaTiO3.vasp")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_yaml(tmp_path: Path, steps: list[dict], **overrides) -> Path:
    cfg = {
        "name":         "test_wf",
        "root":         str(tmp_path / "root"),
        "poll_interval": 0,
        "slurm":        {"partition": "test", "nodes": 1, "ntasks": 4, "time": "1:00:00"},
        "potcar_map":   {"Ca": "Ca_pv", "Ti": "Ti_pv", "O": "O"},
        "steps":        steps,
        **overrides,
    }
    p = tmp_path / "workflow.yaml"
    p.write_text(yaml.dump(cfg))
    return p


def _dummy_prep(dst: Path, cfg: dict, prev: Path | None, potcar_map: dict):
    """Create dst and drop a CONTCAR so dependent steps can read a structure."""
    dst.mkdir(parents=True, exist_ok=True)
    contcar = dst / "CONTCAR"
    if prev and (prev / "CONTCAR").exists():
        shutil.copy(prev / "CONTCAR", contcar)
    else:
        Poscar(Structure.from_file(STRUCTURE_FILE)).write_file(str(contcar))


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests — pure functions
# ─────────────────────────────────────────────────────────────────────────────

class TestLdauForStructure:
    @pytest.fixture(autouse=True)
    def _struct(self):
        self.s = Structure.from_file(STRUCTURE_FILE)  # Ca Ti O

    def test_known_species_ordered(self):
        result = ldau_for_structure(self.s, {"Ti": (2, 4.0, 0.0)})
        # CaTiO3 species order: Ca, Ti, O
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
        assert "--partition"     not in script   # partition is optional, not a default

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
            "modules": ["VASP/6.1.2", "intel/2023"],
            "env":     {"VASP_NPROCS": 128, "OMP_NUM_THREADS": 1},
            "vasp_cmd": "mpirun vasp_ncl",
        })
        assert "module load VASP/6.1.2"    in script
        assert "module load intel/2023"    in script
        assert "export VASP_NPROCS=128"    in script
        assert "export OMP_NUM_THREADS=1"  in script
        assert "mpirun vasp_ncl"           in script
        # modules/env must come before the vasp command
        assert script.index("module load") < script.index("mpirun vasp_ncl")
        assert script.index("export")      < script.index("mpirun vasp_ncl")


class TestUserSlurmConfig:
    def test_user_cfg_merged_over_yaml(self, tmp_path, mock_slurm, monkeypatch):
        """Settings in ~/.config/abvio/slurm.yaml override the workflow YAML."""
        user_cfg = tmp_path / "config.yaml"
        user_cfg.write_text("account: secret_project\npartition: special\n")
        monkeypatch.setattr(wf, "_USER_SLURM_CFG", user_cfg)

        yaml_path = _make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
        ])
        wflow = VaspWorkflow(yaml_path)
        assert wflow.slurm_cfg["account"]   == "secret_project"
        assert wflow.slurm_cfg["partition"] == "special"   # overrides YAML's "test"

    def test_missing_user_cfg_is_silent(self, tmp_path, mock_slurm, monkeypatch):
        """No error when ~/.config/abvio/slurm.yaml does not exist."""
        monkeypatch.setattr(wf, "_USER_SLURM_CFG", tmp_path / "nonexistent.yaml")
        yaml_path = _make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
        ])
        wflow = VaspWorkflow(yaml_path)
        assert "account" not in wflow.slurm_cfg

    def test_user_cfg_extra_in_slurm_cfg(self, tmp_path, mock_slurm, monkeypatch):
        """extra directives from the user file land in slurm_cfg and produce correct script."""
        user_cfg = tmp_path / "config.yaml"
        user_cfg.write_text("extra:\n  - '--account=myproject'\n  - '-q high'\n")
        monkeypatch.setattr(wf, "_USER_SLURM_CFG", user_cfg)

        yaml_path = _make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
        ])
        wflow = VaspWorkflow(yaml_path)
        assert "--account=myproject" in wflow.slurm_cfg["extra"]
        assert "-q high"             in wflow.slurm_cfg["extra"]

        # Verify they render into a submit script
        script = _make_submit_script(Path("/fake"), wflow.slurm_cfg)
        assert "#SBATCH --account=myproject" in script
        assert "#SBATCH -q high"             in script


class TestCheckConvergence:
    def test_returns_false_for_missing_directory(self, tmp_path):
        assert check_convergence(tmp_path / "nonexistent") is False

    def test_returns_false_for_missing_vasprun(self, tmp_path):
        (tmp_path / "step").mkdir()
        assert check_convergence(tmp_path / "step") is False


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixture: patch out all SLURM/prep/convergence calls
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_slurm(monkeypatch, tmp_path):
    """
    Patches sbatch, squeue_states, check_convergence, and all prep functions.

    Returns a namespace with:
        .job_counter        — increments with each sbatch call
        .squeue_live        — set of job_ids that squeue reports as running
        .convergence        — dict[str(dir), bool] override; default True
    """
    state = MagicMock()
    state.job_counter = 0
    state.squeue_live = set()
    state.convergence = {}

    def fake_sbatch(directory, slurm_cfg):
        state.job_counter += 1
        jid = str(state.job_counter * 100)
        state.squeue_live.add(jid)
        return jid

    def fake_squeue(job_ids):
        return {jid: "R" for jid in job_ids if jid in state.squeue_live}

    def fake_convergence(directory):
        return state.convergence.get(str(directory), True)

    monkeypatch.setattr(wf, "sbatch",           fake_sbatch)
    monkeypatch.setattr(wf, "squeue_states",    fake_squeue)
    monkeypatch.setattr(wf, "check_convergence", fake_convergence)
    for name in list(wf.PREP_FUNCTIONS):
        monkeypatch.setitem(wf.PREP_FUNCTIONS, name, _dummy_prep)

    return state


# ─────────────────────────────────────────────────────────────────────────────
# Graph logic
# ─────────────────────────────────────────────────────────────────────────────

class TestGraphReadiness:
    def test_no_dep_step_is_ready(self, tmp_path, mock_slurm):
        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
        ]))
        assert wflow._ready(wflow.steps["relax"])

    def test_dep_step_not_ready_while_parent_pending(self, tmp_path, mock_slurm):
        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
            {"name": "scf",   "type": "scf",   "depends": "relax"},
        ]))
        assert not wflow._ready(wflow.steps["scf"])

    def test_dep_step_ready_after_parent_done(self, tmp_path, mock_slurm):
        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
            {"name": "scf",   "type": "scf",   "depends": "relax"},
        ]))
        wflow.steps["relax"].state = State.DONE
        assert wflow._ready(wflow.steps["scf"])


# ─────────────────────────────────────────────────────────────────────────────
# Single-step lifecycle
# ─────────────────────────────────────────────────────────────────────────────

class TestSingleStep:
    def test_pending_to_running_on_first_tick(self, tmp_path, mock_slurm):
        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
        ]))
        assert wflow.steps["relax"].state == State.PENDING
        wflow._tick()
        assert wflow.steps["relax"].state  == State.RUNNING
        assert wflow.steps["relax"].job_id == "100"

    def test_running_to_done_when_job_leaves_queue(self, tmp_path, mock_slurm):
        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
        ]))
        wflow._tick()                            # → RUNNING
        mock_slurm.squeue_live.discard("100")    # simulate job finishing
        wflow._tick()                            # → DONE
        assert wflow.steps["relax"].state == State.DONE


# ─────────────────────────────────────────────────────────────────────────────
# Two-step chain (relax → scf)
# ─────────────────────────────────────────────────────────────────────────────

class TestChain:
    @pytest.fixture(autouse=True)
    def _wflow(self, tmp_path, mock_slurm):
        self.mock = mock_slurm
        self.wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
            {"name": "scf",   "type": "scf",   "depends": "relax"},
        ]))

    def test_scf_stays_pending_while_relax_running(self):
        self.wflow._tick()
        assert self.wflow.steps["relax"].state == State.RUNNING
        assert self.wflow.steps["scf"].state   == State.PENDING

    def test_scf_submitted_after_relax_done(self):
        self.wflow._tick()                           # relax → RUNNING
        self.mock.squeue_live.discard("100")         # relax finishes
        self.wflow._tick()                           # relax → DONE, scf → RUNNING
        assert self.wflow.steps["relax"].state == State.DONE
        assert self.wflow.steps["scf"].state   == State.RUNNING

    def test_full_chain_completes(self):
        self.wflow._tick()                           # relax → RUNNING
        self.mock.squeue_live.discard("100")
        self.wflow._tick()                           # relax → DONE, scf → RUNNING
        self.mock.squeue_live.discard("200")
        self.wflow._tick()                           # scf → DONE
        assert self.wflow.steps["relax"].state == State.DONE
        assert self.wflow.steps["scf"].state   == State.DONE


# ─────────────────────────────────────────────────────────────────────────────
# Branching DAG
# ─────────────────────────────────────────────────────────────────────────────

class TestBranchingDAG:
    def test_both_children_submitted_after_parent_done(self, tmp_path, mock_slurm):
        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax",  "type": "relax",  "structure": STRUCTURE_FILE},
            {"name": "scf",    "type": "scf",    "depends": "relax"},
            {"name": "phonon", "type": "phonon", "depends": "relax",
             "supercell": [2,2,1]},
        ]))
        wflow._tick()                               # relax → RUNNING
        mock_slurm.squeue_live.discard("100")
        wflow._tick()                               # relax → DONE; scf + phonon → RUNNING
        assert wflow.steps["relax"].state  == State.DONE
        assert wflow.steps["scf"].state    == State.RUNNING
        assert wflow.steps["phonon"].state == State.RUNNING


# ─────────────────────────────────────────────────────────────────────────────
# Failed calculations
# ─────────────────────────────────────────────────────────────────────────────

class TestFailedCalculation:
    def test_failed_step_marked_failed(self, tmp_path, mock_slurm):
        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
        ]))
        wflow._tick()                               # relax → RUNNING
        mock_slurm.convergence[str(wflow.steps["relax"].dir)] = False
        mock_slurm.squeue_live.discard("100")
        wflow._tick()                               # job done, not converged → FAILED
        assert wflow.steps["relax"].state == State.FAILED

    def test_failed_parent_leaves_child_pending(self, tmp_path, mock_slurm):
        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
            {"name": "scf",   "type": "scf",   "depends": "relax"},
        ]))
        wflow._tick()
        mock_slurm.convergence[str(wflow.steps["relax"].dir)] = False
        mock_slurm.squeue_live.discard("100")
        wflow._tick()                               # relax → FAILED
        wflow._tick()                               # scf should NOT submit
        assert wflow.steps["relax"].state == State.FAILED
        assert wflow.steps["scf"].state   == State.PENDING

    def test_failed_step_does_not_block_independent_branch(self, tmp_path, mock_slurm):
        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax",  "type": "relax", "structure": STRUCTURE_FILE},
            {"name": "relax2", "type": "relax", "structure": STRUCTURE_FILE},
            {"name": "scf",    "type": "scf",   "depends": "relax2"},
        ]))
        wflow._tick()                               # relax + relax2 → RUNNING
        # relax fails, relax2 succeeds
        mock_slurm.convergence[str(wflow.steps["relax"].dir)] = False
        mock_slurm.squeue_live.clear()
        wflow._tick()                               # relax → FAILED, relax2 → DONE, scf → RUNNING
        assert wflow.steps["relax"].state  == State.FAILED
        assert wflow.steps["relax2"].state == State.DONE
        assert wflow.steps["scf"].state    == State.RUNNING


# ─────────────────────────────────────────────────────────────────────────────
# Error handling
# ─────────────────────────────────────────────────────────────────────────────

class TestErrorHandling:
    def test_prep_failure_marks_step_failed(self, tmp_path, mock_slurm, monkeypatch):
        def bad_prep(dst, cfg, prev, potcar_map):
            raise RuntimeError("POTCAR not found")
        monkeypatch.setitem(wf.PREP_FUNCTIONS, "relax", bad_prep)

        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
        ]))
        wflow._tick()
        assert wflow.steps["relax"].state == State.FAILED

    def test_unknown_step_type_marks_failed(self, tmp_path, mock_slurm):
        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "mystery", "type": "does_not_exist",
             "structure": STRUCTURE_FILE},
        ]))
        wflow._tick()
        assert wflow.steps["mystery"].state == State.FAILED


# ─────────────────────────────────────────────────────────────────────────────
# State persistence
# ─────────────────────────────────────────────────────────────────────────────

class TestStatePersistence:
    def test_state_written_to_json(self, tmp_path, mock_slurm):
        yaml_path = _make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
        ])
        wflow = VaspWorkflow(yaml_path)
        wflow._tick()
        state_file = Path(wflow.cfg["root"]) / VaspWorkflow.STATE_FILE
        assert state_file.exists()
        data = json.loads(state_file.read_text())
        assert data["relax"]["state"]  == "running"
        assert data["relax"]["job_id"] == "100"

    def test_state_restored_on_reload(self, tmp_path, mock_slurm):
        yaml_path = _make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
        ])
        VaspWorkflow(yaml_path)._tick()             # relax → RUNNING, saved
        wflow2 = VaspWorkflow(yaml_path)            # load from disk
        assert wflow2.steps["relax"].state  == State.RUNNING
        assert wflow2.steps["relax"].job_id == "100"

    def test_reloaded_workflow_can_complete(self, tmp_path, mock_slurm):
        yaml_path = _make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
        ])
        VaspWorkflow(yaml_path)._tick()             # relax → RUNNING
        mock_slurm.squeue_live.discard("100")       # job finishes
        wflow2 = VaspWorkflow(yaml_path)
        wflow2._tick()                              # should detect job gone → DONE
        assert wflow2.steps["relax"].state == State.DONE


# ─────────────────────────────────────────────────────────────────────────────
# run() loop
# ─────────────────────────────────────────────────────────────────────────────

class TestRunLoop:
    def test_run_completes_all_steps(self, tmp_path, mock_slurm, monkeypatch):
        monkeypatch.setattr(wf.time, "sleep", lambda _: None)

        # Simulate jobs finishing: after each sbatch, immediately remove from queue
        original_sbatch = wf.sbatch
        def instant_sbatch(directory, slurm_cfg):
            jid = original_sbatch(directory, slurm_cfg)
            mock_slurm.squeue_live.discard(jid)
            return jid
        monkeypatch.setattr(wf, "sbatch", instant_sbatch)

        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
            {"name": "scf",   "type": "scf",   "depends": "relax"},
        ]))
        wflow.run()
        assert wflow.steps["relax"].state == State.DONE
        assert wflow.steps["scf"].state   == State.DONE

    def test_run_terminates_when_blocked_by_failed_parent(self, tmp_path, mock_slurm, monkeypatch):
        """run() must not loop forever when a failed step blocks all descendants."""
        monkeypatch.setattr(wf.time, "sleep", lambda _: None)

        original_sbatch = wf.sbatch
        def instant_fail_sbatch(directory, slurm_cfg):
            jid = original_sbatch(directory, slurm_cfg)
            mock_slurm.squeue_live.discard(jid)
            mock_slurm.convergence[str(directory)] = False
            return jid
        monkeypatch.setattr(wf, "sbatch", instant_fail_sbatch)

        wflow = VaspWorkflow(_make_yaml(tmp_path, [
            {"name": "relax", "type": "relax", "structure": STRUCTURE_FILE},
            {"name": "scf",   "type": "scf",   "depends": "relax"},
        ]))
        wflow.run()                                 # must not hang
        assert wflow.steps["relax"].state == State.FAILED
        assert wflow.steps["scf"].state   == State.PENDING  # blocked, never submitted
