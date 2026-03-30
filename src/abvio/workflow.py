"""
VASP workflow orchestrator using Parsl for HPC execution.

Runs as a persistent job on an HPC login/service node. Builds a DAG of
Parsl futures, submits each step to Slurm via HighThroughputExecutor, and
advances the workflow graph as futures resolve.

Usage
-----
    abflow run mxenes.yaml
    abflow status mxenes.yaml

Workflow YAML format
--------------------
    name: v4c3_pv
    root: /p/work1/wladerer/mxenes_pv
    poll_interval: 60          # seconds between progress checks (default 60)

    slurm:                     # SLURM directives forwarded to Parsl SlurmProvider
      nodes: 1
      ntasks: 128
      time: "12:00:00"
      queue: standard          # -q flag; omit if using partition instead
      partition: gpu           # --partition; omit if using queue instead
      vasp_cmd: mpirun vasp_std
      modules:                 # loaded on compute nodes before VASP
        - VASP/6.4.2
      env:                     # exported on compute nodes
        OMP_NUM_THREADS: 1
      extra:                   # raw #SBATCH lines
        - "--constraint=knl"

    potcar_map:
      V: V_pv
      C: C

    steps:
      - name: relax
        type: relax
        structure: /path/to/structure.vasp

      - name: scf
        type: scf
        depends: relax

      - name: bands
        type: bands
        depends: scf
"""

from __future__ import annotations

import concurrent.futures as cf
import json
import logging
import subprocess
import time
from enum import Enum
from pathlib import Path
from typing import Any

import parsl
import yaml
from parsl.app.app import python_app
from parsl.config import Config
from parsl.executors import HighThroughputExecutor
from parsl.launchers import SrunLauncher
from parsl.providers import SlurmProvider

from abvio.steps import PREP_FUNCTIONS, check_convergence, step_info

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# State
# ─────────────────────────────────────────────────────────────────────────────

class State(str, Enum):
    PENDING = "pending"   # waiting for dependencies
    RUNNING = "running"   # submitted to Parsl / in queue or executing
    DONE    = "done"      # finished + converged
    FAILED  = "failed"    # finished but not converged, or error


# ─────────────────────────────────────────────────────────────────────────────
# Parsl configuration
# ─────────────────────────────────────────────────────────────────────────────

