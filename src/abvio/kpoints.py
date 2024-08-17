import collections

from pymatgen.core import Structure
from pymatgen.io.vasp import Kpoints
from pymatgen.symmetry.bandstructure import HighSymmKpath
from pydantic import BaseModel, field_validator
from pydantic._internal._model_construction import ModelMetaclass
from typing import List, Union, Tuple


Number = Union[int, float]
IntArray3D = Tuple[int, int, int]
IterableNumeric = Union[List[Number], Tuple[Number]]
Matrix3D = List[Tuple[Number, Number, Number]]


class KpointsMeta(type):
    _registry = {}

    def __new__(cls, name, bases, class_dict):
        new_class = super().__new__(cls, name, bases, class_dict)
        if "mode" in class_dict:
            KpointsMeta._registry[class_dict["mode"]] = new_class
        return new_class

    @classmethod
    def from_dict(cls, kpoints_dictionary: dict):
        base_model = BaseKpoints.validate(kpoints_dictionary)
        mode = base_model.mode
        KpointsClass = cls._registry.get(mode)

        if KpointsClass is None:
            raise ValueError(f"Unknown mode: {mode}")

        return KpointsClass.validate(kpoints_dictionary)


class CombinedMeta(KpointsMeta, ModelMetaclass):
    """This is how we combine two metaclasses in Python"""

    pass


class BaseKpoints(BaseModel, metaclass=CombinedMeta):
    """Represents a base class for Kpoints"""

    mode: str
    spacing: int | float | IntArray3D | IterableNumeric

    @property
    def requires_structure(self) -> bool:
        """Checks if the Kpoints object requires a structure

        This is used to inform abvio if we need to pass a Structure object to the kpoints method

        Returns:
            bool: True if the Kpoints mode requires a structure, False otherwise
        """
        return self.mode in {"surface", "autoline"}

    @field_validator("mode")
    def check_mode(cls, mode) -> str:
        """Tries to handle different cases of the mode string and returns the correct mode

        Args:
            mode (str): The user specified mode of the kpoints

        Returns:
            str: The correct mode of the kpoints
        """

        if mode.lower().startswith("g"):
            return "gamma"
        elif mode.lower().startswith("m"):
            return "monkhorst"
        elif mode.lower() == "surface":
            return "surface"
        elif mode.lower().startswith("line"):
            return "line"
        elif mode.lower() == "autoline":
            return "autoline"
        else:
            raise ValueError(f"Invalid mode: {mode}")

    @field_validator("spacing")
    def check_spacing(cls, spacing) -> int | float:
        """Checks if the spacing is valid

        Args:
            spacing (Any): The spacing of the kpoints
        Returns:
            int | float | IntArray3D | numpy.ndarray : The spacing if it is valid
        Raises:
            ValueError: If the spacing is invalid
        """

        if isinstance(spacing, (int, float)):
            if spacing < 0:
                raise ValueError(f"Spacing must be a non-negative integer: {spacing}")

        elif isinstance(spacing, collections.abc.Iterable):
            if len(spacing) != 3:
                raise ValueError(f"Spacing must have 3 elements: {spacing}")

            for s in spacing:
                if s < 0:
                    raise ValueError(
                        f"Spacings must be all non-negative integer: {spacing}"
                    )

        else:
            raise ValueError(f"Invalid spacing: {spacing}")

        return spacing


class GammaKpoints(BaseKpoints):
    """Represents a Gamma centered grid of kpoints

    Args:
        BaseKpoints: A pydantic BaseModel

    Attributes:
        mode (str): The mode of the kpoints
        spacing (IntArray3D): The spacing of the kpoints
        shift (IntArray3D): The shift of the kpoints
    """

    mode: str = "gamma"
    spacing: IntArray3D
    shift: IntArray3D = [0, 0, 0]

    def kpoints(self):
        kpoints = Kpoints.gamma_automatic(self.spacing, self.shift)

        return kpoints


class MonkhorstKpoints(BaseKpoints):
    """Represents a Monkhorst-Pack grid of kpoints

    Args:
        BaseKpoints: A pydantic BaseModel

    Attributes:
        mode (str): The mode of the kpoints
        spacing (IntArray3D): The spacing of the kpoints
        shift (IntArray3D): The shift of the kpoints
    """

    mode: str = "monkhorst"
    spacing: IntArray3D
    shift: IntArray3D = [0, 0, 0]

    def kpoints(self):
        kpoints = Kpoints.monkhorst_automatic(self.spacing, self.shift)

        return kpoints


