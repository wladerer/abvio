#!/usr/bin/env python3
import argparse
import os
import yaml
import getpass
import platform
import socket
import glob
import json
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any, List, Tuple

# Import pymatgen components
try:
    from abvio.aio import format_structure_output
    from pymatgen.io.vasp import Vasprun, Outcar
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Make sure pymatgen and abvio are installed")
    exit(1)

import logging

# Configure logging with consistent formatting
logger = logging.getLogger(__name__)

def get_file_size_mb(file_path: str) -> float:
    """Get file size in MB."""
    try:
        return os.path.getsize(file_path) / (1024**2)
    except OSError:
        return 0.0

class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to log levels when outputting to terminal."""
    
    COLORS = {
        'DEBUG': '\033[0;36m',    # Cyan
        'INFO': '\033[0;34m',     # Blue
        'SUCCESS': '\033[0;32m',  # Green
        'WARNING': '\033[0;33m',  # Yellow
        'ERROR': '\033[0;31m',    # Red
        'CRITICAL': '\033[0;35m', # Magenta
    }
    RESET = '\033[0m'
    
    def __init__(self, use_colors=None):
        super().__init__('%(asctime)s - %(levelname)s - %(message)s', 
                         datefmt='%Y-%m-%d %H:%M:%S')
        # Auto-detect if we should use colors (terminal vs file)
        if use_colors is None:
            import sys
            self.use_colors = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
        else:
            self.use_colors = use_colors
    
    def format(self, record):
        if self.use_colors and record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
        return super().format(record)

# Add SUCCESS level to logging
SUCCESS_LEVEL = 25
logging.addLevelName(SUCCESS_LEVEL, "SUCCESS")

def log_success(self, message, *args, **kwargs):
    if self.isEnabledFor(SUCCESS_LEVEL):
        self._log(SUCCESS_LEVEL, message, args, **kwargs)

logging.Logger.success = log_success

def setup_logging(verbose=False, use_colors=None):
    """Setup logging with optional colors and verbosity."""
    level = logging.DEBUG if verbose else logging.INFO
    
    # Clear any existing handlers
    logging.getLogger().handlers.clear()
    
    # Create handler with colored formatter
    handler = logging.StreamHandler()
    handler.setFormatter(ColoredFormatter(use_colors))
    
    # Configure root logger
    logging.getLogger().setLevel(level)
    logging.getLogger().addHandler(handler)

def is_valid_xml(file_path: str) -> bool:
    """Check if XML file is valid and complete."""
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        if root.tag != 'modeling':
            return False
            
        calculations = root.findall('.//calculation')
        if not calculations:
            return False
            
        return True
    except (ET.ParseError, Exception):
        return False

def extract_vasprun_summary(vasprun_path: str) -> Optional[Dict[str, Any]]:
    """Extract summary from vasprun.xml with improved error handling."""
    
    if not is_valid_xml(vasprun_path):
        return {"error": "Invalid XML", "size_mb": get_file_size_mb(vasprun_path)}
    
    try:
        v = Vasprun(
            vasprun_path,
            parse_dos=False,
            parse_eigen=False,
            parse_projected_eigen=False,
            parse_potcar_file=False,
            exception_on_bad_xml=True,
            ionic_step_skip=None,
            ionic_step_offset=0,
        )
        
        summary = {}
        
        # Extract all properties with error handling
        for prop, attr in [
            ("converged", 'converged'),
            ("converged_electronic", 'converged_electronic'),
            ("converged_ionic", 'converged_ionic'),
            ("nionic_steps", 'nionic_steps'),
            ("spin", 'is_spin'),
            ("potcar_symbols", 'potcar_symbols'),
        ]:
            try:
                summary[prop] = getattr(v, attr, None)
            except Exception:
                summary[prop] = None
                
        # Handle numeric properties
        for prop, attr in [
            ("final_energy", 'final_energy'),
            ("efermi", 'efermi'),
        ]:
            try:
                val = getattr(v, attr, None)
                summary[prop] = float(val) if val is not None else None
            except Exception:
                summary[prop] = None
                
        # Handle string properties
        try:
            run_type = getattr(v, 'run_type', None)
            summary["run_type"] = str(run_type) if run_type is not None else None
        except Exception:
            summary["run_type"] = None
            
        # Handle complex objects
        try:
            incar = getattr(v, 'incar', None)
            summary["incar"] = incar.as_dict() if incar is not None else None
        except Exception:
            summary["incar"] = None
            
        try:
            final_structure = getattr(v, 'final_structure', None)
            summary["final_structure"] = format_structure_output(final_structure) if final_structure is not None else None
        except Exception:
            summary["final_structure"] = None
        
        return summary

    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)}", "size_mb": get_file_size_mb(vasprun_path)}

def extract_outcar_summary(outcar_path: str) -> Optional[Dict[str, Any]]:
    """Extract summary from OUTCAR with improved error handling."""
    try:
        outcar = Outcar(outcar_path)
        
        summary = {}
        
        # Extract properties with error handling
        try:
            summary["run_stats"] = getattr(outcar, 'run_stats', None)
        except Exception:
            summary["run_stats"] = None
            
        # Handle numeric properties
        for prop, attr in [
            ("free_energy", 'final_fr_energy'),
            ("nelect", 'nelect'),
            ("magnetization", 'total_mag'),
        ]:
            try:
                val = getattr(outcar, attr, None)
                summary[prop] = float(val) if val is not None else None
            except Exception:
                summary[prop] = None
        
        return summary
        
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)}", "size_mb": get_file_size_mb(outcar_path)}

def is_large_file(file_path: str, max_size_gb: int = 6) -> bool:
    """Check if file exceeds size limit."""
    try:
        return os.path.getsize(file_path) > max_size_gb * (1024 ** 3)
    except OSError:
        return False

def find_vasp_directories(root_path: str, max_depth: int = None) -> List[str]:
    """Find all directories containing VASP output files."""
    vasp_dirs = []
    root_path = Path(root_path)
    
    if max_depth is not None:
        pattern = '/'.join(['*'] * max_depth)
        search_pattern = str(root_path / pattern)
    else:
        search_pattern = str(root_path / '**')
    
    # Look for directories with vasprun.xml or OUTCAR
    for pattern in ['vasprun.xml', 'OUTCAR']:
        if max_depth is not None:
            files = glob.glob(f"{search_pattern}/{pattern}")
        else:
            files = glob.glob(f"{search_pattern}/{pattern}", recursive=True)
            
        for file_path in files:
            dir_path = os.path.dirname(file_path)
            if dir_path not in vasp_dirs:
                vasp_dirs.append(dir_path)
    
    return sorted(vasp_dirs)

def process_single_directory(args_tuple: Tuple[str, Dict]) -> Tuple[str, Dict]:
    """Process a single VASP directory. Designed for multiprocessing."""
    directory, config = args_tuple
    
    max_size_gb = config.get('max_size_gb', 6)
    include_metadata = config.get('include_metadata', False)
    
    result = {
        "directory": directory,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }
    
    if include_metadata:
        result["metadata"] = {
            "hostname": socket.gethostname(),
            "user": getpass.getuser(),
            "platform": platform.platform(),
        }
    
    vasprun_path = os.path.join(directory, "vasprun.xml")
    outcar_path = os.path.join(directory, "OUTCAR")
    
    # Process vasprun.xml
    if os.path.isfile(vasprun_path):
        if is_large_file(vasprun_path, max_size_gb):
            file_size_mb = get_file_size_mb(vasprun_path)
            result["vasprun"] = {
                "error": "File too large", 
                "size_mb": file_size_mb, 
                "max_size_gb": max_size_gb
            }
        else:
            result["vasprun"] = extract_vasprun_summary(vasprun_path)
    else:
        result["vasprun"] = {"error": "File not found"}
    
    # Process OUTCAR
    if os.path.isfile(outcar_path):
        if is_large_file(outcar_path, max_size_gb):
            file_size_mb = get_file_size_mb(outcar_path)
            result["outcar"] = {
                "error": "File too large", 
                "size_mb": file_size_mb, 
                "max_size_gb": max_size_gb
            }
        else:
            result["outcar"] = extract_outcar_summary(outcar_path)
    else:
        result["outcar"] = {"error": "File not found"}
    
    return directory, result

def create_slurm_scripts(directories: List[str], output_dir: str, script_name: str = "vasp_summary") -> None:
    """Create SLURM array job script for parallel processing."""
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Create job list file
    job_list_file = f"{output_dir}/{script_name}_jobs.txt"
    with open(job_list_file, 'w') as f:
        for i, directory in enumerate(directories):
            f.write(f"{i}\t{directory}\n")
    
    # Create SLURM script
    slurm_script = f"""#!/bin/bash
