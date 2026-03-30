"""
VASP input preparation and convergence checking.

All functions here are pure (filesystem I/O only) and have no dependency on
Parsl, Slurm, or the workflow orchestrator.
"""

from __future__ import annotations

import logging
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from pymatgen.core import Structure
from pymatgen.io.vasp.inputs import Incar, Kpoints, Poscar, Potcar
from pymatgen.io.vasp.outputs import Vasprun
from pymatgen.io.vasp.sets import VaspInput

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Convergence data
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class StepInfo:
    """Lightweight convergence/progress summary parsed from OSZICAR + OUTCAR."""
    n_ionic_steps: int = 0
    current_scf_iter: int = 0       # > 0 means SCF is actively running
    energies: list[float] = field(default_factory=list)
    electronic_converged: bool | None = None   # None = not yet determined
    ionic_converged: bool | None = None        # None = N/A (SCF/bands) or unknown
    available: bool = False                    # False if no output files found yet

    @property
    def final_energy(self) -> float | None:
        return self.energies[-1] if self.energies else None

    @property
    def energy_change(self) -> float | None:
        """dE between last two ionic steps."""
        if len(self.energies) >= 2:
            return self.energies[-1] - self.energies[-2]
        return None


def parse_oszicar(directory: Path) -> StepInfo:
    """
    Parse OSZICAR for ionic step energies and current SCF progress.
    Fast: reads a small plain-text file, no XML parsing.
    Works on both completed and in-progress calculations.
    """
    path = directory / "OSZICAR"
    if not path.exists():
        return StepInfo()

    info = StepInfo(available=True)
    current_scf = 0

    for line in path.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith(("DAV:", "RMM:")):
            current_scf += 1
        elif re.match(r"\s*\d+\s+F=", line):
            # ionic step line:  "  1 F= -.163E+03 E0= ... d E =..."
            try:
                energy = float(line.split("F=")[1].split()[0])
                info.energies.append(energy)
                info.n_ionic_steps += 1
            except (IndexError, ValueError):
                pass
            current_scf = 0

    info.current_scf_iter = current_scf  # >0 if SCF is running right now
    return info


def parse_outcar_convergence(directory: Path) -> dict[str, bool | None]:
    """
    Scan OUTCAR for convergence markers.
    Returns dict with keys electronic_converged, ionic_converged.
    Reads only the last ~200 lines for speed on large OUTCARs.
    """
    path = directory / "OUTCAR"
    if not path.exists():
        return {"electronic_converged": None, "ionic_converged": None}

    # Read tail only — convergence messages appear at the end
    text = _tail(path, 200)
    return {
        "electronic_converged": "aborting loop because EDIFF is reached" in text,
        "ionic_converged": "reached required accuracy" in text,
    }


def step_info(directory: Path) -> StepInfo:
    """Combined OSZICAR + OUTCAR summary for a step directory."""
    info = parse_oszicar(directory)
    conv = parse_outcar_convergence(directory)
    info.electronic_converged = conv["electronic_converged"]
    info.ionic_converged      = conv["ionic_converged"]
    return info


def _tail(path: Path, n: int) -> str:
    """Return the last n lines of a file as a single string."""
    with open(path, "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        buf  = min(size, n * 120)   # rough estimate: 120 bytes/line
        f.seek(-buf, 2)
        return f.read().decode("utf-8", errors="replace")


# ─────────────────────────────────────────────────────────────────────────────
# Convergence check (used by run_step)
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
    species = list(dict.fromkeys(str(s.specie) for s in structure))
    symbols = [potcar_map.get(sp, sp) for sp in species]
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

KPOINTS_SCF    = Kpoints.gamma_automatic((18, 18, 1))
KPOINTS_BULK   = Kpoints.gamma_automatic((18, 18, 4))
KPOINTS_COARSE = Kpoints.gamma_automatic((9, 9, 1))


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
    structure = Structure.from_file(str(prev / "CONTCAR"))
    write_vasp_input(dst, structure,
                     {"LSORBIT": True, "NBANDS": 64, "SAXIS": [0, 0, 1],
                      "NSW": 0, "LWAVE": False, "LCHARG": False},
                     KPOINTS_SCF, potcar_map)


def prep_adsorption(dst: Path, cfg: dict, prev: Path, potcar_map: dict):
    from tinykit.adsorb import get_molecule, adsorb

    slab       = Structure.from_file(str(prev / "CONTCAR"))
    molecule   = get_molecule(cfg["adsorbate"])
    structures = adsorb(slab, molecule)

    if not structures:
        raise RuntimeError(f"No adsorption sites found for {cfg['adsorbate']}")

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
# phonopy ↔ pymatgen helpers
# ─────────────────────────────────────────────────────────────────────────────

def _pmg_to_phonopy_atoms(structure: Structure):
    from phonopy.structure.atoms import PhonopyAtoms
    return PhonopyAtoms(
        symbols=[str(s.specie) for s in structure],
        cell=structure.lattice.matrix,
        scaled_positions=structure.frac_coords,
    )


def _phonopy_atoms_to_pmg(atoms, ref: Structure) -> Structure:
    from pymatgen.core import Lattice
    lattice = Lattice(atoms.cell)
    return Structure(lattice, atoms.symbols, atoms.scaled_positions)


def _line_kpoints(structure: Structure) -> Kpoints:
    from pymatgen.symmetry.bandstructure import HighSymmKpath
    kpath = HighSymmKpath(structure)
    return Kpoints.automatic_linemode(divisions=40, ibz=kpath)
