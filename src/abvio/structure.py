from pymatgen.io.vasp import Poscar
from pymatgen.core import Structure, Lattice
from pydantic import BaseModel, field_validator, model_validator
from pydantic._internal._model_construction import ModelMetaclass
from typing import List, Union, Tuple
from pathlib import Path

import numpy as np
import os


manual_set = ["lattice", "species", "coords"]
external_set = ["file", "string", "code"]
prototype_set = ["species", "prototype"]

Number = Union[int, float]
ArrayLike = List[Tuple[Number, Number, Number]]


def is_valid_poscar_file(filepath: Path | str) -> bool:
    """Checks if the file is a valid POSCAR file

    Args:
        filepath: The path to the file

    Returns:
        bool: True if file is a valid POSCAR file
    """


    try:
        Poscar.from_file(filepath)
        return True
    except Exception:
        return False


def is_valid_poscar_string(poscar_string: str) -> bool:
    """Checks if the string is a valid POSCAR string

    Args:
        poscar_string: The POSCAR string

    Returns:
        bool: True if string is a valid POSCAR string
    """


    try:
        Poscar.from_str(poscar_string)
        return True
    except Exception as e:
        return False


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


    if not isinstance(species, list):
        raise ValueError("Species must be a list")

    if isinstance(species[0], dict):
        # check if keys are strings and values are integers
        for species_dict in species:
            if not all(isinstance(key, str) for key in species_dict.keys()):
                raise ValueError("Keys in species dictionary must be strings")

            if not all(isinstance(value, int) for value in species_dict.values()):
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
        raise ValueError("Species must be a list of dictionaries or a list of strings")


def structure_from_mpi_code(mpcode: str, is_conventional: bool = True):
    """
    Creates a pymatgen structure from a code
    """
    from mp_api.client import MPRester

    api_key = os.getenv("MP_API_KEY")

    with MPRester(api_key, mute_progress_bars=True) as mpr:
        structure = mpr.get_structure_by_material_id(
            mpcode, conventional_unit_cell=is_conventional
        )

    if structure is None:
        raise ValueError(f"Could not find structure with code {mpcode}")

    return structure


def structure_from_lattice(
    lattice: Lattice | ArrayLike,
    species: list[str],
    coords: ArrayLike,
    cartesian: bool = True,
) -> Structure:
    """Create a Poscar object from a lattice object, species list, and coordinates array"""


    if isinstance(lattice, (list, np.ndarray)):
        lattice = Lattice(lattice)

    if not isinstance(lattice, Lattice):
        raise ValueError("Lattice must be a Lattice object or array")

    if len(coords) != len(species):
        raise ValueError(
            f"Number of species {len(species)} and coordinates {len(coords)} must be the same"
        )

    return Structure(lattice, species, coords, coords_are_cartesian=cartesian)


def structure_from_prototype(
    prototype: str, lattice: dict, species: list[str], cartesian: bool = True
) -> Structure:
    """Create a structure from a prototype, lattice object, species list, and coordinates array"""


    if isinstance(lattice, Lattice):
        lattice = {
            "a": lattice.a,
            "b": lattice.b,
            "c": lattice.c,
            "alpha": lattice.alpha,
            "beta": lattice.beta,
            "gamma": lattice.gamma,
        }

    if isinstance(lattice, (list, np.ndarray)):
        lattice = Lattice(lattice)
        lattice = {
            "a": lattice.a,
            "b": lattice.b,
            "c": lattice.c,
            "alpha": lattice.alpha,
            "beta": lattice.beta,
            "gamma": lattice.gamma,
        }

    return Structure.from_prototype(prototype, species, **lattice)


def structure_from_file(file: Path | str) -> Structure:
    """Creates a pymatgen Structure object from a file containing structure information

    Args:

        file (Path | str): The path to the file containing the structure information

    Returns:

            Structure: The pymatgen Structure object created from the file
    """


    return Structure.from_file(file)


def structure_from_string(string: str) -> Structure:
    """Creates a pymatgen Structure object from a string containing structure information

    Args:

        string (str): The string containing the structure information

    Returns:

            Structure: The pymatgen Structure object created from the string
    """


    return Poscar.from_str(string).structure


class StructureMeta(type):
    """Metaclass for the Structure class that combines the BaseModel and StructureMeta metaclasses"""

    _registry = {}

    def __new__(cls, name, bases, class_dict):
        new_class = super().__new__(cls, name, bases, class_dict)
        if "mode" in class_dict:
            StructureMeta._registry[class_dict["mode"]] = new_class
        return new_class

    @classmethod
    def from_dict(cls, structure_dictionary: dict):
        base_model = BaseStructure.validate(structure_dictionary)
        mode = base_model.mode
        StructureClass = cls._registry.get(mode)

        if StructureClass is None:
            raise ValueError(f"Unknown mode: {mode}")

        return StructureClass.validate(structure_dictionary)


