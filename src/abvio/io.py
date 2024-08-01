import logging
import warnings
import yaml
import os

from pathlib import Path

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


def format_structure_output(structure: Structure) -> dict:
    """Formats the structure object into a dictionary

    This is used for the to_file() method in the Input class

    Args:
        structure (Structure): The pymatgen structure object

    Returns:
        dict: The dictionary representation of the structure
    """

    #structure dict only needs lattice: a,b,c, alpha, beta, gamma ; species: list of species ; coords: list of coordinates
    structure_dict = {
        "mode": "manual",
        "lattice": {
            "a": structure.lattice.a,
            "b": structure.lattice.b,
            "c": structure.lattice.c,
            "alpha": structure.lattice.alpha,
            "beta": structure.lattice.beta,
            "gamma": structure.lattice.gamma,
        },
        "species": [ str(specie) for specie in structure.species ],
        "coords": structure.cart_coords.tolist(),
    }

    return structure_dict


def conver_pmg_kpoints_name_to_abvio_name(pmg_name: str) -> str:
    """Converts a pymatgen kpoints name to an abvio kpoints name

    Args:
        pmg_name (str): The pymatgen kpoints name

    Returns:
        str: The abvio kpoints name
    """

    kpoints_name_map = {
        "Gamma": "gamma",
        "Monkhorst": "monkhorst",
        "Line_mode": "line",
        "Automatic": "surface",
    }

    return kpoints_name_map[str(pmg_name)]


def format_kpoints_output(kpoints: Kpoints) -> dict:
    """Formats the kpoints object into a dictionary

    This is used for the to_file() method in the Input class

    Args:
        kpoints (Kpoints): The pymatgen kpoints object

    Returns:
        dict: The dictionary representation of the kpoints
    """


    kpoints_dict = {
        "mode": conver_pmg_kpoints_name_to_abvio_name(kpoints.style),
        "shift": [float(shift) for shift in kpoints.kpts_shift],
    }

    modes = Kpoints.supported_modes
    simple_list_styles = [modes.Monkhorst, modes.Gamma, modes.Automatic]
    if kpoints.style in simple_list_styles:
        kpoints_dict["spacing"] = list(kpoints.kpts[0])

    elif kpoints.style == Kpoints.supported_modes.Line_mode:
        kpoints_dict["spacing"] = kpoints.num_kpts
        kpoints_dict["paths"] = [list(kpts) for kpts in kpoints.kpts]

    if kpoints.labels is not None:
        kpoints_dict["labels"] = kpoints.labels

    return kpoints_dict



class Input:
    def __init__(self, input_dictionary: dict):
        self.input_dict = input_dictionary
        self.structure_dict = input_dictionary.get("structure")
        self.incar_dict = input_dictionary.get("incar")
        self.kpoints_dict = input_dictionary.get("kpoints")

    @property
    def structure(self) -> Structure:
        if self.structure_dict is None:
            raise ValueError(
                f"No structure dictionary found in input file: keys passed are {self.input_dict.keys()}"
            )

        structure_model = structure_model_from_input_dict(self.structure_dict)
        structure = structure_model.structure

        return structure

    @property
    def incar(self) -> Incar:
        if self.incar_dict is None:
            raise ValueError(
                f"No incar dictionary found in input file: keys passed are {self.input_dict.keys()}"
            )

        incar_model = IncarModel(incar_dict=self.incar_dict)
        incar = incar_model.incar(self.structure)

        return incar

    @property
    def kpoints(self) -> Kpoints:
        if self.kpoints_dict is None:
            raise ValueError(
                f"No kpoints dictionary found in input file: keys passed are {self.input_dict.keys()}"
            )

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

        # write only the files associated with non-None dictionaries
        if self.structure_dict is not None:
            poscar = Poscar(self.structure)
            poscar.write_file(os.path.join(directory, "POSCAR"))

        if self.incar_dict is not None:
            incar = self.incar

            if incar.check_params():
                warnings.warn(
                    "INCAR file contains unrecognized tags or values", UserWarning
                )
            
            incar.write_file(os.path.join(directory, "INCAR"))

        if self.kpoints_dict is not None:
            kpoints = self.kpoints
            kpoints.write_file(os.path.join(directory, "KPOINTS"))

    @classmethod
    def from_vaspset(cls, directory: Path | str) -> dict:
        """Reads the input files from a directory

        Args:
            directory: The directory to read the input files from
        """

        # read the files from the directory
        poscar = Poscar.from_file(os.path.join(directory, "POSCAR"))
        incar = Incar.from_file(os.path.join(directory, "INCAR"))
        kpoints = Kpoints.from_file(os.path.join(directory, "KPOINTS"))

        # create the input dictionary
        structure_dict = format_structure_output(poscar.structure)
        incar_dict = dict(incar)
        kpoints_dict = format_kpoints_output(kpoints)

        input_dict = {
            "structure": structure_dict,
            "incar": incar_dict,
            "kpoints": kpoints_dict
        }

        return cls(input_dict)

    def write_file(self, filename: Path | str):
        """Writes the input dictionary to a file

        Args:
            filepath: The path to write the abvio yaml file to
        """
    
        #prepare structure and kpoints dictionaries
        structure_dict = format_structure_output(self.structure)
        kpoints_dict = format_kpoints_output(self.kpoints)

        #write the dictionary to a file
        output_dict = {
            "structure": structure_dict,
            "incar": self.incar_dict,
            "kpoints": kpoints_dict
        }

        with open(filename, "w") as f:
            yaml.dump(output_dict, f, default_flow_style=None)
