import inspect
from typing import Callable, Dict, Any, List, Optional, Union
from dask_jobqueue.pbs import PBSJob
from dask_jobqueue.slurm import SLURMJob
from pydantic import BaseModel, field_validator, Field, model_validator


# Define job parameters with aliases
JOB_PARAMETERS = {
    "cores": ["cores", "num_cores", "core_count"],
    "memory": ["memory", "mem", "ram"],
    "processes": ["processes", "num_processes"],
    "job_script_prologue": ["job_script_prologue", "script_prologue", "script", "commands"],
    "header_skip": ["header_skip", "skip_directives" ],
    "job_directives_skip": ["job_directives_skip", "skip_header_directives", "skip"],
    "shebang": ["shebang", "interpreter"],
    "python": ["python", "python_exec"],
    "job_name": ["name", "jobname", "job_name"],
}

def extract_kwargs(func: Callable, args_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts and returns only the keyword arguments from a given dictionary 
    that are accepted by the specified function.

    Parameters:
    func (Callable): The function whose keyword arguments should be extracted.
    args_dict (Dict[str, Any]): The dictionary containing potential arguments.

    Returns:
    Dict[str, Any]: A dictionary containing only the keyword arguments that match 
    the function's signature.
    """
    sig = inspect.signature(func)
    kwarg_names = [
        param.name for param in sig.parameters.values()
        if param.default != inspect.Parameter.empty or param.kind == inspect.Parameter.VAR_KEYWORD
    ]
    return {key: value for key, value in args_dict.items() if key in kwarg_names}


def resolve_aliases(input_dict: Dict[str, Any], alias_dict: Dict[str, list]) -> Dict[str, Any]:
    """
    Resolves aliases in the input dictionary to the appropriate job parameter names.

    Parameters:
    input_dict (Dict[str, Any]): Dictionary containing user input with potential aliases.
    alias_dict (Dict[str, list]): Dictionary mapping job parameters to lists of aliases.

    Returns:
    Dict[str, Any]: A dictionary with resolved job parameters and their corresponding values.
    """
    resolved_dict = {}
    for param, aliases in alias_dict.items():
        # Find the first key in input_dict that matches one of the aliases
        for alias in aliases:
            if alias in input_dict:
                resolved_dict[param] = input_dict[alias]
                break
    return resolved_dict


def job_type_from_scheduler(scheduler: str) -> Callable:
    """
    Returns the appropriate job class based on the scheduler type.

    Parameters:
    scheduler (str): The scheduler type, either 'pbs' or 'slurm'.

    Returns:
    Callable: The job class corresponding to the scheduler.

    Raises:
    ValueError: If the scheduler type is not supported.
    """
    if scheduler.lower() == "pbs":
        return PBSJob
    elif scheduler.lower() == "slurm":
        return SLURMJob
    else:
        raise ValueError(f"Unsupported scheduler: {scheduler}")


def update_job_parameters_with_nodes(
    job_parameters: Dict[str, Any],
    extra_parameters: Dict[str, Any],
    scheduler: str
) -> Dict[str, Any]:
    """
    Updates job parameters with node specifications based on the scheduler.

    Parameters:
    job_parameters (Dict[str, Any]): The current job parameters.
    extra_parameters (Dict[str, Any]): Additional parameters including 'nodes'.
    scheduler (str): The scheduler type ('slurm' or 'pbs').

    Returns:
    Dict[str, Any]: The updated job parameters with node specifications.
    """
    nodes = extra_parameters.get('nodes')
    
    if nodes is not None:
        if scheduler.lower() == 'slurm':
            # Append SLURM node specification
            if 'job_extra_directives' not in job_parameters:
                job_parameters['job_extra_directives'] = []
            job_parameters['job_extra_directives'].append(f"--nodes={nodes}")
        elif scheduler.lower() == 'pbs':
            # Append PBS node specification
            if 'job_extra_directives' not in job_parameters:
                job_parameters['job_extra_directives'] = []
            job_parameters['job_extra_directives'].append(f"-l nodes={nodes}")
        else:
            raise ValueError(f"Unsupported scheduler: {scheduler}")

    return job_parameters


class Job(BaseModel):
    scheduler: str = Field(..., description="Scheduler type (e.g., 'pbs' or 'slurm')")
    directives_dict: Dict[str, Any] = Field(..., description="Dictionary of directives for the job")

    dask_job_object: Optional[Union[PBSJob, SLURMJob]] = None
    directives: Optional[str] = None
    shebang: Optional[str] = None
    script: Optional[List[str]] = None
    extra_parameters: Optional[Dict[str, Any]] = None

    class Config:
        arbitrary_types_allowed = True

    @model_validator(mode='before')
    def validate_scheduler_and_directives(cls, values):
        scheduler = values.get('scheduler')
        directives_dict = values.get('directives_dict', {})

        # Validate scheduler
        if scheduler not in ['pbs', 'slurm']:
            raise ValueError("Scheduler must be either 'pbs' or 'slurm'")

        # Validate directives_dict
        shebang = directives_dict.get('shebang', '')
        if not shebang.startswith('#!'):
            raise ValueError("Shebang must start with '#!'")
        
        script = directives_dict.get('script')
        if not isinstance(script, list) or not all(isinstance(line, str) for line in script):
            raise ValueError("Script must be a list of strings.")
        
        #must have at least cores and memory
        if not any(k in directives_dict for k in ['cores', 'memory']):
            raise ValueError("Job must specify at least 'cores' and 'memory'.")
        
        return values

    def __init__(self, scheduler: str, directives_dict: Dict[str, Any]) -> None:
        super().__init__(scheduler=scheduler, directives_dict=directives_dict)
        
        # Resolve aliases and filter parameters
        job_parameters = resolve_aliases(directives_dict, JOB_PARAMETERS)
        extra_parameters = {k: v for k, v in directives_dict.items() if k not in job_parameters}
        
        # Update job parameters with node specifications
        job_parameters = update_job_parameters_with_nodes(job_parameters, extra_parameters, scheduler)
        
        # If name is not provided, use the f"vasp{scheduler}" as the default name
        job_parameters['job_name'] = job_parameters.get('job_name', f"vasp{scheduler}")

        # Initialize the dask job object and extract job header
        job_class = job_type_from_scheduler(self.scheduler)
        self.dask_job_object = job_class(**job_parameters)
        self.directives = self.dask_job_object.job_header
        self.shebang = directives_dict.get('shebang', '#!/bin/bash')
        self.script = directives_dict.get('script', [])
        self.extra_parameters = extra_parameters  # Store extra parameters

    def __str__(self) -> str:
        script_content = "\n".join(self.script)
        return f"{self.shebang}\n{self.directives}\n{script_content}"

    def to_file(self, filename: str) -> None:
        with open(filename, "w") as f:
            f.write(str(self))

    @classmethod
    def from_dict(cls, job_dict: Dict[str, Any]) -> 'Job':
        return cls(**job_dict)