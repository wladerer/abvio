import numpy as np 
import yaml 
import os 
from pathlib import Path

from pymatgen.core import Structure
from scipy.spatial import distance


def magnitude(value: int | float) -> int:
    """takes a numeric value and returns it's magnitude"""
    magnitude = np.floor(np.log10(value)).astype(int)
    return magnitude

def lower_keys(dictionary: dict) -> dict:
    """Converts all keys in a dictionary to lowercase"""
    return {k.lower(): v for k, v in dictionary.items()}


def estimate_nbands(structure: Structure) -> int:
    """Calculates the number of valence electrons in a structure"""
    rough_valence_count = 0
    for site in structure:
        rough_valence_count += sum([  n_l_count[-1] for n_l_count in site.specie.full_electronic_structure[:-2]])

    return rough_valence_count


class CheckIncar:
    """Class that checks INCAR files for correctness"""

    def __init__(self, incar_dict: dict):
        """Initializes the CheckIncar object

        Args:
            incar_dict: The dictionary containing the INCAR tags
        """

        self.incar_dict = lower_keys(incar_dict)
        self.reference_file = os.path.join(Path(__file__).parent, "reference", "incar.yaml")
        self.messages: list[str] = []

    def check_magnitudes(self):

        incar_tags = lower_keys(yaml.load(open(self.reference_file), Loader=yaml.FullLoader))

        # lookup each tag and check if the magnitude is correct, if the tag has a magnitude entry
        for tag, value in self.incar_dict.items():
            if tag in incar_tags:

                if "magnitude" in incar_tags[tag]:
                    ref_magnitude = int(incar_tags[tag]["magnitude"])
                    if isinstance(value, (list, tuple, np.ndarray)):
                        for v in value:
                            if magnitude(v) != ref_magnitude:
                                self.messages.append(f"Tag {tag} has incorrect magnitude: 1e{magnitude(v):.0g} != 1e{ref_magnitude:.0g}")
                    else:
                        if magnitude(value) != ref_magnitude:
                            self.messages.append(f"Tag {tag} has incorrect magnitude: 1e{magnitude(value):.0g} != 1e{ref_magnitude:.0g}")
        
        return self.messages

    def check_dependencies(self):
        """Checks if specified INCAR tags are present together"""
            
        # load the reference file
        incar_tags = lower_keys(yaml.load(open(self.reference_file), Loader=yaml.FullLoader))

        for tag, value in self.incar_dict.items():
            if tag in incar_tags:
                if "depends" in incar_tags[tag]:
                    for dep_tag in incar_tags[tag]["depends"]:
                        if dep_tag.lower() not in self.incar_dict:
                            self.messages.append(f"Tag {tag} requires {dep_tag}")

        return self.messages

    def check_noncollinear_magmom(self):
        """Checks to see if MAGMOM is divisible by 3 if LSORBIT is True"""
            
        if self.incar_dict.get("lsorbit", False):
            magmom = self.incar_dict.get("magmom", [])
            if len(magmom) % 3 != 0:
                self.messages.append("MAGMOM must be divisible by 3 if LSORBIT is True")

        return self.messages


    def check_nbands(self, structure: Structure):
        """Checks if the number of bands is too low"""
                
        #check if nbands is set 
        if "nbands" in self.incar_dict:
            user_nbands = self.incar_dict["nbands"]
            estimated_nbands = estimate_nbands(structure)
            if user_nbands < estimated_nbands:
                self.messages.append(f"NBANDS is too low: {user_nbands} < {estimated_nbands}")
    
        return self.messages

    def check_all(self, structure: Structure):
        self.check_magnitudes()
        self.check_dependencies()
        self.check_noncollinear_magmom()
        self.check_nbands(structure)
        return self.messages


class CheckStructure:

    def __init__(self, structure: Structure):
        self.structure: Structure = structure
        self.messages: list[str] = []

    def check_positions(self, min_distance: float = 0.5) -> list[str]:
        """Checks if atoms are too close to each other."""
        cartesian_coords = self.structure.cart_coords
        symbols = self.structure.species

        distance_matrix = distance.squareform(distance.pdist(cartesian_coords))
        close_indices = np.triu_indices_from(distance_matrix, k=1)
        too_close = np.where(distance_matrix[close_indices] < min_distance)

        for k in too_close[0]:
            i, j = close_indices[0][k], close_indices[1][k]
            self.messages.append(f"{symbols[i]}{i} is too close to {symbols[j]}{j} with a distance of {distance_matrix[i, j]:.3f} Å")
        
        return self.messages

    def check_volume(self):
        """Checks if the volume of the structure is too small"""
                
        volume = self.structure.volume

        if volume < 1:
            self.messages.append(f"Volume of the structure is too small: {volume}")

        return self.messages

    def check_all(self):
        self.check_positions()
        self.check_volume()
        return self.messages



