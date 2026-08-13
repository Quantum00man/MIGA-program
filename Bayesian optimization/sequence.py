###############################################################################
##### Bayesian Optimization program for painted potential: Sequence ###########
########################### Noam MANDIN ; 07/2025 #############################
###############################################################################
'''La class Sequence définie plusieurs fonction. Chacune des fonction 
correspond à une action dans la boucle. Ces fonctions sont appelés dans le 
programme painted_potential_experiement dans la class PPrunner.'''

#%%####### Import of the required libraries ###################################
import re
import numpy as np
from synthe import Synthe


#%%####### Constants and values ###############################################
#Paramètres du potentiel optique non moyenné
P = 17.3e-3       #Puissance du faisceau laser en W
lamb = 1064e-9      #Longueur d'onde du laser en m
w0 = 12.6e-6       #Taille du waist pinceau en m

#Parameters of the frequency modulation of the RF signal (injected into the AOM) and therefore of the spatial modulation
h0 = 3*w0         #Amplitude de la modulation en m (taille du potentiel moyenné)
fper = 200e3         #Fréquence de la périodisation de la fonction de modulation (motif) en Hz
v0 = 2*h0*fper         #Vitesse de déplacement du pinceau en m/s
tl = ((2*h0)/(3*v0))        #Période de la fonction de modulation (motif) en s

########## Time discretization ##########

nb = 1000           #Nombre de pas dans la discrétisation
T = np.linspace(-tl, tl, nb) #Temps discrétisé qui nous intéresse [-tl;tl]


#%%####### Sequence class that defines every little part of the loop ##########
class Sequence:
    
    ########## Class initialization
    def __init__(self, path_txt_files):
        
        self.path_txt_files = path_txt_files
        self.synthe = Synthe(self.path_txt_files)
        self.synthe.load_txt_files(self.path_txt_files)

    ########## Function that updates each parameter with the new value after computing the cost function

    def update_param_with_new_param(self, param_name, path_txt_files, new_param):
        
        if param_name=="a0":
            update = new_param
        elif param_name=="a1":
            update = new_param
        elif param_name=="a2":
            update = new_param
        elif param_name=="a3":
            update = new_param
        elif param_name=="a4":
            update = new_param
        elif param_name=="a5":
            update = new_param
        elif param_name=="a6":
            update = new_param
        return update
       
    ########## Loads the new parameters and applies them in the 
    # parameterization of the new modulation function

    def single_run(self, path_txt_files):
        self.synthe.load_txt_files(path_txt_files)
        self.synthe.synthe_shap()
    
    ########## Loads the new parameters into the parameter buffer file
    def update_sequence_parameters(self, arm_parameters, path_txt_files):
        update=[]
        pattern = r"(a\d+)"
        # Parameter's name 
        # Example: we put 0.5 on a2    
        # 'a2': 0.5
        for param_key, param_value in arm_parameters.items():
            match = re.search(pattern, param_key)
            if match:
                param_name = match.group(1)
            else:
                print("No match found")
                return
            j = self.update_param_with_new_param(param_name, path_txt_files, param_value)
            update.append(j)
        with open(path_txt_files, "w", encoding="utf-8") as f:
            for x in update:
                f.write(f"{x} \t")
        
