import logging

from pymatgen.core import Structure
from pymatgen.io.vasp import Incar

from pydantic import BaseModel, field_validator

log = logging.getLogger(__name__)
log_format = "%(asctime)s - %(levelname)s - %(message)s"
date_format = "%Y-%m-%d"

logging.basicConfig(level=logging.INFO, format=log_format, datefmt=date_format)


def assign_site_property_by_species(
    structure: Structure,
    species: str,
    property_name: str,
    property_value: float | list[float],
) -> Structure:
    """
    Assign a property to a species
    Args:
        structure: pymatgen Structure object
        species: species to assign property to
        property_name: name of property to assign
        property_value: value of property to assign

    Returns:
        pymatgen Structure object with property assigned
    """

    sites = structure.sites
    for site in sites:
        if site.species_string == species:
            site.properties[property_name] = property_value

    return structure


def assign_site_property_by_index(
    structure: Structure,
    index: int,
    property_name: str,
    property_value: float | list[float],
) -> Structure:
    """
    Assign a property to a site
    Args:
        structure: pymatgen Structure object
        index: index of site to assign property to
        property_name: name of property to assign
        property_value: value of property to assign

    Returns:
        pymatgen Structure object with property assigned
    """

    sites = structure.sites
    sites[index].properties[property_name] = property_value

    return structure


def assign_site_property_by_range(
    structure: Structure,
    range: slice,
    property_name: str,
    property_value: float | list[float],
) -> Structure:
    """
    Assign a property to a range of sites
    Args:
        structure: pymatgen Structure object
        range: slice object used to specify range of sites to assign property to
        property_name: name of property to assign
        property_value: value of property to assign

    Returns:
        pymatgen Structure object with property assigned
    """

    sites = structure.sites
    for site in sites[range]:
        site.properties[property_name] = property_value

    return structure


def is_range_dict(range_dict: dict) -> bool:
    """
    Check if a dictionary is a range dictionary

    Format is a dictionary that contains
    {
        "start": int,
        "stop": int,
        "value" : (float | list[float])
    }

    Sometimes the dictionary may contain "step" key to specify step size

    Args:
        range_dict: dictionary to check
    Returns:
        bool indicating if dictionary is a range dictionary
    """

    if "start" in range_dict and "stop" in range_dict and "value" in range_dict:
        return True
    else:
        log.error(f"Range dictionary is improperly formatted: {range_dict}")
        return False


def is_range_list(range_list: list) -> bool:
    """
    Ranges are often specified as a list of dictionaries

    This function checks if a list contains range dictionaries

    Args:
        range_list: list of dictionaries to check
    Returns:
        bool indicating if list contains range dictionaries
    """

    if isinstance(range_list, list) and all(
        [is_range_dict(range_dict) for range_dict in range_list]
    ):
        return True

    log.debug(f"Not a range list: {range_list}")
    return False


def is_species_dict(species_dict: dict) -> bool:
    """
    Check if a dictionary is an index dictionary

    Format is a dictionary that contains
    {
        symbol1: magmom1,
        symbol2: magmom2,
        ...
    }

    Args:
        species_dict: dictionary to check

    Returns:
        bool indicating if dictionary is an index dictionary
    """
    if not isinstance(species_dict, dict):
        return False

    if all(
        [isinstance(value, (int, float, list)) for value in species_dict.values()]
    ) and all([isinstance(key, str) for key in species_dict.keys()]):
        return True
    else:
        return False


def is_index_dict(index_dict: dict) -> bool:
    """
    Check if a dictionary is an index dictionary

    Format is a dictionary that contains
    {
        index1: magmom1,
        index2: magmom2,
        ...
    }

    Args:
        index_dict: dictionary to check

    Returns:
        bool indicating if dictionary is an index dictionary
    """

    if not isinstance(index_dict, dict):
        return False

    if all(
        [isinstance(value, (int, float, list)) for value in index_dict.values()]
    ) and all([isinstance(key, int) for key in index_dict.keys()]):
        return True
    else:
        return False


def is_collinear(magmom_entry: list | dict) -> bool:
    """
    Check if magmom_entry is a collinear magmom entry
    Args:
        magmom_entry: list or dictionary to check
    Returns:
        bool indicating if magmom_entry is a collinear magmom entry
    Raises:
        ValueError if magmom_entry is improperly formatted
    """

    # checks if magmom_entry is an index, range, or species dictionary
    if is_index_dict(magmom_entry) or is_species_dict(magmom_entry):
        # check if values are floats or lists of floats
        if all([isinstance(value, (float, int)) for value in magmom_entry.values()]):
            return True
        if all([isinstance(value, list) for value in magmom_entry.values()]):
            return False
        else:
            raise ValueError(f"Magnetic moments is improperly formatted {magmom_entry}")

    if is_range_list(magmom_entry):
        # select the "value" key of each entry in the list and check if it is a float or list of floats
        if all(
            [
                isinstance(range_dict["value"], (float, int))
                for range_dict in magmom_entry
            ]
        ):
            return True
        if all([isinstance(range_dict["value"], list) for range_dict in magmom_entry]):
            return False
        else:
            raise ValueError(
                f"Magnetic moments is improperly formatted: {magmom_entry}"
            )

    else:
        raise ValueError(f"Magnetic moments is improperly formatted: {magmom_entry}")


