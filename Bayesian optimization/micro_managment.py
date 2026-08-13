###############################################################################
###### Bayesian Optimization program for painted potential: synthe ############
########################### Noam MANDIN ; 07/2025 #############################
###############################################################################
'''The Synthe class allows giving instructions to the synthesizer for the new 
modulation function.'''

#%%####### Import of the required libraries ###################################
import pyvisa as visa
import numpy as np
import os


#%%####### Constants and values ###############################################

#Paramètres du potentiel optique non moyenné
P = 17.3e-3       #Puissance du faisceau laser en W
lamb = 1064e-9      #Longueur d'onde du laser en m
w0 = 12.6e-6       #Taille du waist pinceau en m

#Paramètres de la modulation en fréquence du signal RF (injecté dans l'AOM) et donc de la modulation spatiale
h0 = 3*w0         #Amplitude de la modulation en m (taille du potentiel moyenné)
fper = 200e3         #Fréquence de la périodisation de la fonction de modulation (motif) en Hz
v0 = 2*h0*fper         #Vitesse de déplacement du pinceau en m/s
tl = ((2*h0)/(3*v0))        #Période de la fonction de modulation (motif) en s

########## Time discretization ##########

nb = 1000           #Nombre de pas dans la discrétisation
T = np.linspace(-tl, tl, nb) #Temps discrétisé qui nous intéresse [-tl;tl]


#%%####### Synthe class to interface with the synthesizer and communicate with it ########
class Synthe:
    ########## Class initialization
    def __init__(self, path_txt_files):
        self.path_txt_files = path_txt_files
        self.tl = tl
        
    ########## Function to load the parameter values
    def load_txt_files(self, path_txt_files):
        # Define the directory where results are stored
        param = [] 
        colonnes = []
        if os.path.exists(path_txt_files):          
            with open(path_txt_files, 'r') as fichier:
                lignes = fichier.readlines()
                for ligne in lignes: 
                    valeurs = ligne.strip().split('\t')
                    if not colonnes:
                        param = [[]for _ in valeurs]
                    for i, val in enumerate(valeurs):
                        val = np.char.replace(val, ',', '.')
                        val = val.astype(float)
                        param[i].append(val)    
            param = [float(x[0]) for x in param]  
        else:
            # If the file does not exist, it means no results were stored for this trial
            raise FileNotFoundError("No param file found for trial.")
        self.param = param     
        
    ########## Function to generate the arbitrary modulation function
    def arb_mod(self, *param):
        y=[]
        z=[]
        for j in T: # Generation of a 5th-order polynomial over the interval [-tl; tl]
            y.append(self.param[0]+ param[1]*(j/tl) + param[2]*(j/tl)**2 + param[3]*(j/tl)**3 + param[4]*(j/tl)**4 + param[5]*(j/tl)**5)
        for k in range(len(y)): # Normalization of the polynomial between -1 and 1 over the interval [-tl; tl]
            z.append(np.float32(2.* (y[k] - np.min(y))/(np.max(y)-np.min(y))-1.))
        return z
  
    ########## Function to send instructions to the synthesizer
    def synthe_shap(self):
        
        arbs1 = self.arb_mod(*self.param) # Fonction de modulation arbitraire
        sig = np.array(arbs1, dtype='f4') # Formatage des données pour le synthé
        sig = np.array(arbs1, dtype='f4')
        rm=visa.ResourceManager()
        inst = rm.open_resource('USB0::2391::19207::MY59002881::0::INSTR') # Identité du synthé
        name = "truc"
        fc = 40.0e6 # Fréquence centrale de la modulation en Hz
        #set timeout time (ms)
        inst.timeout = 10000
        
        #clear errors
        inst.write('*RST')
        inst.write('*CLS')

        #set byte order to little-endian
        inst.write('FORM:BORD SWAP')
        
        #clear volatile memory of source SOUR (can be SOUR1 if dual chanel)
        inst.write("SOUR1:DATA:VOL:CLE")
        
        #write the signal as arb waveform to the device
        # inst.write_binary_values(f'SOUR1:DATA:DAC {name},', sig, datatype='f4', is_big_endian=False)
        inst.write_binary_values('SOUR1:DATA:ARB '+name+',', sig,
                                 is_big_endian=False,
                                 )
        
        inst.write("*WAI") #make sure no other commands are executed unitl arb is done downloading
        # Select the arbitrary waveform
        inst.write('SOUR1:FUNC:ARB '+name)
        inst.write('MMEM:STOR:DATA "INT:\\'+name+'.arb"')
        
        # Load waveforms into volatile memory so they can be used in sequence
        inst.write('MMEM:LOAD:DATA "INT:\\'+name+'.arb"')
        
        # Set some parameters for the arb and output it
        inst.write('SOUR1:FUNC:ARB:SRATE '+str(600e6))
        inst.write('SOUR1:VOLT:OFFS 0')
        inst.write('SOUR1:FUNC ARB')
        inst.write('SOUR1:VOLT 0.1')
        print(inst.query('SYST:ERR?'))
        
        #############################################################
        ####Triggered burst setup
        #############################################################
        inst.write('TRIG:SOUR EXT') #trigger mode ##KEY for front panel, EXT for external
        
        inst.write('SOUR1:BURS:STAT OFF') #burst mod
        # inst.write('SOUR1:BURS:SOUR INT')
        inst.write('SOUR1:BURS:MODE GAT') #gated mode
        inst.write('SOUR1:BURS:GATE:POL INV')
        
        ####################################################################
        #####Prepare chan 2 to be modulated by chan 1
        ####################################################################
        inst.write('SOUR2:FUNC SIN') #waveform
        inst.write('SOUR2:FREQ:FIX '+str(fc))  #freq of the carrier
        inst.write('SOUR2:VOLT ' +str(0.9))  #amp of the carrier
        
        #####set mod of 2 by chan 1
        inst.write('SOUR2:FM:SOUR CH1')
        inst.write('SOUR2:FM:INT:FUNC ARB')
        fdev = self.param[6] #Profodeur de la modulation en fréquence
        inst.write('SOUR2:FM:DEV '+str(fdev)) 
        inst.write('SOUR2:FM:STATE ON')
        
        #clear message and set outputs on
        inst.write("DISP:TEXT ''")
        inst.write('OUTP1 ON')
        inst.write('OUTP2 ON')
        
        rm.close()


