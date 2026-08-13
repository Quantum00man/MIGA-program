###############################################################################
######### Bayesian Optimization program for painted potential: ################
############ painted_potential_experiment - Noam MANDIN ; 07/2025 #############
###############################################################################
'''Program for defining the experimentation and the Bayesian algorithm loop. To 
do this, the camera VI must first be interfaced with Python. Then, a sequence 
of actions that the program must perform in order is defined. Each action 
corresponds to a part of the loop.'''

#%%####### Import of the required libraries ###################################
import win32com.client
import os
import numpy as np
from ax import Runner
from Sequence import Sequence


#%%####### PointGrey camera class #############################################
class CameraPointGrey:
    ########### Initialization of the CameraPointGrey class ###################
     def __init__(self, labview, vi_path):
         try:
             self.control_vi = labview.getvireference(vi_path)
         except:
             print("Labview not connected -- Starting with no Camera VI")
     ########## Function to capture an image with the camera ##################
     def take_image(self)->None:
         self.control_vi._FlagAsMethod('Run')
         self.control_vi.Run()


#%%####### PPExperiment class that defines the experimentation and the LabVIEW interfacing
class PPExperiment:
    ########## Initializes the experimentation with the necessary file paths ##
    def __init__(self, vi_camera_path, path_txt_files) -> None:
        '''vi_camera_path = path of the VI that handles image capture with the 
        camera
        path_txt_files = path of the temporary file where the parameters chosen 
        by the algorithm are saved for each trial'''
        # Initialize LabView application
        self.labview = win32com.client.Dispatch("LabVIEW.Application")
        # Initialize Sequence device
        self.sequence = Sequence(path_txt_files)
        # Initialize Detection device
        self.detection = CameraPointGrey(labview = self.labview, vi_path=vi_camera_path)
        try:
            # Load and process sequence data from text files
            Sequence.single_run(path_txt_files)
        except:
            print("No txt files loaded -- only estimator available")
            
    # Function that calls a method of the Sequence class to modify the parameters in the temporary file
    def update_sequence_params(self, sequence_params):
        self.sequence.update_sequence_parameters(self, sequence_params)
        
    # Function that instructs the detection VI to execute in order to capture an image
    # The important data associated with this image is saved in a data.txt file
    def take_image(self):
        self.detection.take_image()


#%%####### Function to extract the data from data.txt and store it as a list of floats in the trial file
def store_results(result_directory, new_directory, trial_index, arm_name):
    # Define the directory where results are stored
    profil = []
    # Define the files path for this particular trial's results    
    files_path = result_directory
    new_files_path = os.path.join(new_directory, f"trial_{trial_index}", arm_name)    
    os.makedirs(new_files_path, exist_ok=True)
    new_txt_files = os.path.join(new_files_path, "data.txt")
    colonnes = []
    if os.path.exists(files_path):
        with open(files_path, 'r') as fichier:
            lignes = fichier.readlines()
            for ligne in lignes: 
                valeurs = ligne.strip().split('\t')
                if not colonnes:
                    profil = [[]for _ in valeurs]
                    for i, val in enumerate(valeurs):
                        val = np.char.replace(val, ',', '.')
                        val = val.astype(float)
                        profil[i].append(val)
        profil = [float(x[0]) for x in profil]
    else:
        # If the file does not exist, it means no results were stored for this trial
        raise FileNotFoundError("No results file found for trial.")   
    with open(new_txt_files, "w", encoding="utf-8") as f:
        f.write(str(profil))
            
    return profil # This return serves no purpose; it is there simply because one is required.

#%%####### PPrunner class that defines the runner to execute, one by one and in 
# order, each small sequence corresponding to a step of the Bayesian algorithm loop
class PPRunner(Runner):
    ########## Initializes the runner with all file paths, application paths, and sequences
    def __init__(self, experiment, result_directory, new_directory, vi_camera_path, path_txt_files):
        # Initialize the runner with an experiment and a directory to store results
        self.result_directory = result_directory
        self.new_directory = new_directory
        self.path_txt_files = path_txt_files
        self.experiment = experiment
        self.vi_camera_path = vi_camera_path
        self.labview = win32com.client.Dispatch("LabVIEW.Application")
        self.control_vi = self.labview.getvireference(self.vi_camera_path)
        self.sequence = Sequence(self.path_txt_files)
    ########## Performs a loop of the Bayesian algorithm
    def run(self, trial):
        # Iterate over each arm in the trial
        for arm_name, arm in trial.arms_by_name.items():
            # Update the experiment's sequence parameters with the current arm's parameters
            self.sequence.update_sequence_parameters(arm.parameters, self.path_txt_files)
            # load the the arbitrary waveform in synthe
            self.sequence.single_run(self.path_txt_files)
            # Print the parameters of the current arm for debugging purposes
            print("*** Arm parameters : ", arm.parameters)
            # Execute the experiment's sequence and capture the last image
            self.experiment.take_image()
            # Store the result of the optimization in the specified directory
            store_results(self.result_directory, self.new_directory, trial.index, arm_name)
        # Return an empty dictionary as the result of the run
        return {}