class CombinedMeta(StructureMeta, ModelMetaclass):
    """This is how we combine two metaclasses in Python"""

    pass


class BaseStructure(BaseModel, metaclass=CombinedMeta):
    mode: str

    @field_validator("mode")
    def check_mode(cls, mode) -> str:
        """Tries to handle different cases of the mode string and returns the correct mode

        Args:
            mode (str): The user specified mode of the kpoints

        Returns:
            str: The correct mode of the kpoints
        """

        if mode.lower().startswith("ext"):
            return "external"
        elif mode.lower().startswith("pro"):
            return "prototype"
        elif mode.lower() == "manual":
            return "manual"
        else:
            raise ValueError(f"Invalid mode: {mode}")


class ManualStructure(BaseStructure):
    """Handles validating manual structure input

    Requires lattice, species, and coords
    """

    mode: str = "manual"
    lattice: Lattice | ArrayLike | dict
    coords: ArrayLike
    species: list[str] | list[dict[str, int]]

    @field_validator("species")
    def validate_species(cls, species):
        return format_species(species)

    @field_validator("lattice")
    def validate_lattice(cls, lattice):
        if isinstance(lattice, (list, np.ndarray)):
            lattice = Lattice(lattice)
        elif isinstance(lattice, dict):
            lattice = Lattice.from_dict(lattice)
        return lattice

    @property
    def structure(self) -> Structure:
        """Creates a pymatgen Structure object from the input data"""
        return structure_from_lattice(self.lattice, self.species, self.coords)


class PrototypeStructure(BaseStructure):
    """Pydantic model for prototype structure input

    Must contain species and prototype

    Valid prototypes:
    fcc, bcc, hcp, diamond, rocksalt, perovskite, cscl, fluorite, antifluorite, zincblende
    """

    mode: str = "prototype"
    species: list[str] | list[dict]
    lattice: dict | Lattice | ArrayLike
    prototype: str

    @field_validator("species")
    def validate_species(cls, species):
        return format_species(species)

    @field_validator("prototype")
    def validate_prototype(cls, prototype):
        valid_prototypes = [
            "fcc",
            "bcc",
            "hcp",
            "diamond",
            "rocksalt",
            "perovskite",
            "cscl",
            "fluorite",
            "antifluorite",
            "zincblende",
        ]
        if prototype not in valid_prototypes:
            raise ValueError(f"Prototype '{prototype}' is not implemented")
        return prototype

    @property
    def structure(self) -> Structure:
        """Creates a pymatgen Structure object from the input data"""

        return structure_from_prototype(
            prototype=self.prototype, species=self.species, lattice=self.lattice
        )


class ExternalStructure(BaseStructure):
    """Pydantic model for external structure input

    Must contain either file, string, or code
    """

    mode: str = "external"
    file: Path | str = None
    string: str = None
    code: str = None

    @model_validator(mode="before")
    def check_external(cls, values):
        if not any(values.values()):
            raise ValueError("Must provide either file, string, or code")

        # if sum(bool(values[key]) for key in values) > 1:
        #     raise ValueError("Must provide only one of file, string, or code")
        return values

    @field_validator("file")
    def check_file(cls, file):
        if not is_valid_poscar_file(file):
            raise ValueError(f"Invalid POSCAR file: {file}")
        return file

    @field_validator("string")
    def check_string(cls, string):
        if not is_valid_poscar_string(string):
            raise ValueError("Invalid POSCAR string")
        return string

    @field_validator("code")
    def check_code(cls, code):
        # code is a string that starts with "mp-" and is followed by a number
        if not code.startswith("mp-") or not code[3:].isdigit():
            raise ValueError("Invalid Materials Project code")
        return code

    @property
    def structure(self) -> Structure:
        """Checks to see if file, string, or code is provided and returns a pymatgen Structure object"""

        if self.file and self.string and self.code:
            raise ValueError("Must provide only one of file, string, or code")

        elif self.file:
            struct = structure_from_file(self.file)

        elif self.string:
            struct = structure_from_string(self.string)

        elif self.code:
            struct = structure_from_mpi_code(self.code)

        else:
            raise ValueError("Must provide either file, string, or code")

        return struct


def structure_model_from_input_dict(structure_dictionary: dict) -> Structure:
    """Creates a pymatgen Structure object from a dictionary containing input structure information

    Args:

        structure_dict (dict): The dictionary containing the structure information

    Returns:

            Structure: The pymatgen Structure object created from the dictionary
    """


    base_model = BaseStructure.validate(structure_dictionary)

    mode_model_map = {
        "manual": ManualStructure,
        "prototype": PrototypeStructure,
        "external": ExternalStructure,
    }

    BaseStructureModel = mode_model_map.get(base_model.mode)
    return BaseStructureModel.validate(structure_dictionary)
