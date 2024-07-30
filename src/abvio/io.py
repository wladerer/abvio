import logging
import yaml
import os

from pathlib import Path
from pydantic import BaseModel, field_validator

from pymatgen.core import Structure
from pymatgen.io.vasp import Incar, Kpoints, Poscar

from abvio.structure import structure_model_from_input_dict
from abvio.kpoints import kpoints_model_from_dictionary
from abvio.incar import IncarModel

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

    with open(filepath, "r") as f:
        input_dictionary = yaml.safe_load(f)

    return input_dictionary


class Input:

    def __init__(self, input_dictionary: dict):
        self.input_dict = input_dictionary
        self.structure_dict = input_dictionary.get("structure")
        self.incar_dict = input_dictionary.get("incar")
        self.kpoints_dict = input_dictionary.get("kpoints")

    @property
    def structure(self) -> Structure:
        
        structure_model = structure_model_from_input_dict(self.structure_dict)
        structure = structure_model.structure

        return structure

    @property
    def incar(self) -> Incar:
        
        incar_model = IncarModel(incar_dict=self.incar_dict)
        incar = incar_model.incar(self.structure)

        return incar

    @property
    def kpoints(self) -> Kpoints:

        kpoints_model = kpoints_model_from_dictionary(self.kpoints_dict)
        kpoints = kpoints_model.kpoints
        
        return kpoints


