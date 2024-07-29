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


def structure_from_lattice(lattice: Lattice | np.ndarray, species: list[str], coords: np.ndarray, cartesian: bool = True) -> Structure:
    """Create a Poscar object from a lattice object, species list, and coordinates array"""
    
    log.debug("Creating structure from lattice array")
    log.debug(f"Lattice: {lattice}")
    log.debug(f"Species: {species}")
    log.debug(f"Coordinates: {coords}")
    log.debug(f"Cartesian: {cartesian}")

    if isinstance(lattice, np.ndarray):
        lattice = Lattice(lattice)
    
    if not isinstance(lattice, Lattice):
        log.error(f"Expected np.ndarray or Lattice object, got {type(lattice)}")
        raise ValueError("Lattice must be a Lattice object or numpy array")

    if len(coords) != len(species):
        log.error(f"Species ({len(species)}) and coordinates ({len(coords)}) are not the same length")
        raise ValueError("Number of species and coordinates must be the same")

    structure = Structure(lattice, species, coords, coords_are_cartesian=cartesian)
    
    return structure


def structure_from_prototype(prototype: dict, species: list[str], cartesian: bool = True) -> Structure:
    """Create a structure from a prototype, lattice object, species list, and coordinates array"""

    log.debug("Creating structure from prototype")
    log.debug(f"Prototype: {prototype}")
    log.debug(f"Species: {species}")
    log.debug(f"Cartesian: {cartesian}")

    prototype_string, prototype_parameter = next(iter(prototype.items()))
    structure = Structure.from_prototype(prototype_string, species, a=prototype_parameter)
    
    return structure