def make_parsl_config(slurm_cfg: dict, run_dir: str | Path) -> Config:
    """Build a Parsl Config with a SlurmProvider from the workflow slurm_cfg."""
    scheduler_options = ""
    if "account" in slurm_cfg:
        scheduler_options += f"#SBATCH --account={slurm_cfg['account']}\n"
    if "queue" in slurm_cfg:
        scheduler_options += f"#SBATCH -q {slurm_cfg['queue']}\n"
    if "partition" in slurm_cfg:
        scheduler_options += f"#SBATCH --partition={slurm_cfg['partition']}\n"
    for extra in slurm_cfg.get("extra", []):
        scheduler_options += f"#SBATCH {extra}\n"

    worker_init_lines = []
    for mod in slurm_cfg.get("modules", []):
        worker_init_lines.append(f"module load {mod}")
    for key, val in slurm_cfg.get("env", {}).items():
        worker_init_lines.append(f"export {key}={val}")
    if "worker_init" in slurm_cfg:
        worker_init_lines.insert(0, slurm_cfg["worker_init"])
    worker_init = "\n".join(worker_init_lines)

    provider = SlurmProvider(
        nodes_per_block=slurm_cfg.get("nodes", 1),
        cores_per_node=slurm_cfg.get("ntasks", 128),
        walltime=slurm_cfg.get("time", "12:00:00"),
        scheduler_options=scheduler_options,
        worker_init=worker_init,
        max_blocks=slurm_cfg.get("max_jobs", 8),
        launcher=SrunLauncher(),
    )

    return Config(
        executors=[
            HighThroughputExecutor(
                label="vasp_htex",
                max_workers_per_node=1,
                provider=provider,
            )
        ],
        run_dir=str(run_dir),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Parsl app
# ─────────────────────────────────────────────────────────────────────────────

@python_app
def run_step(
    step_name: str,
    step_type: str,
    step_cfg: dict,
    step_dir: str,
    prev_dir: str | None,
    potcar_map: dict,
    vasp_cmd: str,
    inputs: list = [],
) -> bool:
    """Prepare VASP inputs and run VASP. Executes on a Parsl compute worker.

    Returns True if converged, False if not. Raises on prep or execution error.
    """
    import subprocess
    import logging
    import subprocess
    from pathlib import Path
    from abvio.steps import PREP_FUNCTIONS, check_convergence, step_info

    _log = logging.getLogger(__name__)
    dst  = Path(step_dir)
    prev = Path(prev_dir) if prev_dir else None

    prep_fn = PREP_FUNCTIONS.get(step_type)
    if prep_fn is None:
        raise ValueError(f"Unknown step type: {step_type!r}")

    prep_fn(dst, step_cfg, prev, potcar_map)
    _log.info(f"[{step_name}] inputs written, launching VASP")

    result = subprocess.run(vasp_cmd.split(), cwd=str(dst),
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"VASP failed in {step_dir} (exit {result.returncode}):\n{result.stderr}"
        )

    converged = check_convergence(dst)

    # Log convergence summary without loading vasprun.xml
    info = step_info(dst)
    e_str   = f"{info.final_energy:.4f} eV" if info.final_energy is not None else "n/a"
    scf_str = "yes" if info.electronic_converged else ("no" if info.electronic_converged is False else "?")
    ion_str = ("yes" if info.ionic_converged
               else ("no" if info.ionic_converged is False
                     else f"{info.n_ionic_steps} steps" if info.n_ionic_steps else "n/a"))
    _log.info(
        f"[{step_name}] done | electronic: {scf_str} | ionic: {ion_str} | "
        f"E={e_str} | converged={converged}"
    )

    return converged


# ─────────────────────────────────────────────────────────────────────────────
# Daemon submit script (for the abflow daemon job itself)
# ─────────────────────────────────────────────────────────────────────────────

_USER_SLURM_CFG = Path.home() / ".config" / "abvio" / "config.yaml"


def _load_user_slurm_cfg() -> dict:
    """Load ~/.config/abvio/config.yaml if it exists; silently return {} otherwise."""
    if _USER_SLURM_CFG.exists():
        with open(_USER_SLURM_CFG) as f:
            return yaml.safe_load(f) or {}
    return {}


def _make_submit_script(directory: Path, slurm_cfg: dict) -> str:
    """Generate a Slurm batch script for the abflow daemon job."""
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
# Workflow
# ─────────────────────────────────────────────────────────────────────────────

class WorkflowStep:
    def __init__(self, cfg: dict, root: Path, workspace: Path):
        self.name    = cfg["name"]
        self.type    = cfg["type"]
        self.cfg     = cfg
        self.depends = cfg.get("depends")
        self.dir     = workspace / cfg.get("dir", cfg["name"])
        self.state   = State.PENDING
        self.job_id  = None   # unused with Parsl; kept for JSON schema compatibility

    def to_dict(self) -> dict:
        return {"name": self.name, "state": self.state.value,
                "job_id": self.job_id, "dir": str(self.dir)}


class VaspWorkflow:
    STATE_FILE = "workflow_state.json"

    def __init__(self, config_path: str | Path):
        with open(config_path) as f:
            self.cfg = yaml.safe_load(f)

        self.name          = self.cfg["name"]
        self.root          = Path(self.cfg["root"])
        self.workspace     = self.root / self.cfg.get("workspace", "workspace")
        self.slurm_cfg     = {**self.cfg.get("slurm", {}), **_load_user_slurm_cfg()}
        self.potcar_map    = self.cfg.get("potcar_map", {})
        self.poll_interval = self.cfg.get("poll_interval", 60)

        self.steps: dict[str, WorkflowStep] = {}
        for step_cfg in self.cfg["steps"]:
            step = WorkflowStep(step_cfg, self.root, self.workspace)
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

    # ── DAG construction ──────────────────────────────────────────────────────

    def _build_dag(self) -> dict[str, cf.Future]:
        """Submit all pending steps to Parsl. Returns a name→future mapping."""
        futures: dict[str, cf.Future] = {}

        # Reset previously-failed steps so they are retried this run.
        for step in self.steps.values():
            if step.state == State.FAILED:
                step.state = State.PENDING

        for step in self.steps.values():
            if step.state == State.DONE:
                # Already done from a previous run — provide a resolved sentinel.
                fut: cf.Future = cf.Future()
                fut.set_result(True)
                futures[step.name] = fut
                continue

            parent      = self._parent(step)
            dep_futures = [futures[parent.name]] if parent else []
            prev_dir    = str(parent.dir) if parent else None

            futures[step.name] = run_step(
                step_name=step.name,
                step_type=step.type,
                step_cfg=step.cfg,
                step_dir=str(step.dir),
                prev_dir=prev_dir,
                potcar_map=self.potcar_map,
                vasp_cmd=self.slurm_cfg.get("vasp_cmd", "mpirun vasp_std"),
                inputs=dep_futures,
            )
            step.state = State.RUNNING

        return futures

    # ── monitoring ────────────────────────────────────────────────────────────

    def _monitor(self, futures: dict[str, cf.Future]) -> None:
        """Poll futures until all complete, updating step states as they finish."""
        # Only monitor steps that were actually submitted this run.
        active = {
            name: fut for name, fut in futures.items()
            if self.steps[name].state == State.RUNNING
        }
        reverse = {id(fut): name for name, fut in active.items()}

        for completed in cf.as_completed(list(active.values())):
            name = reverse[id(completed)]
            step = self.steps[name]
            try:
                converged = completed.result()
                step.state = State.DONE if converged else State.FAILED
                log.info(f"[{'DONE' if converged else 'NOT CONVERGED'}] {name}")
            except Exception as e:
                step.state = State.FAILED
                log.error(f"[FAILED] {name}: {e}")
            self._save_state()

    # ── run ───────────────────────────────────────────────────────────────────

    def run(self) -> None:
        log.info(f"Starting workflow '{self.name}'")
        cfg = make_parsl_config(self.slurm_cfg,
                                run_dir=self.root / "parsl_runinfo")
        parsl.load(cfg)
        try:
            futures = self._build_dag()
            self._save_state()
            self._monitor(futures)
        finally:
            parsl.clear()
        self._print_status()

    # ── status display ────────────────────────────────────────────────────────

    def _print_status(self):
        print(f"\nWorkflow: {self.name}")
        print(f"{'Step':<30} {'Type':<18} {'State'}")
        print("-" * 60)
        for step in self.steps.values():
            print(f"{step.name:<30} {step.type:<18} {step.state.value}")

    def _print_monitor(self):
        from datetime import datetime
        from rich.console import Console
        from rich.table import Table

        table = Table(title=f"Workflow: {self.name}  [{datetime.now().strftime('%H:%M:%S')}]")
        table.add_column("Step",       style="bold")
        table.add_column("Type",       style="dim")
        table.add_column("State")
        table.add_column("Electronic", justify="center")
        table.add_column("Ionic",      justify="center")
        table.add_column("Ion. Steps", justify="right")
        table.add_column("Energy (eV)", justify="right")
        table.add_column("dE (eV)",    justify="right")

        STATE_STYLE = {
            State.PENDING: "dim",
            State.RUNNING: "yellow",
            State.DONE:    "green",
            State.FAILED:  "red bold",
        }

        for step in self.steps.values():
            style    = STATE_STYLE.get(step.state, "")
            state_s  = f"[{style}]{step.state.value}[/{style}]"

            if step.state in (State.PENDING,):
                table.add_row(step.name, step.type, state_s, "-", "-", "-", "-", "-")
                continue

            info = step_info(step.dir)

            if not info.available:
                table.add_row(step.name, step.type, state_s, "-", "-", "-", "-", "-")
                continue

            scf = ("✓" if info.electronic_converged
                   else ("✗" if info.electronic_converged is False
                         else f"iter {info.current_scf_iter}"))
            ion = ("✓" if info.ionic_converged
                   else ("✗" if info.ionic_converged is False
                         else ("n/a" if info.n_ionic_steps <= 1 else f"{info.n_ionic_steps}")))
            n_ion = str(info.n_ionic_steps) if info.n_ionic_steps else "-"
            energy = f"{info.final_energy:.5f}" if info.final_energy is not None else "-"
            de     = (f"{info.energy_change:+.5f}" if info.energy_change is not None
                      else "-")

            table.add_row(step.name, step.type, state_s, scf, ion, n_ion, energy, de)

        Console().print(table)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    import argparse
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    ap = argparse.ArgumentParser(description="VASP workflow runner")
    ap.add_argument("command", choices=["run", "status", "monitor"])
    ap.add_argument("config", help="Workflow YAML file")
    ap.add_argument("--watch", type=int, metavar="SECONDS",
                    help="Re-print monitor table every N seconds (monitor only)")
    args = ap.parse_args()

    wf = VaspWorkflow(args.config)
    if args.command == "run":
        wf.run()
    elif args.command == "status":
        wf._load_state()
        wf._print_status()
    elif args.command == "monitor":
        wf._load_state()
        if args.watch:
            import time as _time
            try:
                while True:
                    wf._load_state()
                    wf._print_monitor()
                    _time.sleep(args.watch)
            except KeyboardInterrupt:
                pass
        else:
            wf._print_monitor()


if __name__ == "__main__":
    main()
