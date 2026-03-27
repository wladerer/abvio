"""
Lightweight VASP workflow orchestrator.

Runs as a persistent polling daemon (e.g. inside tmux on an HPC login node).
Submits VASP jobs via sbatch, monitors them via squeue, and advances the
workflow graph when each step completes.

Usage
-----
    python -m abvio.workflow run mxenes.yaml
    python -m abvio.workflow status mxenes.yaml

Workflow YAML format
--------------------
    name: v4c3_pv
    root: /p/oldwork1/wladerer/mxenes_pv
    poll_interval: 60          # seconds between squeue checks

    slurm:                     # default SLURM directives for all steps
      partition: gpu
      nodes: 1
      ntasks: 128
      time: "12:00:00"
      vasp_cmd: mpirun vasp_std

    potcar_map:                # element → POTCAR label
      V: V_pv
      C: C
      O: O
      H: H

    steps:
      - name: relax
        type: relax
        structure: /path/to/monolayer.vasp

      - name: scf
        type: scf
        depends: relax

      - name: bands_nosoc
        type: bands
        depends: scf
        soc: false

      - name: scf_soc
        type: scf
        depends: relax
        soc: true

      - name: bands_soc
        type: bands
        depends: scf_soc
        soc: true

      - name: phonon
        type: phonon
        depends: relax
        supercell: [3, 3, 1]

      - name: adsorption_bare_H
        type: adsorption
        depends: relax
        adsorbate: H

      - name: soc_sp_bare_H
        type: soc_singlepoint
        depends: adsorption_bare_H
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
from enum import Enum
from pathlib import Path
from typing import Any, Callable

import yaml
from pymatgen.core import Structure
from pymatgen.io.vasp.inputs import Incar, Kpoints, Poscar, Potcar
from pymatgen.io.vasp.outputs import Vasprun
from pymatgen.io.vasp.sets import VaspInput

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# State
# ─────────────────────────────────────────────────────────────────────────────

class State(str, Enum):
    PENDING  = "pending"    # waiting for dependencies
    READY    = "ready"      # deps done, not yet submitted
    RUNNING  = "running"    # sbatch submitted, job in queue/running
    DONE     = "done"       # finished + converged
    FAILED   = "failed"     # finished but not converged


# ─────────────────────────────────────────────────────────────────────────────
# SLURM interface
# ─────────────────────────────────────────────────────────────────────────────

def sbatch(directory: Path, slurm_cfg: dict) -> str:
    """Write a submit script and call sbatch. Returns job ID."""
    script = _make_submit_script(directory, slurm_cfg)
    script_path = directory / "submit.sh"
    script_path.write_text(script)

    result = subprocess.run(
        ["sbatch", str(script_path)],
        capture_output=True, text=True, cwd=str(directory),
    )
    if result.returncode != 0:
        raise RuntimeError(f"sbatch failed: {result.stderr}")

    job_id = result.stdout.strip().split()[-1]
    log.info(f"Submitted {directory.name} → job {job_id}")
    return job_id


def squeue_states(job_ids: list[str]) -> dict[str, str]:
    """Return {job_id: state} for all given job IDs. Missing = completed."""
    if not job_ids:
        return {}
    result = subprocess.run(
        ["squeue", "--jobs", ",".join(job_ids), "--format=%i %t", "--noheader"],
        capture_output=True, text=True,
    )
    states = {}
    for line in result.stdout.strip().splitlines():
        parts = line.split()
        if len(parts) == 2:
            states[parts[0]] = parts[1]
    return states


_USER_SLURM_CFG = Path.home() / ".config" / "abvio" / "config.slurm"


def _load_user_slurm_cfg() -> dict:
    """Load ~/.config/abvio/slurm.yaml if it exists; silently return {} otherwise."""
    if _USER_SLURM_CFG.exists():
        with open(_USER_SLURM_CFG) as f:
            return yaml.safe_load(f) or {}
    return {}


def _make_submit_script(directory: Path, slurm_cfg: dict) -> str:
    nodes    = slurm_cfg.get("nodes", 1)
    ntasks   = slurm_cfg.get("ntasks", 128)
    time_    = slurm_cfg.get("time", "12:00:00")
    vasp_cmd = slurm_cfg.get("vasp_cmd", "mpirun vasp_std")
    name     = directory.name

    lines = [
        "#!/bin/bash",
        f"#SBATCH --job-name={name}",
        f"#SBATCH --nodes={nodes}",
        f"#SBATCH --ntasks={ntasks}",
        f"#SBATCH --time={time_}",
        f"#SBATCH --output={directory}/slurm-%j.out",
    ]

    if "partition" in slurm_cfg:
        lines.append(f"#SBATCH --partition={slurm_cfg['partition']}")
    if "queue" in slurm_cfg:
        lines.append(f"#SBATCH -q {slurm_cfg['queue']}")

    for directive in slurm_cfg.get("extra", []):
        lines.append(f"#SBATCH {directive}")

    lines.append("")

    for mod in slurm_cfg.get("modules", []):
        lines.append(f"module load {mod}")

    for key, val in slurm_cfg.get("env", {}).items():
        lines.append(f"export {key}={val}")

    lines += [f"cd {directory}", vasp_cmd, ""]
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Convergence check
# ─────────────────────────────────────────────────────────────────────────────

def check_convergence(directory: Path) -> bool:
    vr_path = directory / "vasprun.xml"
    if not vr_path.exists():
        return False
    try:
        vr = Vasprun(
            str(vr_path),
            parse_potcar_file=False,
            parse_projected_eigen=False,
            parse_eigen=False,
        )
        return vr.converged
    except Exception as e:
        log.warning(f"Could not parse {vr_path}: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# INCAR / POTCAR builders
# ─────────────────────────────────────────────────────────────────────────────

def ldau_for_structure(structure: Structure, u_vals: dict) -> dict:
    """Build LDAUL/U/J lists ordered by structure species. u_vals: {El: (L, U, J)}."""
    species = list(dict.fromkeys(str(s.specie) for s in structure))
    return {
        "LDAUL": [u_vals.get(sp, (-1, 0.0, 0.0))[0] for sp in species],
        "LDAUU": [u_vals.get(sp, (-1, 0.0, 0.0))[1] for sp in species],
        "LDAUJ": [u_vals.get(sp, (-1, 0.0, 0.0))[2] for sp in species],
    }


def potcar_for_structure(structure: Structure, potcar_map: dict) -> Potcar:
    species  = list(dict.fromkeys(str(s.specie) for s in structure))
    symbols  = [potcar_map.get(sp, sp) for sp in species]
    return Potcar(symbols=symbols, functional="PBE")


BASE_INCAR = {
    "ALGO":      "All",
    "EDIFF":     1e-6,
    "ENCUT":     550,
    "ISMEAR":    0,
    "SIGMA":     0.05,
    "ISPIN":     1,
    "ISYM":      0,
    "IVDW":      12,
    "KPAR":      4,
    "LASPH":     True,
    "LCHARG":    False,
    "LDAU":      True,
    "LDAUPRINT": 1,
    "LDAUTYPE":  2,
    "LMAXMIX":   4,
    "LORBIT":    11,
    "LREAL":     False,
    "LWAVE":     False,
    "NCORE":     16,
    "NELM":      300,
    "NSW":       0,
    "PREC":      "Accurate",
}

U_VALS = {"V": (2, 2.5, 0.0)}   # extend as needed


def write_vasp_input(directory: Path, structure: Structure,
                     incar_updates: dict, kpoints: Kpoints,
                     potcar_map: dict):
    """Write INCAR, POSCAR, KPOINTS, POTCAR to directory."""
    directory.mkdir(parents=True, exist_ok=True)
    poscar = Poscar(structure)
    potcar = potcar_for_structure(structure, potcar_map)
    incar  = Incar({**BASE_INCAR,
                    **ldau_for_structure(structure, U_VALS),
                    **incar_updates})
    VaspInput(incar=incar, kpoints=kpoints,
              poscar=poscar, potcar=potcar).write_input(str(directory))


# ─────────────────────────────────────────────────────────────────────────────
# Step preparation functions
# ─────────────────────────────────────────────────────────────────────────────

KPOINTS_SCF   = Kpoints.gamma_automatic((18, 18, 1))
KPOINTS_BULK  = Kpoints.gamma_automatic((18, 18, 4))
KPOINTS_COARSE = Kpoints.gamma_automatic((9, 9, 1))


def prep_relax(dst: Path, cfg: dict, _prev: Path | None, potcar_map: dict):
    structure = Structure.from_file(cfg["structure"])
    write_vasp_input(dst, structure,
                     {"NSW": 200, "IBRION": 2, "ISIF": 2,
                      "EDIFFG": -0.02, "LWAVE": True, "LCHARG": True},
                     KPOINTS_COARSE, potcar_map)


def prep_scf(dst: Path, cfg: dict, prev: Path, potcar_map: dict):
    structure = Structure.from_file(str(prev / "CONTCAR"))
    soc       = cfg.get("soc", False)
    updates   = {"ISTART": 0, "LWAVE": True, "LCHARG": True}
    if soc:
        updates.update({"LSORBIT": True, "NBANDS": 64, "SAXIS": [0, 0, 1]})
    write_vasp_input(dst, structure, updates, KPOINTS_SCF, potcar_map)


def prep_bands(dst: Path, cfg: dict, prev: Path, potcar_map: dict):
    """prev is the SCF directory. Copies CHGCAR and writes line-mode KPOINTS."""
    scf_dir   = prev
    structure = Structure.from_file(str(scf_dir / "CONTCAR"))
    soc       = cfg.get("soc", False)

    kpoints = _line_kpoints(structure)
    updates = {"ISTART": 1, "ICHARG": 11, "LORBIT": 11, "NSW": 0,
               "LWAVE": False, "LCHARG": False, "ISMEAR": 0, "SIGMA": 0.01}
    if soc:
        updates.update({"LSORBIT": True, "NBANDS": 64, "SAXIS": [0, 0, 1]})

    write_vasp_input(dst, structure, updates, kpoints, potcar_map)
    shutil.copy(scf_dir / "CHGCAR", dst / "CHGCAR")


def prep_phonon(dst: Path, cfg: dict, prev: Path, potcar_map: dict):
    """Create phonopy displaced supercells after relaxation."""
    import phonopy
    from phonopy.interface.vasp import write_vasp

    structure = Structure.from_file(str(prev / "CONTCAR"))
    sc_matrix = cfg.get("supercell", [3, 3, 1])

    ph = phonopy.Phonopy(
        _pmg_to_phonopy_atoms(structure),
        supercell_matrix=[[sc_matrix[0], 0, 0],
                          [0, sc_matrix[1], 0],
                          [0, 0, sc_matrix[2]]],
    )
    ph.generate_displacements(distance=0.01)
    ph.save(str(dst / "phonopy_params.yaml"))

    disp_dir = dst / "displacements"
    disp_dir.mkdir(exist_ok=True)
    for i, sc in enumerate(ph.supercells_with_displacements):
        d = disp_dir / f"disp-{i+1:03d}"
        d.mkdir(exist_ok=True)
        write_vasp(str(d / "POSCAR"), sc)
        sc_struct = _phonopy_atoms_to_pmg(sc, structure)
        write_vasp_input(d, sc_struct,
                         {"NSW": 0, "IBRION": -1, "LWAVE": False, "LCHARG": False,
                          "PREC": "Accurate"},
                         Kpoints.gamma_automatic((6, 6, 1)), potcar_map)

    log.info(f"Created {len(ph.supercells_with_displacements)} displacement dirs")


def prep_soc_singlepoint(dst: Path, cfg: dict, prev: Path, potcar_map: dict):
    """SOC single-point on the geometry from a completed adsorption run."""
    structure = Structure.from_file(str(prev / "CONTCAR"))
    write_vasp_input(dst, structure,
                     {"LSORBIT": True, "NBANDS": 64, "SAXIS": [0, 0, 1],
                      "NSW": 0, "LWAVE": False, "LCHARG": False},
                     KPOINTS_SCF, potcar_map)


def prep_adsorption(dst: Path, cfg: dict, prev: Path, potcar_map: dict):
    """Place adsorbate on relaxed slab using tinykit adsorb."""
    from tinykit.adsorb import get_molecule, adsorb

    slab      = Structure.from_file(str(prev / "CONTCAR"))
    molecule  = get_molecule(cfg["adsorbate"])
    structures = adsorb(slab, molecule)

    if not structures:
        raise RuntimeError(f"No adsorption sites found for {cfg['adsorbate']}")

    # Take the first (lowest-energy site from AdsorbateSiteFinder)
    structure = structures[0]
    write_vasp_input(dst, structure,
                     {"NSW": 100, "IBRION": 2, "ISIF": 2,
                      "EDIFFG": -0.02, "LWAVE": False, "LCHARG": False},
                     KPOINTS_SCF, potcar_map)


PREP_FUNCTIONS: dict[str, Callable] = {
    "relax":           prep_relax,
    "scf":             prep_scf,
    "bands":           prep_bands,
    "phonon":          prep_phonon,
    "soc_singlepoint": prep_soc_singlepoint,
    "adsorption":      prep_adsorption,
}


# ─────────────────────────────────────────────────────────────────────────────
# Workflow
# ─────────────────────────────────────────────────────────────────────────────

class WorkflowStep:
    def __init__(self, cfg: dict, root: Path):
        self.name    = cfg["name"]
        self.type    = cfg["type"]
        self.cfg     = cfg
        self.depends = cfg.get("depends")          # name of parent step, or None
        self.dir     = root / cfg.get("dir", cfg["name"])
        self.state   = State.PENDING
        self.job_id  = None

    def to_dict(self) -> dict:
        return {"name": self.name, "state": self.state.value,
                "job_id": self.job_id, "dir": str(self.dir)}


class VaspWorkflow:
    STATE_FILE = "workflow_state.json"

    def __init__(self, config_path: str | Path):
        with open(config_path) as f:
            self.cfg = yaml.safe_load(f)

        self.name         = self.cfg["name"]
        self.root         = Path(self.cfg["root"])
        # User-local overrides (~/.config/abvio/slurm.yaml) win over the workflow YAML.
        self.slurm_cfg    = {**self.cfg.get("slurm", {}), **_load_user_slurm_cfg()}
        self.potcar_map   = self.cfg.get("potcar_map", {})
        self.poll_interval = self.cfg.get("poll_interval", 60)

        self.steps: dict[str, WorkflowStep] = {}
        for step_cfg in self.cfg["steps"]:
            step = WorkflowStep(step_cfg, self.root)
            self.steps[step.name] = step

        self._load_state()

    # ── persistence ──────────────────────────────────────────────────────────

    def _state_path(self) -> Path:
        return self.root / self.STATE_FILE

    def _save_state(self):
        self.root.mkdir(parents=True, exist_ok=True)
        data = {name: step.to_dict() for name, step in self.steps.items()}
        self._state_path().write_text(json.dumps(data, indent=2))

    def _load_state(self):
        p = self._state_path()
        if not p.exists():
            return
        data = json.loads(p.read_text())
        for name, d in data.items():
            if name in self.steps:
                self.steps[name].state  = State(d["state"])
                self.steps[name].job_id = d.get("job_id")

    # ── graph helpers ─────────────────────────────────────────────────────────

    def _parent(self, step: WorkflowStep) -> WorkflowStep | None:
        return self.steps.get(step.depends) if step.depends else None

    def _ready(self, step: WorkflowStep) -> bool:
        if step.state != State.PENDING:
            return False
        parent = self._parent(step)
        return parent is None or parent.state == State.DONE

    # ── core loop ─────────────────────────────────────────────────────────────

    def run(self):
        log.info(f"Starting workflow '{self.name}'")
        while True:
            self._tick()
            terminal = {State.DONE, State.FAILED}
            if all(s.state in terminal for s in self.steps.values()):
                break
            if not self._can_make_progress():
                log.warning("No further progress possible (blocked by failed steps)")
                break
            time.sleep(self.poll_interval)
        self._print_status()

    def _can_make_progress(self) -> bool:
        """Return True if any step is running or could be submitted."""
        for s in self.steps.values():
            if s.state in (State.RUNNING, State.READY):
                return True
            if s.state == State.PENDING:
                parent = self._parent(s)
                if parent is None or parent.state == State.DONE:
                    return True
        return False

    def _tick(self):
        # 1. Update running jobs
        running = {s.name: s for s in self.steps.values()
                   if s.state == State.RUNNING and s.job_id}
        if running:
            live = squeue_states([s.job_id for s in running.values()])
            for name, step in running.items():
                if step.job_id not in live:
                    # Job left the queue — check convergence
                    if check_convergence(step.dir):
                        step.state = State.DONE
                        log.info(f"[DONE]   {name}")
                    else:
                        step.state = State.FAILED
                        log.warning(f"[FAILED] {name} — check {step.dir}")

        # 2. Submit newly ready steps
        for step in self.steps.values():
            if self._ready(step):
                step.state = State.READY
                try:
                    self._prepare_and_submit(step)
                except Exception as e:
                    step.state = State.FAILED
                    log.error(f"Preparation failed for {step.name}: {e}")

        self._save_state()

    def _prepare_and_submit(self, step: WorkflowStep):
        parent = self._parent(step)
        prev_dir = parent.dir if parent else None

        prep_fn = PREP_FUNCTIONS.get(step.type)
        if prep_fn is None:
            raise ValueError(f"Unknown step type: {step.type}")

        log.info(f"Preparing {step.name} ({step.type}) …")
        prep_fn(step.dir, step.cfg, prev_dir, self.potcar_map)

        step.job_id = sbatch(step.dir, self.slurm_cfg)
        step.state  = State.RUNNING

    # ── status display ────────────────────────────────────────────────────────

    def _print_status(self):
        print(f"\nWorkflow: {self.name}")
        print(f"{'Step':<30} {'Type':<18} {'State':<10} {'Job ID'}")
        print("-" * 70)
        for step in self.steps.values():
            print(f"{step.name:<30} {step.type:<18} "
                  f"{step.state.value:<10} {step.job_id or ''}")


# ─────────────────────────────────────────────────────────────────────────────
# phonopy ↔ pymatgen helpers (minimal, no extra deps)
# ─────────────────────────────────────────────────────────────────────────────

def _pmg_to_phonopy_atoms(structure: Structure):
    from phonopy.structure.atoms import PhonopyAtoms
    import numpy as np
    return PhonopyAtoms(
        symbols=[str(s.specie) for s in structure],
        cell=structure.lattice.matrix,
        scaled_positions=structure.frac_coords,
    )


def _phonopy_atoms_to_pmg(atoms, ref: Structure) -> Structure:
    from pymatgen.core import Lattice
    import numpy as np
    lattice = Lattice(atoms.cell)
    return Structure(lattice, atoms.symbols, atoms.scaled_positions)


def _line_kpoints(structure: Structure) -> Kpoints:
    from pymatgen.symmetry.bandstructure import HighSymmKpath
    kpath = HighSymmKpath(structure)
    return Kpoints.automatic_linemode(divisions=40, ibz=kpath)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    ap = argparse.ArgumentParser(description="VASP workflow runner")
    ap.add_argument("command", choices=["run", "status"])
    ap.add_argument("config", help="Workflow YAML file")
    args = ap.parse_args()

    wf = VaspWorkflow(args.config)
    if args.command == "run":
        wf.run()
    elif args.command == "status":
        wf._load_state()
        wf._print_status()


if __name__ == "__main__":
    main()
