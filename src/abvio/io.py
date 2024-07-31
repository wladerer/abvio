import logging
import warnings
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
        
        if self.structure_dict is None:
            raise ValueError(f"No structure dictionary found in input file: keys passed are {self.input_dict.keys()}")

        structure_model = structure_model_from_input_dict(self.structure_dict)
        structure = structure_model.structure

        return structure

    @property
    def incar(self) -> Incar:

        if self.incar_dict is None:
            raise ValueError(f"No incar dictionary found in input file: keys passed are {self.input_dict.keys()}")
        
        incar_model = IncarModel(incar_dict=self.incar_dict)
        incar = incar_model.incar(self.structure)

        return incar

    @property
    def kpoints(self) -> Kpoints:

        if self.kpoints_dict is None:
            raise ValueError(f"No kpoints dictionary found in input file: keys passed are {self.input_dict.keys()}")

        kpoints_model = kpoints_model_from_dictionary(self.kpoints_dict)

        if kpoints_model.requires_structure:
            kpoints = kpoints_model.kpoints(self.structure)
        else:
            kpoints = kpoints_model.kpoints()
        
        return kpoints

    @classmethod
    def from_file(cls, filepath: Path | str):
        """Creates an Input object from a file

        Args:
            filepath: The path to the abvio yaml file

        Returns:
            Input: The Input object
        """

        input_dict = load(filepath)
        return cls(input_dict)

    def write_inputs(self, directory: Path | str):
        """Writes the input files to the directory

        Args:
            directory: The directory to write the input files to
        """

        #write only the files associated with non-None dictionaries
        if self.structure_dict is not None:
            poscar = Poscar(self.structure)
            poscar.write_file(os.path.join(directory, "POSCAR"))

        if self.incar_dict is not None:
            incar = self.incar

            if incar.check_params():
                warnings.warn("INCAR file contains unrecognized tags or values", UserWarning)

            incar.write_file(os.path.join(directory, "INCAR"))

        if self.kpoints_dict is not None:
            kpoints = self.kpoints
            kpoints.write_file(os.path.join(directory, "KPOINTS"))