class SurfaceKpoints(BaseKpoints):
    """Represents kpoints for a fermi surface calculation

    Args:
        BaseKpoints: A pydantic BaseModel

    Attributes:
        mode (str): The mode of the kpoints
        spacing (float): The spacing of the kpoints
    """

    mode: str = "surface"
    spacing: float

    def kpoints(self, structure: Structure):
        """Generates kpoints for a fermi surface calculation

        Spacing is the grid density scaled by the number of divisions along each reciprocal lattice vector proportional to its length.
        Usually a large number of kpoints are needed for a fermi surface calculation (e.g 1000)

        Args:
            structure (Structure): The structure to generate kpoints for
        """

        kpoints = Kpoints.automatic_density(structure=structure, kppa=self.spacing)

        return kpoints


class LineKpoints(BaseKpoints):
    """Represents a line mode kpoints

    Args:
        BaseKpoints: A pydantic BaseModel

    Attributes:
        mode (str): The mode of the kpoints
        spacing (Number): The spacing of the kpoints
        paths (Matrix3D): Points that form the path in the Brillouin zone where each entry is [kx, ky, kz]
        labels (List[str]): The labels of the kpoints
    """

    mode: str = "line"
    spacing: int
    paths: Matrix3D
    labels: List[str]

    @field_validator("paths")
    def check_paths(cls, paths) -> Matrix3D:
        """Checks if the paths are valid

        1. the paths must have at least 2 points
        2. the paths must be a 3D matrix
        3. each point must have 3 coordinates

        Args:
            paths (Matrix3D): The paths to check

        Returns:
            Matrix3D: The paths if they are valid
        """
        if len(paths) < 2:
            raise ValueError(f"Invalid paths: {paths}")

        for path in paths:
            if len(path) != 3:
                raise ValueError(f"Invalid path: {path}")

        return paths

    @field_validator("labels")
    def check_labels(cls, labels) -> List[str]:
        """Checks if the labels are valid

        1. labels must be greater than 1
        2. each label must be a string

        Args:
            labels (List[str]): The labels to check

        Returns:
            List[str]: The labels if they are valid

        Raises:
            ValueError: If the labels are invalid
        """

        if len(labels) < 2:
            raise ValueError(f"Number of labels must be greater than 1: {labels}")

        for label in labels:
            if not isinstance(label, str):
                raise ValueError(f"Invalid label: {label}")

        return labels

    def kpoints(self, system: str = "reciprocal"):
        """Generates a line mode Kpoints object

        Args:
            system (str): The coordinate system of the path. Defaults to "reciprocal"

        Returns:
            Kpoints: A pymatgen Kpoints object
        """

        if len(self.paths) != len(self.labels):
            raise ValueError(
                f"Dimensions of labels and paths do not match: {self.paths}, {self.labels}"
            )

        header = "\n".join(
            ["Line mode KPOINTS file", f"{self.spacing}", "linemode", f"{system}"]
        )
        path_string = "\n".join(
            [
                f"{path[0]} {path[1]} {path[2]} {label}"
                for path, label in zip(self.paths, self.labels)
            ]
        )
        kpoints_str = f"{header}\n{path_string}"


        kpoints = Kpoints.from_str(kpoints_str)

        return kpoints


class AutoLineKpoints(BaseKpoints):
    mode: str = "autoline"
    spacing: int

    def kpoints(self, structure: Structure):
        """Automatically generates line mode kpoints

        Args:
            structure (Structure): The structure to generate kpoints for

        Returns:
            Kpoints: A pymatgen Kpoints object
        """

        kpath = HighSymmKpath(structure)
        kpoints = Kpoints.automatic_linemode(self.spacing, kpath)

        return kpoints


def kpoints_model_from_dictionary(kpoints_dictionary: dict) -> Kpoints:
    """Parses and validates a dictionary to create a Kpoints object according to the mode provided"""

    base_model = BaseKpoints.validate(kpoints_dictionary)

    mode_model_map = {
        "gamma": GammaKpoints,
        "monkhorst": MonkhorstKpoints,
        "surface": SurfaceKpoints,
        "line": LineKpoints,
        "autoline": AutoLineKpoints,
    }

    BaseKpointsModel = mode_model_map.get(base_model.mode)
    KpointsModel = BaseKpointsModel.validate(kpoints_dictionary)

    return KpointsModel


def kpoints_from_dictionary(
    kpoints_dictionary, structure: Structure | None = None
) -> Kpoints:
    """Parses and validates a dictionary to create a Kpoints object according to the mode provided"""

    KpointsModel = kpoints_model_from_dictionary(kpoints_dictionary)

    if KpointsModel.requires_structure:
        if structure is None:
            raise ValueError("Kpoints model requires a structure")

        kpoints = KpointsModel.kpoints(structure)

    else:
        kpoints = KpointsModel.kpoints()

    return kpoints
