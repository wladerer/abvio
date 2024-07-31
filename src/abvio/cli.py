import argparse
import sys
import yaml
from rich.console import Console
from rich.table import Table

from pymatgen.symmetry.analyzer import SpacegroupAnalyzer


from pydantic import ValidationError
from abvio.io import Input


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

    # get space group symbol and number for Notes section
    sga = SpacegroupAnalyzer(structure)
    space_group = sga.get_space_group_symbol()
    space_group_number = sga.get_space_group_number()

    notes = (
        f"Space group symbol: {space_group}\nSpace group number ({space_group_number})"
    )

    table.add_column("Structure")
    table.add_column("INCAR")
    table.add_column("KPOINTS")
    table.add_column("Notes")
    table.add_row(f"{structure}", f"{incar}", f"{kpoints}", f"{notes}")

    return table


def main():
    """
    Create a VASP input set from a yaml file.

    This function parses command line arguments, reads an abvio yaml file, and generates VASP input files based on the
    provided input. It also performs optional checks on the input file for validity.

    Command line arguments:
        -i, --input (str): The path to the abvio yaml file.
        -o, --output (str): The path to the output directory.
        --check: Perform validity checks on the input file.

    Returns:
        None
    """
    parser = argparse.ArgumentParser(
        description="Create a VASP input set from a yaml file"
    )
    parser.add_argument("input", type=str, help="The path to the abvio yaml file")
    parser.add_argument(
        "-o", "--output", type=str, help="The path to the output directory"
    )
    parser.add_argument(
        "--check", action="store_true", help="Check validity of input file"
    )
    parser.add_argument(
        "--preview", action="store_true", help="Preview the input files"
    )
    args = parser.parse_args()

    input_file = args.input
    output_directory = args.output

    if args.check:
        check_input_file(input_file)

    if args.preview:
        Console().print(preview(input_file))

    if args.output:
        input_object = Input.from_file(input_file)
        input_object.write_inputs(output_directory)


if __name__ == "__main__":
    main()