#SBATCH --job-name={script_name}
#SBATCH --array=0-{len(directories)-1}
#SBATCH --output={output_dir}/{script_name}_%A_%a.out
#SBATCH --error={output_dir}/{script_name}_%A_%a.err
#SBATCH --time=02:00:00
#SBATCH --mem=4G
#SBATCH --cpus-per-task=1

# Load modules (adjust as needed for your system)
# module load python/3.9
# module load vasp

# Get directory for this array task
DIRECTORY=$(sed -n "${{SLURM_ARRAY_TASK_ID + 1}}p" {job_list_file} | cut -f2)

# Run the VASP summary script
python3 {os.path.abspath(__file__)} "$DIRECTORY" \\
    --output "{output_dir}/vasp_summary_${{SLURM_ARRAY_TASK_ID}}.yaml" \\
    --single-dir \\
    --no-parallel
"""
    
    slurm_script_file = f"{output_dir}/{script_name}_array.sbatch"
    with open(slurm_script_file, 'w') as f:
        f.write(slurm_script)
    
    logger.success(f"Created SLURM array job script: {slurm_script_file}")
    logger.info(f"Created job list: {job_list_file}")
    logger.info(f"To submit: sbatch {slurm_script_file}")
    logger.info(f"Jobs: {len(directories)}")

def main():
    parser = argparse.ArgumentParser(description="Parallel VASP output summarizer with SLURM support")
    parser.add_argument("input", type=str, help="Path to root directory or single VASP directory")
    parser.add_argument("-o", "--output", type=str, help="Output file/directory")
    parser.add_argument("-j", "--jobs", type=int, default=None, help="Number of parallel jobs (default: CPU count)")
    parser.add_argument("--max-size-gb", type=int, default=6, help="Maximum file size in GB (default: 6)")
    parser.add_argument("--max-depth", type=int, help="Maximum search depth for directories")
    parser.add_argument("--single-dir", action="store_true", help="Process only the input directory (no recursive search)")
    parser.add_argument("--no-parallel", action="store_true", help="Disable parallel processing")
    parser.add_argument("--create-slurm", action="store_true", help="Create SLURM array job scripts instead of running")
    parser.add_argument("--slurm-name", type=str, default="vasp_summary", help="SLURM job name")
    parser.add_argument("-m", "--message", type=str, help="Optional note")
    parser.add_argument("-t", "--tags", nargs="*", help="Optional tags")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Setup logging with color detection
    setup_logging(args.verbose)
    
    # Determine number of jobs
    if args.jobs is None:
        args.jobs = min(cpu_count(), 8)  # Cap at 8 to avoid overwhelming the system
    
    # Find directories to process
    if args.single_dir:
        if not os.path.isdir(args.input):
            print_status("ERROR", f"Input directory does not exist: {args.input}")
            return 1
        directories = [args.input]
    else:
        logger.info(f"Searching for VASP directories in: {args.input}")
        directories = find_vasp_directories(args.input, args.max_depth)
        logger.info(f"Found {len(directories)} directories with VASP files")
    
    if not directories:
        logger.warning("No VASP directories found")
        return 1
    
    # Create output directory if needed
    output_dir = args.output or f"vasp_summaries_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if not args.single_dir and not args.output:
        os.makedirs(output_dir, exist_ok=True)
    elif args.output and not args.single_dir:
        os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else '.', exist_ok=True)
    
    # Create SLURM scripts if requested
    if args.create_slurm:
        if args.single_dir:
            logger.error("--create-slurm cannot be used with --single-dir")
            return 1
        create_slurm_scripts(directories, output_dir, args.slurm_name)
        return 0
    
    # Prepare processing configuration
    config = {
        'max_size_gb': args.max_size_gb,
        'include_metadata': True,
        'message': args.message,
        'tags': args.tags,
    }
    
    # Process directories
    if args.single_dir:
        # Single directory mode
        logger.info(f"Processing single directory: {args.input}")
        directory, result = process_single_directory((args.input, config))
        
        # Add global metadata
        if args.message:
            result["note"] = args.message
        if args.tags:
            result["tags"] = args.tags
        
        # Output results
        if args.output:
            with open(args.output, 'w') as f:
                yaml.dump(result, f, sort_keys=False, default_flow_style=False)
            logger.success(f"Output written to: {args.output}")
        else:
            print(yaml.dump(result, sort_keys=False, default_flow_style=False))
    
    else:
        # Multi-directory mode
        if args.no_parallel:
            # Sequential processing
            logger.info(f"Processing {len(directories)} directories sequentially")
            results = []
            for i, directory in enumerate(directories):
                logger.info(f"Processing [{i+1}/{len(directories)}]: {directory}")
                _, result = process_single_directory((directory, config))
                results.append(result)
        else:
            # Parallel processing
            logger.info(f"Processing {len(directories)} directories with {args.jobs} parallel jobs")
            results = []
            
            with ProcessPoolExecutor(max_workers=args.jobs) as executor:
                # Submit all jobs
                future_to_dir = {
                    executor.submit(process_single_directory, (directory, config)): directory 
                    for directory in directories
                }
                
                # Collect results
                for i, future in enumerate(as_completed(future_to_dir)):
                    directory = future_to_dir[future]
                    try:
                        _, result = future.result()
                        results.append(result)
                        logger.success(f"Completed [{i+1}/{len(directories)}]: {directory}")
                    except Exception as e:
                        logger.error(f"Failed [{i+1}/{len(directories)}]: {directory} - {e}")
                        results.append({
                            "directory": directory,
                            "error": f"Processing failed: {e}",
                            "processed_at": datetime.now(timezone.utc).isoformat()
                        })
        
        # Prepare final output
        final_output = {
            "summary": {
                "total_directories": len(directories),
                "successful": len([r for r in results if "error" not in r]),
                "failed": len([r for r in results if "error" in r]),
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "hostname": socket.gethostname(),
                "user": getpass.getuser(),
            },
            "results": results
        }
        
        if args.message:
            final_output["summary"]["note"] = args.message
        if args.tags:
            final_output["summary"]["tags"] = args.tags
        
        # Output results
        output_file = args.output or f"{output_dir}/summary.yaml"
        with open(output_file, 'w') as f:
            yaml.dump(final_output, f, sort_keys=False, default_flow_style=False)
        
        logger.success(f"Processing complete. Output written to: {output_file}")
        logger.info(f"Successful: {final_output['summary']['successful']}, Failed: {final_output['summary']['failed']}")
    
    return 0

if __name__ == "__main__":
    exit(main())