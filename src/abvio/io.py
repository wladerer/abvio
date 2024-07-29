import logging 
import yaml 
import os 

import numpy as np

from pathlib import Path
from pymatgen.core import Structure, Lattice
from pymatgen.io.vasp import Poscar

log = logging.getLogger(__name__)
log_format = "%(asctime)s - %(levelname)s - %(message)s"
date_format = "%Y-%m-%d"

logging.basicConfig(level=logging.INFO, format=log_format, datefmt=date_format)


def load(filepath: Path | str) -> dict:
    """Loads the abvio yaml file into a dictionary

    Args:
        filepath: The path to the abvio yaml file

    Returns:
        dict: The dictionary containing vasp input information
    """

    log.debug(f"Loading file: {filepath}")

    if not os.path.exists(filepath):
        log.error(f"File does not exist: {filepath}")
        raise FileNotFoundError(f"File does not exist: {filepath}")

    with open(filepath, 'r') as f:
        return yaml.safe_load(f)


def format_species(species: list[dict] | list[str]) -> list[str]:
    """Formats the species list

    Species list can either be 
    - A list of dictionaries where each dictionary contains the species and count
    - A list of strings where each string is the species

    Args:
        species: The list of species

    Returns:
        list: The formatted list of species
    """

    log.debug("Formatting species list")
    log.debug(f"Species is of type: {type(species)}")

    if not isinstance(species, list):
        log.error(f"Species is of type: {type(species)}")
        raise ValueError("Species must be a list")
    
    if isinstance(species[0], dict):
        #check if keys are strings and values are integers
        for species_dict in species:
            if not all(isinstance(key, str) for key in species_dict.keys()):
                log.error(f"Keys in species dictionary are not strings: {species_dict.keys()}")
                raise ValueError("Keys in species dictionary must be strings")
            
            if not all(isinstance(value, int) for value in species_dict.values()):
                log.error(f"Values in species dictionary are not integers: {species_dict.values()}")
                raise ValueError("Values in species dictionary must be integers")


    if isinstance(species[0], dict):

        formatted_species_list = []
        for species_dict in species:
            species_str, species_count = next(iter(species_dict.items()))
            formatted_species_list.extend([species_str] * species_count)
        
        return formatted_species_list

    if isinstance(species, list) and isinstance(species[0], str):
        return species


    else:
        log.error(f"Species is of type: {type(species)}")
        raise ValueError("Species must be a list of dictionaries or a list of strings")


def format_poscar_info(input_structure_dictionary: dict) -> dict:
    """Formats the dictionary containing the POSCAR information

    Converts lattice and coords to a numpy array

    Args:
        input_structure_dictionary: The dictionary containing the POSCAR information

    Returns:
        dict: The dictionary containing the formatted POSCAR information
    """

    log.debug("Formatting POSCAR information")

    if 'lattice' in input_structure_dictionary:
        if isinstance(input_structure_dictionary['lattice'], list):
            input_structure_dictionary['lattice'] = np.array(input_structure_dictionary['lattice'])
        if isinstance(input_structure_dictionary['lattice'], dict):
            input_structure_dictionary['lattice'] = Lattice.from_dict(input_structure_dictionary['lattice']).matrix

    if 'coords' in input_structure_dictionary:
        input_structure_dictionary['coords'] = np.array(input_structure_dictionary['coords'])

    if 'species' in input_structure_dictionary:
        input_structure_dictionary['species'] = format_species(input_structure_dictionary['species'])

    return input_structure_dictionary


def read(filepath: Path | str) -> dict:
    """Reads an abvio yaml file and returns a formatted dictionary

    Args:
        filepath: The path to the abvio yaml file

    Returns:
        dict: The dictionary containing the formatted input file information
    """

    log.debug(f"Reading file: {filepath}")
    input_dictionary = load(filepath)

    structure_dictionary = input_dictionary['poscar']
    formatted_structure_dictionary = format_poscar_info(structure_dictionary)


    # update the dictionary with the formatted structure information
    input_dictionary['poscar'] = formatted_structure_dictionary

    return input_dictionary





