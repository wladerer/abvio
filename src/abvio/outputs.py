import argparse
import os
import yaml
import getpass
import platform
import socket
from datetime import datetime, timezone
from abvio.aio import format_structure_output
from pymatgen.io.vasp import Vasprun, Outcar
from typing import Optional, Dict, Any
import xml.etree.ElementTree as ET

import logging

logger = logging.getLogger(__name__)
# Configure logging to have a basic configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def is_valid_xml(file_path: str) -> bool:
    """Check if XML file is valid and complete."""
    try:
        # Quick check for basic XML validity
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        # Check if it's a VASP XML file
        if root.tag != 'modeling':
            logger.warning(f"{file_path}: Not a valid VASP XML file (root tag: {root.tag})")
            return False
            
        # Check for basic completion - look for calculation tag
        calculations = root.findall('.//calculation')
        if not calculations:
            logger.warning(f"{file_path}: No calculation data found")
            return False
            
        return True
    except ET.ParseError as e:
        logger.warning(f"{file_path}: XML parse error - {e}")
        return False
    except Exception as e:
        logger.warning(f"{file_path}: Error checking XML validity - {e}")
        return False

def extract_vasprun_summary(vasprun_path: str) -> Optional[Dict[str, Any]]:
    """Extract summary from vasprun.xml with improved error handling."""
    
    # First check if the XML is valid
    if not is_valid_xml(vasprun_path):
        logger.error(f"Skipping {vasprun_path}: Invalid or incomplete XML file")
        return None
    
    try:
        logger.info(f"Processing vasprun.xml: {vasprun_path}")
        
        # More conservative parsing options
        v = Vasprun(
            vasprun_path,
            parse_dos=False,
            parse_eigen=False,
            parse_projected_eigen=False,
            parse_potcar_file=False,
            exception_on_bad_xml=True,  # Changed to True for better error detection
            ionic_step_skip=None,
            ionic_step_offset=0,
            parse_parameters=True,
        )
        
        # Build summary with more defensive checks
        summary = {}
        
        # Basic convergence info
        try:
            summary["converged"] = getattr(v, 'converged', None)
            summary["converged_electronic"] = getattr(v, 'converged_electronic', None)
            summary["converged_ionic"] = getattr(v, 'converged_ionic', None)
        except Exception as e:
            logger.warning(f"Error extracting convergence info: {e}")
            
        # Energy information
        try:
            final_energy = getattr(v, 'final_energy', None)
            summary["final_energy"] = float(final_energy) if final_energy is not None else None
        except Exception as e:
            logger.warning(f"Error extracting final energy: {e}")
            summary["final_energy"] = None
            
        # Run type
        try:
            run_type = getattr(v, 'run_type', None)
            summary["run_type"] = str(run_type) if run_type is not None else None
        except Exception as e:
            logger.warning(f"Error extracting run type: {e}")
            summary["run_type"] = None
            
        # Ionic steps
        try:
            summary["nionic_steps"] = getattr(v, 'nionic_steps', None)
        except Exception as e:
            logger.warning(f"Error extracting ionic steps: {e}")
            summary["nionic_steps"] = None
            
        # Fermi energy
        try:
            efermi = getattr(v, 'efermi', None)
            summary["efermi"] = float(efermi) if efermi is not None else None
        except Exception as e:
            logger.warning(f"Error extracting Fermi energy: {e}")
            summary["efermi"] = None
            
        # Spin information
        try:
            summary["spin"] = getattr(v, 'is_spin', None)
        except Exception as e:
            logger.warning(f"Error extracting spin info: {e}")
            summary["spin"] = None
            
        # POTCAR symbols
        try:
            summary["potcar_symbols"] = getattr(v, 'potcar_symbols', None)
        except Exception as e:
            logger.warning(f"Error extracting POTCAR symbols: {e}")
            summary["potcar_symbols"] = None
            
        # INCAR parameters
        try:
            incar = getattr(v, 'incar', None)
            summary["incar"] = incar.as_dict() if incar is not None else None
        except Exception as e:
            logger.warning(f"Error extracting INCAR: {e}")
            summary["incar"] = None
            
        # Final structure
        try:
            final_structure = getattr(v, 'final_structure', None)
            summary["final_structure"] = format_structure_output(final_structure) if final_structure is not None else None
        except Exception as e:
            logger.warning(f"Error extracting final structure: {e}")
            summary["final_structure"] = None
        
        logger.info(f"Successfully processed vasprun.xml: {vasprun_path}")
        return summary

    except Exception as e:
        logger.error(f"Error parsing vasprun.xml {vasprun_path}: {type(e).__name__}: {e}")
        # Log more details for debugging
        try:
            file_size = os.path.getsize(vasprun_path) / (1024**2)  # Size in MB
            logger.error(f"File size: {file_size:.2f} MB")
        except:
            pass
        return None

