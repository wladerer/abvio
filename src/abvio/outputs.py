#!/usr/bin/env python3
import argparse
import json
import logging
import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from numpy import log
from pymatgen.io.vasp import Vasprun
from pymatgen.core import Structure


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def surface_area(structure: Structure) -> float:
    """Approximate surface area of a structure from a and b lattice vectors."""
    return structure.lattice.a * structure.lattice.b


def parse_vasprun(vasprun_path: Path) -> Dict[str, Any]:
    """Parse vasprun.xml file and extract summary data."""
    vasprun = Vasprun(
        vasprun_path,
        exception_on_bad_xml=False,
        parse_potcar_file=False,
        parse_projected_eigen=False,
        parse_eigen=False,
    )

    final_structure: Structure = vasprun.final_structure
    composition: str = final_structure.composition.formula

    return {
        "composition": composition,
        "energy": vasprun.final_energy,
        "structure": final_structure.as_dict(),
        "surface_area": surface_area(final_structure),
        "incar": vasprun.incar.as_dict(),
        "kpoints": vasprun.kpoints.as_dict(),
        "converged": vasprun.converged,
        "converged_electronic": vasprun.converged_electronic,
        "converged_ionic": vasprun.converged_ionic,
    }


def get_file_metadata(file_path: Path) -> Dict[str, Any]:
    """Get basic metadata for a file."""
    return {
        "path": str(file_path.resolve()),
        "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
        "created": datetime.fromtimestamp(file_path.stat().st_ctime).isoformat(),
    }


def get_unique_id(data: Dict[str, Any]) -> str:
    """Generate a unique id for a job dictionary."""
    core = {
        "composition": data.get("composition"),
        "energy": data.get("energy"),
        "path": data.get("path"),
    }
    return hashlib.sha256(json.dumps(core, sort_keys=True).encode()).hexdigest()


def parse_vasp_job(directory_path: Path) -> Dict[str, Any]:
    """Parse a VASP job directory for vasprun.xml data + metadata."""
    vasprun_path = directory_path / "vasprun.xml"
    if not vasprun_path.exists():
        raise FileNotFoundError(f"No vasprun.xml found in {directory_path}")

    logger.info(f"Parsing {vasprun_path}")
    file_metadata = get_file_metadata(vasprun_path)
    vasprun_data = parse_vasprun(vasprun_path)

    job = {**file_metadata, **vasprun_data}
    job["id"] = get_unique_id(job)
    return job


def init_sqlite(db_path: Path, overwrite: bool = False):
    """Initialize or open an SQLite database for storing jobs."""
    if db_path.exists() and overwrite:
        logger.warning(f"Overwriting existing database at {db_path}")
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        composition TEXT,
        energy REAL,
        surface_area REAL,
        converged INTEGER,
        converged_electronic INTEGER,
        converged_ionic INTEGER,
        modified TEXT,
        created TEXT,
        path TEXT,
        incar TEXT,
        kpoints TEXT,
        structure TEXT
    )
    """)
    conn.commit()
    return conn


def insert_job(conn, job: Dict[str, Any]):
    """Insert or update a job record in the database."""
    cursor = conn.cursor()
    cursor.execute(
        """
    INSERT OR REPLACE INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            job["id"],
            job["composition"],
            job["energy"],
            job["surface_area"],
            int(job["converged"]),
            int(job["converged_electronic"]),
            int(job["converged_ionic"]),
            job["modified"],
            job["created"],
            job["path"],
            json.dumps(job["incar"]),
            json.dumps(job["kpoints"]),
            json.dumps(job["structure"]),
        ),
    )
    conn.commit()


def get_paths_from_db(conn) -> set[str]:
    """Return a set of all job directory paths currently in the database."""
    cursor = conn.cursor()
    cursor.execute("SELECT path FROM jobs")
    return {Path(row[0]).resolve().as_posix() for row in cursor.fetchall()}


def main():
    parser = argparse.ArgumentParser(
        description="Summarize VASP jobs into an SQLite database."
    )
    parser.add_argument(
        "directories", nargs="+", help="List of VASP job directories to parse"
    )
    parser.add_argument(
        "-o", "--output", default="vasp_summary.sqlite", help="SQLite database file"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing database file if it exists",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--force", action="store_true", help="Force parsing even if already in database"
    )
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    conn = init_sqlite(Path(args.output), overwrite=args.overwrite)

    # get a list of all paths in the database
    paths = get_paths_from_db(conn)
    logger.debug(f"Paths in database: {paths}")

    parsed = 0
    for d in args.directories:
        directory = Path(d).resolve()
        logger.debug(f"Parsing {directory}")
        try:
            normalized_dir = directory.resolve().as_posix()
            if not args.force and normalized_dir in paths:
                logger.info(f"Skipping {directory} (already in database)")
                continue

            job = parse_vasp_job(directory)
            insert_job(conn, job)
            parsed += 1

        except Exception as e:
            logger.error(f"Failed to parse {directory}: {e}")

    conn.close()
    logger.info(f"Saved {parsed} jobs into SQLite database at {args.output}")


if __name__ == "__main__":
    main()
