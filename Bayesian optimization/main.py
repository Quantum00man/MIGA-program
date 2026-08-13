###############################################################################
####### Bayesian Optimization program for painted potential: main #############
########################### Noam MANDIN ; 07/2025 #############################
###############################################################################
'''The main program of the Bayesian Optimisation. This is the program that is 
executed to perform the optimization.'''

#%%####### Import of the required libraries ###################################

import numpy as np
import matplotlib.pyplot as plt
import os
import ast
from scipy import signal as sig #Used to create a square function
from scipy import integrate as intg #Used for integration

#The ax library is the one that enables Bayesian optimization
from ax.core import (ParameterType,
                     RangeParameter,
                     SearchSpace,
                     OptimizationConfig, 
                     Objective,
                     Experiment,
                     Arm) 
from ax.modelbridge.factory import Models
#The main program is central and therefore calls classes from other programs
from painted_potential_experiment import PPExperiment, PPRunner 
from fct_cout import ECART
from helpers import create_result_directory, create_search_space


#%%####### Creation of paths to store the results and to locate access to the 
# parameter configuration and the detection VI ################################

# Temporary results file
result_directory = "C://Users//Rb//Desktop//stage_noam//painted_potential//results//data.txt"

# Create a directory to store optimization results
'''Each time this program is executed in full, the Bayesian optimization 
algorithm runs from start to finish. The results of each trial are saved in a 
file with the following type of path:
"C:\Users\Rb\Desktop\stage_noam\painted_potential\results\optim_example_{num_execution}\trial_{num_trial}\{arm_name}\data".
For example, if I run this program for the 64th time and want to check the 54th 
trial, the file path will be: 
"C:\Users\Rb\Desktop\stage_noam\painted_potential\results\optim_example_64\trial_54\54_0\data".
'''

new_directory = "C:\\Users\\Rb\\Desktop\\stage_noam\\painted_potential\\results\\optim_example"
new_directory = create_result_directory(new_directory)

# Specifying the location of the detection VI
vi_camera_path = "C:\\Users\\Rb\\Desktop\\stage_noam\\painted_potential\\LabVIEW\\optiB.vi"

# Specifying the location of the parameter temporary file
path_txt_files = "C://Users//Rb//Desktop//stage_noam//painted_potential//results//config.txt"

#%%####### Create the search space from a configuration file ##################

# Specifying the location of the parameter configuration files
config_optim_path = "C://Users//Rb//Desktop//stage_noam//painted_potential//param//"

# Creation of the parameter space
all_optim_params = create_search_space(config_optim_path, ['a0', "a1", 'a2', 'a3', 'a4', 'a5', 'a6'])

# The space in which we search for the best configuration is the parameter space
search_space = SearchSpace(parameters=all_optim_params)

#%%####### Initialize the cold atom experiment control interface ##############

pp_experiment = PPExperiment(
                             vi_camera_path,
                             path_txt_files,
                            )

#%%####### Define the optimization configuration ##############################

#It is there, but I’m not really sure why, actually.
param_cible = [0, 1, 0, 0, 0, 0, 4000000]

optimization_config = OptimizationConfig(
                                         objective=Objective(
                                                             metric = ECART(pp_experiment, new_directory, param_cible),
                                                             minimize = True  # Maximizing the objective
                                                            )
                                        )

#%%####### Create the experiment and define a runner ##########################

experiment = Experiment(
                        name="Draft",
                        search_space=search_space,
                        optimization_config=optimization_config,
                        runner=PPRunner(pp_experiment, result_directory, new_directory, vi_camera_path, path_txt_files),
                       )

#%%####### Initial loop parameters ###################################

initial_params = {'a0':0.,
                  'a1':1.,
                  'a2':0.,
                  'a3':0.,
                  'a4':0.,
                  'a5':0.,
                  'a6':4000000
                  }

#%%####### Run an initial trial with starting parameters ######################

trial = experiment.new_trial()
trial.add_arm(Arm(parameters=initial_params, name="initial_trial"))
trial.run()
trial.mark_completed()

#%%####### Set the number of trials ###########################################

NUM_SOBOL_TRIALS = 5    # Random exploration trials
NUM_BOTORCH_TRIALS = 5  # Bayesian optimization trials