def extract_outcar_summary(outcar_path: str) -> Optional[Dict[str, Any]]:
    """Extract summary from OUTCAR with improved error handling."""
    try:
        logger.info(f"Processing OUTCAR: {outcar_path}")
        outcar = Outcar(outcar_path)
        
        summary = {}
        
        # Run statistics
        try:
            summary["run_stats"] = getattr(outcar, 'run_stats', None)
        except Exception as e:
            logger.warning(f"Error extracting run stats: {e}")
            summary["run_stats"] = None
            
        # Free energy
        try:
            final_fr_energy = getattr(outcar, 'final_fr_energy', None)
            summary["free_energy"] = float(final_fr_energy) if final_fr_energy is not None else None
        except Exception as e:
            logger.warning(f"Error extracting free energy: {e}")
            summary["free_energy"] = None
            
        # Number of electrons
        try:
            nelect = getattr(outcar, 'nelect', None)
            summary["nelect"] = float(nelect) if nelect is not None else None
        except Exception as e:
            logger.warning(f"Error extracting nelect: {e}")
            summary["nelect"] = None
            
        # Magnetization
        try:
            total_mag = getattr(outcar, 'total_mag', None)
            summary["magnetization"] = float(total_mag) if total_mag is not None else None
        except Exception as e:
            logger.warning(f"Error extracting magnetization: {e}")
            summary["magnetization"] = None
        
        logger.info(f"Successfully processed OUTCAR: {outcar_path}")
        return summary
        
    except Exception as e:
        logger.error(f"Error parsing OUTCAR {outcar_path}: {type(e).__name__}: {e}")
        return None

def is_large_file(file_path: str, max_size_gb: int = 6) -> bool:
    """Check if file exceeds size limit."""
    try:
        return os.path.getsize(file_path) > max_size_gb * (1024 ** 3)
    except OSError:
        return False

def main():
    parser = argparse.ArgumentParser(description="Summarize VASP outputs to YAML")
    parser.add_argument("input", type=str, help="Path to the VASP output directory")
    parser.add_argument("-o", "--output", type=str, help="Path to the output YAML file")
    parser.add_argument("-m", "--message", type=str, help="Optional note or message")
    parser.add_argument("-t", "--tags", nargs="*", help="Optional tags to annotate the calculation (e.g., slab 111 soc)")
    parser.add_argument("--max-size-gb", type=int, default=6, help="Maximum file size in GB to process (default: 6)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    # Adjust logging level if verbose
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    output_dir = args.input

    # Validate input directory
    if not os.path.isdir(output_dir):
        logger.error(f"Input directory does not exist: {output_dir}")
        return 1

    metadata = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hostname": socket.gethostname(),
        "user": getpass.getuser(),
        "platform": platform.platform(),
        "current_directory": os.path.abspath(output_dir)
    }

    if args.message:
        metadata["note"] = args.message

    if args.tags:
        metadata["tags"] = args.tags

    output_data = {"metadata": metadata}

    vasprun_path = os.path.join(output_dir, "vasprun.xml")
    outcar_path = os.path.join(output_dir, "OUTCAR")

    # Process vasprun.xml
    if os.path.isfile(vasprun_path):
        if is_large_file(vasprun_path, args.max_size_gb):
            logger.warning(f"{vasprun_path} exceeds the maximum file size of {args.max_size_gb} GB and will be skipped")
            output_data["vasprun"] = {"error": "File too large", "max_size_gb": args.max_size_gb}
        else:
            vasprun_summary = extract_vasprun_summary(vasprun_path)
            if vasprun_summary is not None:
                output_data["vasprun"] = vasprun_summary
            else:
                output_data["vasprun"] = {"error": "Failed to parse vasprun.xml"}
    else:
        logger.warning("vasprun.xml not found")
        output_data["vasprun"] = {"error": "File not found"}

    # Process OUTCAR
    if os.path.isfile(outcar_path):
        if is_large_file(outcar_path, args.max_size_gb):
            logger.warning(f"{outcar_path} exceeds the maximum file size of {args.max_size_gb} GB and will be skipped")
            output_data["outcar"] = {"error": "File too large", "max_size_gb": args.max_size_gb}
        else:
            outcar_summary = extract_outcar_summary(outcar_path)
            if outcar_summary is not None:
                output_data["outcar"] = outcar_summary
            else:
                output_data["outcar"] = {"error": "Failed to parse OUTCAR"}
    else:
        logger.warning("OUTCAR not found")
        output_data["outcar"] = {"error": "File not found"}

    # Output results
    if args.output:
        try:
            with open(args.output, "w") as f:
                yaml.dump(output_data, f, sort_keys=False, default_flow_style=False)
            logger.info(f"Output written to: {args.output}")
        except Exception as e:
            logger.error(f"Error writing output file: {e}")
            return 1
    else:
        logger.info("Output data:")
        print(yaml.dump(output_data, sort_keys=False, default_flow_style=False))

    return 0

if __name__ == "__main__":
    exit(main())