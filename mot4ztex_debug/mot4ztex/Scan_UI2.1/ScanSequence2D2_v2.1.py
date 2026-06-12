import os
import pickle
from PyQt5 import QtWidgets, QtCore, uic
import numpy as np
from random import shuffle
import datetime
import threading

migaPath = '/Home/miga_lastversion/mot4ztex'
date = datetime.datetime.now()
dict1 = dict(
    p0=[0], p1=[0], sequence='seq', scanName='scan0', parameter0='p0', parameter1='p1',
    dataPath=migaPath + 'Data_analysis/' + str(date.year) + '/' + str(date.year) + '_' + str(date.month) + '/' + str(date.year) + '_' + str(date.month) + '_' + str(date.day)
)

# Load the UI definition
Ui_ScanSequence, _ = uic.loadUiType("scan.ui")
redpit_address={'red':'root@192.168.2.5','green':'root@192.168.3.5'}
redpit_pass={'red':'root','green':'root'}
redpit_gains={'red':np.array([1,1]),'green':np.array([1,1])}

class ScanSequence(QtWidgets.QWidget, Ui_ScanSequence):

    updateProgress = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super(ScanSequence, self).__init__(parent=parent)
        self.setupUi(self)
        self.startScan.clicked.connect(self.main)
        self.updateProgress.connect(self.progress.setValue)

    def main(self):
        self.updateDict1()
        if self.shuffle.isChecked():
            shuffle(dict1['p0'])
            shuffle(dict1['p1'])
        if os.path.exists(f'{dict1["dataPath"]}/{dict1["scanName"]}Text_Sequence.txt'):
            returnValue = self.scanOverwrite.exec_()
            if returnValue == 16384:
                threading.Thread(target=self.scan).start()
            else:
                pass
        else:
            threading.Thread(target=self.scan).start()

    def scan(self):

        for i, val1 in enumerate(dict1['p1']):
            for j, val0 in enumerate(dict1['p0']):
                print(f'val0={val0},val1={val1}')
                self.updateProgress.emit(i * len(dict1['p0']) + j + 1)
                self.writeSeq(sequence=dict1['sequence'], val0=val0, val1=val1)
                os.system('rm /var/lock/mot4')
                os.system('/home/miga/miga_lastversion/mot4ztex/tmot4 -f MIGA_II_sequence_DDSChange_test_final.mot')
                try:
                    os.system('wget -qO- '+redpit_address['green']+':8000/ch1.dat > ch1.dat')
                    os.system('wget -qO- '+redpit_address['green']+':8000/ch2.dat > ch2.dat')
                    # add a time stamp to the ch1.dat file
                    with open('temp/green1.dat', 'w') as file1:
                        file1.write(str(time.time())+'\n')
                    os.system('cat temp/ch1.dat >> temp/green1.dat')
                    # add a time stamp to the ch2.dat file
                    with open('temp/green2.dat', 'w') as file1:
                        file1.write(str(time.time())+'\n')
                    os.system('cat temp/ch2.dat >> temp/green2.dat')
                    green=True
                except:
                    print('unable to fetch data from greenpitaya '+redpit_address['green']+''),
                    green=False

    def updateDict1(self):
        dict1['p0'] = [i for i in range(self.startValue0.value(), self.endValue0.value() + 1, self.deltaValue0.value())]
        dict1['p1'] = [i for i in range(self.startValue1.value(), self.endValue1.value() + 1, self.deltaValue1.value())]
        dict1['sequence'] = self.sequence.text()
        dict1['parameter0'] = self.scanedParameter0.text()
        dict1['parameter1'] = self.scanedParameter1.text()
        dict1['scanName'] = self.scanName.text()
        date = datetime.datetime.now()
        dict1['dataPath'] = migaPath + 'Data_analysis/' + str(date.year) + '/' + str(date.year) + '_' + str(date.month) + '/' + str(date.year) + '_' + str(date.month) + '_' + str(date.day)
        self.progress.setMaximum(len(dict1['p0']) * len(dict1['p1']))
        if not os.path.exists(dict1['dataPath']):
            os.makedirs(dict1['dataPath'])

    def writeSeq(self, sequence, val0, val1, param1=1, param0=0):
        os.system('cp ' + sequence + '.mot ./MIGA_II_sequence_DDSChange_test_intermediaire.mot')
        os.system(f'sed -i "s/<PARAMETER{param0}>/{val0}/" ./MIGA_II_sequence_DDSChange_test_intermediaire.mot')
        os.system(f'sed -i "s/<PARAMETER{param1}>/{val1}/" ./MIGA_II_sequence_DDSChange_test_intermediaire.mot')
        os.system('cp ./MIGA_II_sequence_DDSChange_test_intermediaire.mot ./MIGA_II_sequence_DDSChange_test_final.mot')
        
        


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    widget = ScanSequence()
    widget.show()
    app.exec_()
