import argparse
import sys
import yaml
import logging
import os

from pathlib import Path
from pydantic import ValidationError
from abvio.io import Input
from rich.console import Console
from rich.table import Table

#set logging level to silent
logging.basicConfig(level=logging.ERROR)

def check_input_file(input_file):
    try:
        Input.from_file(input_file)
    except ValueError:
        print(f"Input file is incorrectly formatted: {input_file}")
        sys.exit(1)
    except ValidationError as e:
        print(f"Input file contains incorrect tags or parameters: {input_file}")
        print(e)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Input file is not valid yaml: {input_file}")
        print(e)
        sys.exit(1)
    except FileNotFoundError:
        print(f"Input file not found: {input_file}")
        sys.exit(1)


def preview(input_file):
    """Uses rich to create a preview of the structure, kpoints, and incar files.

    Args:
        input_file (str): The path to the abvio yaml file.

    Returns:
        rich.table.Table: A table with the structure, kpoints, and incar files.
    """
    table = Table(title="VASP Input Preview")

    input_object = Input.from_file(input_file)
    structure = input_object.structure
    incar = input_object.incar
    kpoints = input_object.kpoints

    table.add_column("Structure")
    table.add_column("INCAR")
    table.add_column("KPOINTS")
    table.add_row(f"{structure}", f"{incar}", f"{kpoints}") 

    return table



def main():
    """
    Create a VASP input set from a YAML file.

    This function parses command line arguments, reads an abvio YAML file, and generates VASP input files based on the
    provided input. It also performs optional checks on the input file for validity.

    Command line arguments:
        input (str | Path): The path to the abvio YAML file or directory.
        -o, --output (str): The path to the output directory or file.
        --check: Perform validity checks on the input file.
        --preview: Preview the input files.
        --convert: Convert VASP input files to abvio format.
        --verbose: Increase output verbosity.
    """
    parser = argparse.ArgumentParser(
        description="Create a VASP input set from a YAML file"
    )
    parser.add_argument("input", type=str, help="The path to the abvio YAML file or directory")
    parser.add_argument(
        "-o", "--output", type=str, help="The path to the output directory or file"
    )
    parser.add_argument(
        "--check", action="store_true", help="Check validity of the input file"
    )
    parser.add_argument(
        "--preview", action="store_true", help="Preview the input files"
    )
    parser.add_argument(
        "--convert", action="store_true", help="Convert VASP input files to abvio format"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Increase output verbosity"
    )
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    user_input = args.input
    output_path = args.output

    if args.check:
        check_input_file(user_input)

    if args.preview:
        Console().print(preview(user_input), markup=False)

    if args.output and not args.convert:
        if not os.path.exists(output_path):
            logging.error(f"Output path '{output_path}' does not exist.")
            sys.exit(1)
        input_object = Input.from_file(user_input)
        input_object.write_inputs(output_path)

    if args.convert:

        input_object = Input.from_vaspset(user_input)
        input_object.write_file(output_path)



if __name__ == "__main__":
    main()