#%%####### Phase 1: Random exploration using Sobol sequences ##################

print('----------------------------------')
print("Starting Sobol initialization trials...")
sobol = Models.SOBOL(search_space=experiment.search_space)
#Exploration loop executed NUM_SOBOL_TRIALS times
for i in range(NUM_SOBOL_TRIALS): 
    print(f"Running Sobol trial {i + 1}/{NUM_SOBOL_TRIALS}")
    trial = experiment.new_trial(generator_run=sobol.gen(1))
    trial.run()
    trial.mark_completed()
print("End of Sobol trials...")
print('----------------------------------')

#%%####### Phase 2: Bayesian optimization using GP-EI #########################

print('----------------------------------')
print("Starting Bayesian optimisation trials...")
best_arm = None
#Optimization loop executed NUM_BOTORCH_TRIALS times
for i in range(NUM_BOTORCH_TRIALS):
    print(f"Running GP-EI trial {i + 1}/{NUM_BOTORCH_TRIALS}")
    gpei = Models.BOTORCH_MODULAR(experiment=experiment, data=experiment.fetch_data())
    generator_run = gpei.gen(1)
    best_arm, _ = generator_run.best_arm_predictions # Les paramètres qui ont donné le meilleur try jusqu'ici, sont sauvegardés
    trial = experiment.new_trial(generator_run=generator_run)
    trial.run()
    trial.mark_completed()
print("End of Bayesian optimisation trials...")
print('----------------------------------')
print("Optimization completed!")
# Bayesian optimization is finished

#%%####### Retrieve the best parameters found #################################

best_parameters = best_arm.parameters
best_param = []
print("Best parameters found:")
# Print the best parameters
for param, value in best_parameters.items():
    best_param.append(value)
    print(f"  {param}: {value}")

'''A final trial is run with the best parameters. This way, the temporary file 
data.txt contains the best intensity profile that can be achieved. The best 
parameters are also displayed.'''

best_params = {'a0':best_param[0],
                  'a1':best_param[1],
                  'a2':best_param[2],
                  'a3': best_param[3],
                  'a4':best_param[4],
                  'a5':best_param[5],
                  'a6':best_param[6],
                  }

trial = experiment.new_trial()
trial.add_arm(Arm(parameters=best_params, name="best_trial"))
trial.run()
trial.mark_completed()

#%%####### Calculs de fonction de modulation et de profils d'intensité ########

# Constantes et valeurs nécessaire aux calculs
fper = 90e3
P = 17.3e-3
w0 = 13e-6
h0 = 3*w0
v0 = 2*h0*fper
tl = ((2*h0)/(3*v0)) 
nb = 1000
x = np.linspace(-(h0+w0), (h0+w0), nb)
T = np.linspace(-tl, tl, nb)


########## Défintion des fonctions de modulations ##########
def f_t(t, *param): #Fonction de modulation quelconque définie par des paramètres
    y = param[0] + param[1]*(t/tl) + param[2]*(t/tl)**2 + param[3]*(t/tl)**3 + param[4]*(t/tl)**5 + param[5]*(t/tl)**7
    return y

def xi(t):      #Définition de la fonction atroce normalisée de -1 à 1 et de période 2*tl
    y1 = (1/2)*np.real(  ((1 - 1j*np.sqrt(3))*((2*(t+tl/2)/tl) - 1j*np.sqrt(1 - (2*(t+tl/2)/tl)**2))**(1/3)) + ((1 + 1j*np.sqrt(3))*((2*(t+tl/2)/tl) + 1j*np.sqrt(1 - (2*(t+tl/2)/tl)**2))**(1/3))  )
    y2 = -(1/2)*np.real(  ((1 - 1j*np.sqrt(3))*((2*(t-tl/2)/tl) - 1j*np.sqrt(1 - (2*(t-tl/2)/tl)**2))**(1/3)) + ((1 + 1j*np.sqrt(3))*((2*(t-tl/2)/tl) + 1j*np.sqrt(1 - (2*(t-tl/2)/tl)**2))**(1/3))  )
    return np.where(t<0, y1, y2)

def carre(t):   #Définition de la fonction carré normalisée de -1 à 1 et de période 2*tl
    y = sig.square(t*np.pi/tl)
    return y


