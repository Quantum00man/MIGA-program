import os
import pickle
from Scantemplate import Ui_ScanSequence
from PyQt5 import QtWidgets, QtCore
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


class ScanSequence(QtWidgets.QWidget):

    updateProgress = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super(ScanSequence, self).__init__(parent=parent)
        self.ui = Ui_ScanSequence()
        self.ui.setupUi(self)
        self.ui.startScan.clicked.connect(self.main)
        self.updateProgress.connect(self.ui.progress.setValue)

    def main(self):
        self.updateDict1()
        if self.ui.shuffle.isChecked():
            shuffle(dict1['p0'])
            shuffle(dict1['p1'])
        if os.path.exists(f'{dict1["dataPath"]}/{dict1["scanName"]}Text_Sequence.txt'):
            returnValue = self.ui.scanOverwrite.exec_()
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
                os.system('./tmot4 -f MIGA_II_sequence_DDSChange_test_final.mot')

    def updateDict1(self):
        dict1['p0'] = [i for i in range(self.ui.startValue0.value(), self.ui.endValue0.value() + 1, self.ui.deltaValue0.value())]
        dict1['p1'] = [i for i in range(self.ui.startValue1.value(), self.ui.endValue1.value() + 1, self.ui.deltaValue1.value())]
        dict1['sequence'] = self.ui.sequence.text()
        dict1['parameter0'] = self.ui.scanedParameter0.text()
        dict1['parameter1'] = self.ui.scanedParameter1.text()
        dict1['scanName'] = self.ui.scanName.text()
        date = datetime.datetime.now()
        dict1['dataPath'] = migaPath + 'Data_analysis/' + str(date.year) + '/' + str(date.year) + '_' + str(date.month) + '/' + str(date.year) + '_' + str(date.month) + '_' + str(date.day)
        self.ui.progress.setMaximum(len(dict1['p0']) * len(dict1['p1']))
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
