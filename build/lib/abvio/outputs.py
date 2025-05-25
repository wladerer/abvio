import argparse
import sys
import yaml
import os

from pymatgen.io.vasp import Vasprun

def extract_vasprun_summary(vasprun_path, output_yaml_path=None):
    v = Vasprun(vasprun_path, parse_dos=False, parse_eigen=False, exception_on_bad_xml=False, parse_potcar_file=False)
    summary = {
        "converged": v.converged,
        "converged_electronic": v.converged_electronic,
        "converged_ionic": v.converged_ionic,
        "run_type": str(v.run_type),
        "nionic_steps": v.nionic_steps,
        "efermi": v.efermi,
        "final_energy": v.final_energy,
        "final_free_energy": v.final_free_energy,
        "magnetization": [m['tot'] for m in v.magnetization] if v.magnetization else None,
        "initial_magnetic_moments": v.initial_magmoms,
        "potcar_symbols": v.potcar_symbols,
        "ldauu": v.ldauu,
        "ldauj": v.ldauj,
        "ldautype": v.ldautype,
    }

    if output_yaml_path:
        with open(output_yaml_path, 'w') as f:
            yaml.dump(summary, f, sort_keys=False, default_flow_style=False)

    return summary


def main():
    """
    Create a VASP input set from a YAML file.

    This function parses command line arguments, reads an abvio YAML file, and generates VASP input files based on the
    provided input. It also performs optional checks on the input file for validity.

    Command line arguments:
        input (str | Path): The path to the VASP output directory
        -o, --output (str): The path to file.
    """
    parser = argparse.ArgumentParser(
        description="Create a VASP input set from a YAML file"
    )
    parser.add_argument(
        "input", type=str, help="The path to the VASP output directory"
    )
    parser.add_argument(
        "-o", "--output", type=str, help="The path to the output file"
    )

    args = parser.parse_args()


    user_input = args.input
    
    summary = extract_vasprun_summary(f"{args.input}/vasprun.xml", args.output) 
    if not args.output:
        print(summary)



if __name__ == "__main__":
    main()