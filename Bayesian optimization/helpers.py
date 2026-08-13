###############################################################################
##### Bayesian Optimization program for painted potential: helpers ############
########################### Noam MANDIN ; 07/2025 #############################
###############################################################################
'''Programme qui regroupe un ensemblke de fonction utile pour réaliser 
l'optimisation bayésienne.'''

#%%####### Import of the required libraries ###################################
import os
import h5py
import yaml
from ax import ParameterType, RangeParameter, ChoiceParameter


#%%####### Function to load a YML file ########################################
def load_yaml_config(path):
    """
    Loads a YAML configuration file.

    Args:
    path (str): The path to the YAML file.

    Returns:
    dict: The configuration dictionary.
    """
    with open(path, "r") as f:
        config = yaml.safe_load(f)
    return config


#%%####### Function to create a file path for storing files ###################
def create_result_directory(base_directory): 
    """
    Creates a result directory. If the directory already exists, appends a suffix (_1, _2, etc.)
    to create a unique directory name.

    Args:
    base_directory (str): The base name for the directory.

    Returns:
    str: The name of the directory that was created.
    """
    directory = base_directory
    counter = 1

    # Check if the directory exists and append a suffix if it does
    while os.path.exists(directory):
        directory = f"{base_directory}_{counter}"
        counter += 1

    # Create the directory
    os.makedirs(directory)

    return directory


#%%####### Stores the data of a trial #########################################
def store_ax_optimization_result(result_directory, last_image, trial_index, arm_name):

    dir_path = os.path.join(result_directory, f"trial_{trial_index}", arm_name)

    # Create the nested directory structure 
    os.makedirs(dir_path, exist_ok=True)

    with h5py.File(f'{dir_path}/cam_acquisition.h5', 'w') as hf:
        hf.create_dataset("image", data=last_image)
 
        
#%%####### Create a parameter and its dedicated space #########################
def create_parameter(param_config, subsequence_name):

    if param_config['type'] == 'float':
        return RangeParameter(
            name=f"{param_config['name']} %{subsequence_name} ${param_config['family']}",
            parameter_type=ParameterType.FLOAT,
            lower=param_config['bounds'][0],
            upper=param_config['bounds'][1]
        )

    elif param_config['type'] == 'int':
        return RangeParameter(
            name=f"{param_config['name']} %{subsequence_name} ${param_config['family']}",
            parameter_type=ParameterType.INT,
            lower=param_config['bounds'][0],
            upper=param_config['bounds'][1]
        )
    elif param_config['type'] == 'choice':
        return ChoiceParameter(
            name=f"{param_config['name']} %{subsequence_name} ${param_config['family']}",
            parameter_type=ParameterType.INT,
            values=param_config['values']
        )


#%%####### Create a parameter space from all the parameters ###################
def create_search_space(config_optim_path, list_subsequences_names):
    """
    Creates a search space by generating parameters for each subsequence.

    Parameters:
    - config_optim_path (str): The directory path where optimization parameter YAML files are stored.
    - list_subsequences_names (list of str): A list of subsequence names for which parameters need to be created.

    Returns:
    - list_params (list): A list of parameter objects created for each subsequence.
    """

    # Initialize an empty list to store parameters
    list_params = []

    # Iterate over each subsequence name provided
    for subsequence_name in list_subsequences_names:
        # Construct the path to the optimization parameters YAML file for the current subsequence
        path_optim_params = os.path.join(config_optim_path, f"optim_params_{subsequence_name}.yml")
        
        # Load the optimization parameters from the YAML file
        optim_params_config = load_yaml_config(path_optim_params)

        # Create parameters for each entry in the optimization parameters configuration
        parameters = [create_parameter(param, subsequence_name) for param in optim_params_config]
        
        # Extend the list of parameters with the newly created parameters
        list_params.extend(parameters)

    # Return the complete list of parameters
    return list_params