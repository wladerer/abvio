import argparse
import os
import yaml
import getpass
import platform
import socket
from datetime import datetime, timezone
from abvio.aio import format_structure_output
from pymatgen.io.vasp import Vasprun, Outcar
from typing import Optional, Dict, Any

def extract_vasprun_summary(vasprun_path: str) -> Optional[Dict[str, Any]]:
    try:
        v = Vasprun(
            vasprun_path,
            parse_dos=False,
            parse_eigen=False,
            exception_on_bad_xml=False,
            parse_potcar_file=False,
        )
        summary = {
            "converged": v.converged,
            "converged_electronic": v.converged_electronic,
            "converged_ionic": v.converged_ionic,
            "final_energy": float(v.final_energy) if v.final_energy is not None else None,  # Convert to plain float
            "run_type": str(v.run_type) if v.run_type is not None else None,
            "nionic_steps": v.nionic_steps,
            "efermi": float(v.efermi) if v.efermi is not None else None,
            "spin": v.is_spin,
            "potcar_symbols": v.potcar_symbols,
            "incar": v.incar.as_dict(),
            "final_structure": format_structure_output(v.final_structure) if v.final_structure is not None else None,
        }
        return summary

    except Exception as e:
        print(f"Error parsing vasprun.xml: {e}")
        return None

def extract_outcar_summary(outcar_path: str) -> dict:
    outcar = Outcar(outcar_path)
    summary = {
        "run_stats": outcar.run_stats if outcar.run_stats is not None else None,
        "free_energy": float(outcar.final_fr_energy) if outcar.final_fr_energy is not None else None,
        "nelect": float(outcar.nelect) if outcar.nelect is not None else None,
        "magnetization": float(outcar.total_mag) if outcar.total_mag is not None else None,
    }
    return summary

def main():
    parser = argparse.ArgumentParser(description="Summarize VASP outputs to YAML")
    parser.add_argument("input", type=str, help="Path to the VASP output directory")
    parser.add_argument("-o", "--output", type=str, help="Path to the output YAML file")
    parser.add_argument("-m", "--message", type=str, help="Optional note or message")
    parser.add_argument("-t", "--tags", nargs="*", help="Optional tags to annotate the calculation (e.g., slab 111 soc)")
    args = parser.parse_args()

    metadata = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hostname": socket.gethostname(),
        "user": getpass.getuser(),
        "platform": platform.platform(),
        "current_directory": os.getcwd()
    }

    if args.message:
        metadata["note"] = args.message

    if args.tags:
        metadata["tags"] = args.tags

    output_data = {"metadata": metadata}

    output_dir = args.input
    vasprun_path = os.path.join(output_dir, "vasprun.xml")
    outcar_path = os.path.join(output_dir, "OUTCAR")

    if os.path.isfile(vasprun_path):
        output_data["vasprun"] = extract_vasprun_summary(vasprun_path)
    else:
        print("Warning: vasprun.xml not found")

    if os.path.isfile(outcar_path):
        output_data["outcar"] = extract_outcar_summary(outcar_path)
    else:
        print("Warning: OUTCAR not found")

    if args.output:
        with open(args.output, "w") as f:
            yaml.dump(output_data, f, sort_keys=False, default_flow_style=False)
    else:
        print(yaml.dump(output_data, sort_keys=False, default_flow_style=False))

if __name__ == "__main__":
    main()
