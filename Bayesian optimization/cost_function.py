###############################################################################
##### Bayesian Optimization program for painted potential: fct_cout ###########
########################### Noam MANDIN ; 07/2025 #############################
###############################################################################
'''Cost function calculation program. The calculation is performed in the ECART 
class. The ECART class is called in the main program within the 
OptimizationConfig function of the ax library. The algorithm's objective is to 
minimize the result of this calculation.'''

#%%####### Import of the required libraries ###################################

import ast
import os
import pandas as pd
import numpy as np
from scipy import integrate as intg
from scipy import signal as sig
from ax import Metric
from ax.core.data import Data
from ax.utils.common.result import Ok


#%%####### Constants and values ###############################################

#Unaveraged optical potential parameters
P = 17.3e-3       #Laser beam power in W
lamb = 1064e-9      #Wavelenght of the laser in m
w0 = 12.6e-6       #Size of the waist pinceau in m

#RF signal frequency modulation parameters (injected into the AOM) and thus the spatial modulation
h0 = 3*w0         #Amplitude de la modulation en m (taille du potentiel moyenné)
fper = 200e3         #Fréquence de la périodisation de la fonction de modulation (motif) en Hz
v0 = 2*h0*fper         #Vitesse de déplacement du pinceau en m/s
tl = ((2*h0)/(3*v0))        #Période de la fonction de modulation (motif) en s

########## Time discretization ##########

nb = 1000           #Nombre de pas dans la discrétisation
T = np.linspace(-tl, tl, nb) #Temps discrétisé qui nous intéresse [-tl;tl]


#%%####### Cost function class ################################################

class ECART(Metric):
    
    ########### Initialization of the ECART class as the metric on which the Bayesian algorithm relies
    def __init__(self, experiment, new_directory, param_cible, name="ecart"):
        super().__init__(name=name)
        self.new_directory = new_directory # The path to the measured intensity profile data
        self.experiment = experiment # Not useful I think
        self.tl = tl
        self.h0 = h0
        self.param_cible = param_cible
    
    ########### Calculation of the modulation function to define a target averaged intensity profile
    def xi(self, t):      # Définition de la fonction atroce normalisée à h0 et tl
        y1 = (1/2)*np.real(  ((1 - 1j*np.sqrt(3))*((2*(t+self.tl/2)/self.tl) - 1j*np.sqrt(1 - (2*(t+self.tl/2)/self.tl)**2))**(1/3)) + ((1 + 1j*np.sqrt(3))*((2*(t+self.tl/2)/self.tl) + 1j*np.sqrt(1 - (2*(t+self.tl/2)/self.tl)**2))**(1/3))  )
        y2 = -(1/2)*np.real(  ((1 - 1j*np.sqrt(3))*((2*(t-self.tl/2)/self.tl) - 1j*np.sqrt(1 - (2*(t-self.tl/2)/self.tl)**2))**(1/3)) + ((1 + 1j*np.sqrt(3))*((2*(t-self.tl/2)/self.tl) + 1j*np.sqrt(1 - (2*(t-self.tl/2)/self.tl)**2))**(1/3))  )
        return np.where(t<0, y1, y2)

    def carre(self, t):   # Définition de la fonction carré normalisée à tl
        y = sig.square(t*np.pi/self.tl)
        return y

    ########## Calculation of the target averaged intensity profiles ##################
    def Int_moy(self, x): # Fonction qui calcul un profil d'intensité sur un axe de l'espace à partir d'une fonction de modulation
        Ix =[]
        for i in (x):
            I0 = (2*P)/(np.pi*w0**2) #Calcul de I0 l'intensité du faisceau laser
            Ix.append( I0*intg.quad(lambda t: np.exp(-2*((i-h0*self.xi(t))**2)/w0**2), -tl, tl)[0] )  
            #Ix.append( I0*intg.quad(lambda t: np.exp(-2*((i-h0*self.carre(t))**2)/w0**2), -tl, tl)[0] )
        return Ix
    
    def xcarre(self, x): # Fonction qui défini un potentiel harmonique avec un polynôme carré
        y = -(x/h0)**2 + 1
        return y
    
    def xsix(self, x): # Fonction qui défini un potentiel plat avec un polynôme d'ordre 6
        y = -(x/h0)**6 + 1
        return y
    
    ########## Definition of the cost function: the Mean Square Error (MSE) ###
    def MSE(self, x, profil):  # The MSE is defined for different target profiles: here, there are 3 different ones
        #mse = np.mean((np.array((( self.Int_moy(x) - np.min(self.Int_moy(x)) )  /  (  np.max(self.Int_moy(x)) - np.min(self.Int_moy(x)))) )  -  np.array((( profil - np.min(profil) )  /  (  np.max(profil) - np.min(profil)))))**2)
        #mse = np.mean(   (  np.array((( self.xcarre(x) - np.min(self.xcarre(x)) )  /  (  np.max(self.xcarre(x)) - np.min(self.xcarre(x)))) )  -  np.array((( profil - np.min(profil) )  /  (  np.max(profil) - np.min(profil))))  )**2   )
        mse = np.mean(   (  np.array((( self.xsix(x) - np.min(self.xsix(x)) )  /  (  np.max(self.xsix(x)) - np.min(self.xsix(x)))) )  -  np.array((( profil - np.min(profil) )  /  (  np.max(profil) - np.min(profil))))  )**2   )
        print (mse)
        return mse

    ########## Function called by the main program to return data #############
    def fetch_trial_data(self, trial,**kwargs):
        records = []
        for arm_name, arm in trial.arms_by_name.items():
            # Extracting the result from trial metadata
            profil = retrieve_results(trial.index, arm_name, self.new_directory)
            # Mapping each element of the list to a real position on the x-axis
            '''Le calcul est le suivant : lim = (nombre_pixel*taille_pixel)/2 avec 
            nombre_pixel = arrondi_supérieur(taille_profil/taille_pixel). L'intervalle 
            est donc [-lim ; lim] avec un nombre de pas égal au nombre de pixel.
            Le nombre de pixel correspond à la taille de la liste correspondant au profil'''
            x = np.linspace(-51.6e-6, 51.6e-6, np.size(profil))
            # Calculation of the MSE cost function
            ecart = self.MSE(x, profil)
            records.append({"arm_name": arm_name, 
                            "metric_name": self.name, # Metric name
                            "mean": ecart, # Value of the cost function calculation
                            "sem": 0,  # Standard error of the mean
                            "trial_index": trial.index, # Trial number
                            })
        data = Data(df=pd.DataFrame.from_records(records))
        return Ok(data)
    '''The fetch_trial_data function returns the metric name, the cost function 
    value, and its weight for a particular trial with its set of parameters.'''


#%%####### Retrieve the results of a trial ####################################

def retrieve_results(trial_index, arm_name, new_directory):
    # Define the directory where results are stored
    profil = []
    # Define the files path for this particular trial's results
    files_path = os.path.join(new_directory, f"trial_{trial_index}", f"{arm_name}", "data.txt")
    if os.path.exists(files_path):
        with open(files_path, 'r') as fichier:
            profil = fichier.read()
            profil = ast.literal_eval(profil) # Retrieves the data from data.txt and stores it in the "profil" list                        
    else:
        # If the file does not exist, it means no results were stored for this trial
        raise FileNotFoundError("No results file found for trial.")
    return profil
