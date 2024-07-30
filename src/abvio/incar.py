import logging

from pymatgen.core import Structure

log = logging.getLogger(__name__)
log_format = "%(asctime)s - %(levelname)s - %(message)s"
date_format = "%Y-%m-%d"

logging.basicConfig(level=logging.INFO, format=log_format, datefmt=date_format)


def assign_magnetic_moments_by_species(structure: Structure, species: str, moment: float | list[float]) -> Structure:
    """
    Assign magnetic moments to a structure
    Args:
        structure: pymatgen Structure object
        species: species to assign magnetic moments to
        moment: magnetic moment to assign to species
    Returns:
        pymatgen Structure object with magnetic moments assigned
    """

    sites = structure.sites
    for site in sites:

        if site.species_string == species:
            site.properties['magmom'] = moment

    return structure

def assign_magnetic_moments_by_index(structure: Structure, index: int, moment: float | list[float]) -> Structure:
    """
    Assign magnetic moments to a structure
    Args:
        structure: pymatgen Structure object
        index: index of site to assign magnetic moment to
        moment: magnetic moment to assign to site
    Returns:
        pymatgen Structure object with magnetic moments assigned
    """

    sites = structure.sites
    sites[index].properties['magmom'] = moment

    return structure

def assign_magnetic_moments_by_range(structure: Structure, range: slice,  moment: float | list[float]) -> Structure:
    """
    Assign magnetic moments to a structure
    Args:
        structure: pymatgen Structure object
        range: slice object used to specify range of sites to assign magnetic moments to
        moment: magnetic moment to assign to sites
    Returns:
        pymatgen Structure object with magnetic moments assigned
    """

    sites = structure.sites
    for site in sites[range]:
        site.properties['magmom'] = moment

    return structure


def magnetic_moments_from_structure(structure: Structure, default: float | list[float] = 0) -> list:
    """
    Get magnetic moments from a structure
    Args:
        structure: pymatgen Structure object
        default: default magnetic moment if no magnetic moment is assigned
    Returns:
        list of magnetic moments
    """

    sites = structure.sites
    moments = [site.properties.get('magmom', default) for site in sites]

    return moments


def assign_ldauu_by_species(structure: Structure, species: str, ldauu: float) -> Structure:
    """
    Assign LDA+U U value to a species
    Args:
        structure: pymatgen Structure object
        species: species to assign LDA+U U value to
        ldauu: LDA+U U value to assign to species
    Returns:
        pymatgen Structure object with LDA+U U values assigned
    """

    sites = structure.sites
    for site in sites:

        if site.species_string == species:
            site.properties['ldauu'] = ldauu

    return structure

def assign_ldauu_by_index(structure: Structure, index: int, ldauu: float) -> Structure:
    """
    Assign LDA+U U value to a site
    Args:
        structure: pymatgen Structure object
        index: index of site to assign LDA+U U value to
        ldauu: LDA+U U value to assign to site
    Returns:
        pymatgen Structure object with LDA+U U values assigned
    """

    sites = structure.sites
    sites[index].properties['ldauu'] = ldauu

    return structure

def assign_ldauu_by_range(structure: Structure, range: slice, ldauu: float) -> Structure:
    """
    Assign LDA+U U value to a range of sites
    Args:
        structure: pymatgen Structure object
        range: slice object used to specify range of sites to assign LDA+U U value to
        ldauu: LDA+U U value to assign to sites
    Returns:
        pymatgen Structure object with LDA+U U values assigned
    """

    sites = structure.sites
    for site in sites[range]:
        site.properties['ldauu'] = ldauu

    return structure

def ldauu_values_from_structure(structure: Structure, default: float = 0) -> list:
    """
    Get LDA+U U values from a structure
    Args:
        structure: pymatgen Structure object
        default: default LDA+U U value if no LDA+U U value is assigned
    Returns:
        list of LDA+U U values
    """

    sites = structure.sites
    ldauu_values = [site.properties.get('ldauu', default) for site in sites]

    return ldauu_values



    