def is_valid_magmom_entry(magmom_entry: list | dict) -> bool:
    """
    Check if magmom_entry is a valid magmom entry
    Args:
        magmom_entry: list or dictionary to check
    Returns:
        bool indicating if magmom_entry is a valid magmom entry
    """

    # checks if magmom_entry is an index, range, or species dictionary
    if (
        is_index_dict(magmom_entry)
        or is_species_dict(magmom_entry)
        or is_range_list(magmom_entry)
    ):
        return True
    else:
        return False


def site_properties_from_structure(
    structure: Structure, property_name: str, default=None
) -> list:
    """
    Get a property from a structure
    Args:
        structure: pymatgen Structure object
        property_name: name of property to get
        default: default value of property if no property is assigned
    Returns:
        list of property values
    """

    sites = structure.sites
    properties = [site.properties.get(property_name, default) for site in sites]

    return properties


def format_magnetic_moments(
    magmom_entry: list | dict, structure: Structure, missing: float | list = 0
) -> list:
    """
    Format magnetic moments to be compatible with pymatgen Incar object
    Args:
        magmom_entry: magmom entry to format
        structure: structure to assign magmom entries to
        missing: default value for missing magmom entries
    Returns:
        list of magnetic moments
    """

    if is_index_dict(magmom_entry):
        for index, magmom in magmom_entry.items():
            structure = assign_site_property_by_index(
                structure, index, "magmom", magmom
            )

    if is_species_dict(magmom_entry):
        for species, magmom in magmom_entry.items():
            structure = assign_site_property_by_species(
                structure, species, "magmom", magmom
            )

    if is_range_list(magmom_entry):
        for range_dict in magmom_entry:
            start = range_dict["start"]
            stop = range_dict["stop"]
            step = range_dict.get("step")
            value = range_dict["value"]
            structure = assign_site_property_by_range(
                structure, slice(start, stop, step), "magmom", value
            )

    magmoms = site_properties_from_structure(structure, "magmom", missing)

    return magmoms


def format_incar_dict(
    incar_dict: dict, structure: Structure, missing: float | list = 0
) -> dict:
    """Takes incar dict and formats it to be compatible with pymatgen Incar object

    Currently only supports magmom entries

    Args:
        incar_dict (dict): The incar dictionary
        structure (Structure, optional): The structure to assign magmom entries to
        missing (float | list): The default value for missing magmom entrie. Defaults to 0.
    """
    formatted_incar_dict = incar_dict.copy()

    if formatted_incar_dict.get("magmom"):
        magmom_entry = formatted_incar_dict.pop("magmom")
        magmoms = format_magnetic_moments(magmom_entry, structure, missing)
        formatted_incar_dict["magmom"] = magmoms

    # set all keys to uppercase
    formatted_incar_dict = {
        key.upper(): value for key, value in formatted_incar_dict.items()
    }

    return formatted_incar_dict


class IncarModel(BaseModel):
    """Pydantic model used to help validate the incar dictionary format

    1. checks if incar is a dictionary
    2. checks if all key value pairs are valid
    3. uses pymatgen to validate the incar dictionary
    """

    incar_dict: dict

    @field_validator("incar_dict")
    def validate_incar_dict(cls, incar_dict: dict):
        """Validates the incar dictionary

        Args:
            incar_dict (dict): The incar dictionary

        Raises:
            ValueError: If the incar dictionary is invalid
        """

        if not isinstance(incar_dict, dict):
            raise ValueError("incar_dict must be a dictionary")

        try:
            if "magmom" in incar_dict:
                if not is_valid_magmom_entry(incar_dict["magmom"]):
                    raise ValueError(f"Invalid magmom entry {incar_dict['magmom'] }")
            Incar(incar_dict)
        except Exception as e:
            raise ValueError(f"Invalid INCAR dictionary: {e}")

        return incar_dict

    def incar(self, structure: Structure) -> Incar:
        """Returns the pymatgen Incar object

        Returns:
            Incar: The pymatgen Incar object
        """

        formatted_incar_dictionary = format_incar_dict(self.incar_dict, structure)
        incar = Incar(formatted_incar_dictionary)

        return incar
