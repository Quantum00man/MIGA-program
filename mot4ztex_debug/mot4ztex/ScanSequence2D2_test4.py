import os
import pickle
from Scantemplate import Ui_ScanSequence
from PyQt5 import QtWidgets
#QtGui, QtCore
import numpy as np
from random import shuffle
import datetime
import threading


migaPath='/Home/miga_lastversion/mot4ztex'
date = datetime.datetime.now()
dict1=dict(p0=[0],p1=[0],sequence='seq',scanName='scan0',parameter0='p0',parameter1='p1',dataPath=migaPath+'Data_analysis/'+str(date.year)+'/'+str(date.year)+'_'+str(date.month)+'/'\
        +str(date.year)+'_'+str(date.month)+'_'+str(date.day)) #K dictionary: collection of key-value pairs.



class ScanSequence(QtWidgets.QWidget): #K ScanSequence inherits fonctionalities of QtWidgets and QWidget classes.

    def __init__(self, parent=None): #K self: instance of the created class, parent: optional parameter with the default value "None".
        super(ScanSequence, self).__init__(parent=parent) #K super: call the parent class (QtWidgets or QWidget), then initialization of the "parent" parameter
        # set up the form class as a `ui` attribute
        self.ui = Ui_ScanSequence() #K Creation of an instance in Ui_ScanSequence assigned to ui (user interface) attribute in ScanSequence: an instance of Ui_ScanSequence manages the user interface elements for ScanSequence
        self.ui.setupUi(self) # ui : interface définie dans template, #K setupUi: method to initialize and set up the user interface.
        self.ui.startScan.clicked.connect(self.main) #K Connect the clicked signal of button "startScan" (within the interface) to the main of ScanSequence.  


    def main(self):
        self.updateDict1() #K update dict1
        if self.ui.shuffle.isChecked() : #K : is the shuffle checkbox (created in Ui__ScanSequence) is checked?
            shuffle(dict1['p0']) #K the method shuffle is applied to the p0 parameter of dict1 (all the parameters given y the users are mixed: they won't be applied in a specific order)
            shuffle(dict1['p1'])
        if os.path.exists(f'{dict1["dataPath"]}/{dict1["scanName"]}Text_Sequence.txt'): #K Is the file 'Sequence' (taking from the file path found in dict1) exist?
            returnValue=self.ui.scanOverwrite.exec_() #K Give a dialog window with the operator, returnValue is the value indicated by the operator
            if returnValue==16384:
                #self.saveSequence(dict1["sequence"])
                #self.shareValue(dict(scanName=dict1['scanName'],parameter0=dict1['parameter0'],parameter1=dict1['parameter1'],val0=0,val1=0)) #K a value is given
                threading.Thread(target=self.scan).start()  #K allows to run scan in background, while the main continue to be executed.
            else :
                pass
        else :
                #self.saveSequence(dict1["sequence"])
                #self.shareValue(dict(scanName=dict1['scanName'],parameter0=dict1['parameter0'],parameter1=dict1['parameter1'],val0=0,val1=0))
                threading.Thread(target=self.scan).start()


    def scan(self): #K Scan and give values to the interface
        for i,val1 in enumerate(dict1['p1']): #K the for is applied on the dict1 elements (i: index, val1: value)
            for j,val0 in enumerate(dict1['p0']):
                print(f'val0={val0},val1={val1}') #K print values corresponding to p0 and p1
                self.ui.progress.setValue(i*len(dict1['p0'])+j+1) #K Set the value of setValue in the progress bar (expression i*len(dict1['p0'])+j+1) widget within the interface
                self.writeSeq(sequence=dict1['sequence'],val0=val0,val1=val1) #K Complete the sequence with val1 and val2 as param0 and param1.
                os.system('rm /var/lock/mot4')
                os.system('./tmot4 -f MIGA_II_sequence_DDSChange_test_final.mot')
        
                #self.shareValue(dict(scanName=dict1['scanName'],parameter0=dict1['parameter0'],parameter1=dict1['parameter1'],val0=val0,val1=val1))

    def updateDict1(self): #K Update dict1 with values given by the user (start, end and delta)
        dict1['p0']=[i for i in range(self.ui.startValue0.value(),self.ui.endValue0.value()+1,self.ui.deltaValue0.value())]
        dict1['p1']=[i for i in range(self.ui.startValue1.value(),self.ui.endValue1.value()+1,self.ui.deltaValue1.value())]
        dict1['sequence']=self.ui.sequence.text()
        dict1['parameter0']=self.ui.scanedParameter0.text()
        dict1['parameter1']=self.ui.scanedParameter1.text()
        dict1['scanName']=self.ui.scanName.text()
        date = datetime.datetime.now()
        dict1['dataPath']=migaPath+'Data_analysis/'+str(date.year)+'/'+str(date.year)+'_'+str(date.month)+'/'\
        +str(date.year)+'_'+str(date.month)+'_'+str(date.day)
        self.ui.progress.setMaximum(len(dict1['p0'])*len(dict1['p1']))
        if not os.path.exists(dict1['dataPath']):
            os.makedirs(dict1['dataPath'])
            
    def writeSeq(self,sequence,val0,val1,param1=1,param0=0) : #K Complete the sequence with values given by the user.
        os.system('cp '+sequence+'.mot ./MIGA_II_sequence_DDSChange_test_intermediaire.mot')
        os.system(f'sed -i "s/<PARAMETER{param0}>/{val0}/" ./MIGA_II_sequence_DDSChange_test_intermediaire.mot')
        os.system(f'sed -i "s/<PARAMETER{param1}>/{val1}/" ./MIGA_II_sequence_DDSChange_test_intermediaire.mot')
        os.system('cp ./MIGA_II_sequence_DDSChange_test_intermediaire.mot ./MIGA_II_sequence_DDSChange_test_final.mot')
        
    #def saveSequence(self,sequence): #K Save the sequence in f.
        #with open(f'{sequence}.mot','r')as f:
            #seqTemp=f.read()
        #with open(f'{dict1["dataPath"]}/{dict1["scanName"]}Text_Sequence.txt','w') as f:
            #f.write(seqTemp)

    #def shareValue(self,param): #K Give scan values??
        #with open (f'{migaPath}/Softwares/SharedFiles/scanP0Value.dat','wb') as f:
            #pickle.dump(param,f,3) #K Serialize and save the object param into the file f.
            #print(param)


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    widget = ScanSequence()
    widget.show()
    app.exec_()