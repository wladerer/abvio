from pymatgen.io.vasp import Poscar, Kpoints, Incar
from pymatgen.core import Structure, Lattice

import numpy as np
import yaml 

import os 
from pathlib import Path

import logging

log = logging.getLogger(__name__)
log_format = "%(asctime)s - %(levelname)s - %(message)s"
date_format = "%Y-%m-%d"

logging.basicConfig(level=logging.INFO, format=log_format, datefmt=date_format)

def is_valid_poscar_file(filepath: Path | str) -> bool:
    """Checks if the file is a valid POSCAR file

    Args:
        filepath: The path to the file

    Returns:
        bool: True if file is a valid POSCAR file
    """

    log.debug(f"Checking if file is a valid POSCAR file: {filepath}")

    if not os.path.exists(filepath):
        log.error(f"File does not exist: {filepath}")
        raise FileNotFoundError(f"File does not exist: {filepath}")

    try:
        poscar = Poscar.from_file(filepath)
        return True
    except Exception as e:
        return False


def is_valid_poscar_string(poscar_string: str) -> bool:
    """Checks if the string is a valid POSCAR string

    Args:
        poscar_string: The POSCAR string

    Returns:
        bool: True if string is a valid POSCAR string
    """

    log.debug("Checking if string is a valid POSCAR string")

    try:
        poscar = Poscar.from_string(poscar_string)
        return True
    except Exception as e:
        return False


def is_valid_mp_code(code: str | int) -> bool:
    """Checks if the materials project code is valid

    Args:
        mp_code: The materials project code

    Returns:
        bool: True if materials project code is valid
    """

    log.debug(f"Checking if materials project code {code} is valid")

    #checks if code contains either mp-(integer) or simply (integer)
    if not any([code.startswith("mp-"), code.isdigit()]):
        return False

    return True



def validate_internal_mode(structure_input_set: dict) -> bool:
    """Validates if all requisite information is present in the structure input set to construct a structure object
    
    Args:
        structure_input_set: A dictionary containing the structure input set

    Returns:
        bool: True if structure_input_set contains all necessary information
    """

    log.debug(f"Validating internal mode for structure input set: {structure_input_set}")

    manual_set  = ["lattice", "species", "coords"]
    prototype_set = ["lattice", "species", "prototype"] 

    # must contain one of the two sets, but not both

    if all(key in structure_input_set for key in manual_set) and all(key in structure_input_set for key in prototype_set):
        log.error("Structure input set contains both manual and prototype information")
        raise ValueError("Structure input set must contain either manual or prototype information, not both")

    if not any(key in structure_input_set for key in manual_set) and not any(key in structure_input_set for key in prototype_set):
        log.error("Structure input set contains neither manual nor prototype information")
        raise ValueError("Structure input set must contain either manual or prototype information")

    if any(key in structure_input_set for key in manual_set):
        if not all(key in structure_input_set for key in manual_set):
            log.error("Structure input set missing manual information")
            raise ValueError("Structure input set must contain lattice, species, and coords")

    if any(key in structure_input_set for key in prototype_set):
        if not all(key in structure_input_set for key in prototype_set):
            log.error("Structure input set missing prototype information")
            raise ValueError("Structure input set must contain lattice, species, and prototype")

    return True


def validate_external_mode(structure_input_set: dict) -> bool:
    """Validates if user has given a valid file, string, or materials project code
    
    Args:
        structure_input_set: A dictionary containing the structure input set
    
    Returns:
        bool: True if structure_input_set contains all necessary information

    Raises:
        ValueError: If structure_input_set does not contain file, string, or materials project code
    """

    log.debug(f"Validating external mode for structure input set: {structure_input_set}")

    if not any(key in structure_input_set for key in ["file", "string", "code"]):
        log.error("Structure input set missing external information")
        raise ValueError("Structure input set must contain either file, string, or mp_code")
    
    if "file" in structure_input_set:
        if not is_valid_poscar_file(structure_input_set["file"]):
            log.error("Invalid POSCAR file")
            raise ValueError(f"Invalid POSCAR file {structure_input_set['file']}")

    if "string" in structure_input_set:
        if not is_valid_poscar_string(structure_input_set["string"]):
            log.error("Invalid POSCAR string")
            raise ValueError("Invalid POSCAR string")

    if "code" in structure_input_set:
        if not is_valid_mp_code(structure_input_set["code"]):
            log.error(f"Invalid materials project code {structure_input_set['code']}")
            raise ValueError(f"Invalid materials project code {structure_input_set['code']}")

    return True