########## Définition des profils d'intensités ##########
def f_x(x, *param): # Profil d'intensité quelconque défini par des paramètres
    y = param[0] + param[1]*(x/h0) + param[2]*(x/h0)**2 + param[3]*(x/h0)**3 + param[4]*(x/h0)**5 + param[5]*(x/h0)**7
    return y

def Int_moy(x): # Fonction qui calcul un profil d'intensité sur un axe de l'espace à partir d'une fonction de modulation
   Ix =[]
   for i in (x):
       I0 = (2*P)/(np.pi*w0**2) #Calcul de I0 l'intensité du faisceau laser
       Ix.append( I0*intg.quad(lambda t: np.exp(-2*((i-h0*xi(t))**2)/w0**2), -tl, tl)[0] )      
   return Ix

def xcarre(x): # Fonction qui défini un potentiel harmonique avec un polynôme carré
    y = - (x/h0)**2 + 1
    return y

def xsix(x): # Fonction qui défini un potentiel plat avec un polynôme d'ordre 6
    y = - (x/h0)**6 + 1
    return y


# Function to retrieve the results from the temporary file data.txt
def retrieve_results(trial_index, best_trial, new_directory):
    # Define the list where results are stored
    profil = []
    # Define the files path for this particular trial's results     
    files_path = os.path.join(new_directory, f"trial_{trial_index}", f"{best_trial}", "data.txt")
    if os.path.exists(files_path):
        with open(files_path, 'r') as fichier:
            profil = fichier.read()
            profil = ast.literal_eval(profil) # Retrieves the data from data.txt and saves it in the "profil" list                   
    else:
        # If the file does not exist, it means no results were stored for this trial
        raise FileNotFoundError("No results file found for trial.")
    return profil

'''Since the last try of the algorithm uses the best parameters, the data.txt 
file contains a list corresponding to the points of the intensity profile 
closest to the target profile according to the Bayesian optimization.'''
profil = retrieve_results(NUM_SOBOL_TRIALS + NUM_BOTORCH_TRIALS + 1, "best_trial", new_directory)

#%%####### Display of the results #############################################
'''Avant d'afficher, il faut normaliser tous les profils d'intensités (que ce 
soit calculés ou mesurés) et les fonctions de modulation. De cette 
façon, on peut réellement comparer les profils entre eux.'''

#Normalisation des profils d'intensités calculés et mesurés entre 0 et 1
profil_norm = (profil - np.min(profil) ) /  (  np.max(profil) - np.min(profil))
Int_moy_norm = (Int_moy(x) - np.min(Int_moy(x)) )  /  (  np.max(Int_moy(x)) - np.min(Int_moy(x)))
xcarre_norm = (xcarre(x) - np.min(xcarre(x)) ) /  (  np.max(xcarre(x)) - np.min(xcarre(x)))
xsix_norm = (xsix(x) - np.min(xsix(x)) ) /  (  np.max(xsix(x)) - np.min(xsix(x)))

# Normalisation de la fonction de modulation entre -1 et 1
f_t_norm = 2.* (f_t(T, *np.array(best_param)) - np.min(f_t(T, *np.array(best_param))))/(np.max(f_t(T, *np.array(best_param)))-np.min(f_t(T, *np.array(best_param))))-1.

#Plot de deux figures
fig, ax = plt.subplots(1, 2, figsize=(12, 8))

#Affichage des fonctions de modulations (à gauche)
ax[0].plot(T, xi(T), 'b-')
ax[0].plot(T, f_t_norm, 'r-')
ax[0].set_xlim(-1*tl,1*tl)
ax[0].set_ylim(-1,1)
ax[0].set_xlabel('Temps en s')
ax[0].set_ylabel('Position selon x')

#Affichage des courbes de profils d'intensités (à droite)
#ax[0].plot(x, Int_moy(x), 'b-')
#ax[0].plot(x, xcarre(x), 'b-')
ax[0].plot(x, xsix(x), 'b-')
ax[0].plot(np.linspace(-51.6e-6, 51.6e-6, len(profil_norm)), profil_norm, 'r-')
ax[0].set_xlabel('x en m')
ax[0].set_ylabel('Profil dintensité normalisé à 1')
ax[0].set_ylim(0, 1.1)

plt.show(block=0)

