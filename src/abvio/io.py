import logging
import yaml
import os

from pathlib import Path

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


