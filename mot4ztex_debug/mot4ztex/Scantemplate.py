from PyQt5 import QtCore, QtGui, QtWidgets
from pyqtgraph import PlotWidget, SpinBox, ValueLabel, LabelItem
import pyqtgraph as pg




class Ui_ScanSequence(object):
    def setupUi(self, ScanSequence):
        ScanSequence.setObjectName("ScanSequence")
        ScanSequence.resize(300, 300)
        self.gridLayout = QtWidgets.QGridLayout(ScanSequence)
        self.gridLayout.setObjectName("gridLayout")




        self.startScan = QtWidgets.QPushButton(ScanSequence)
        self.startScan.setText("Start Scan")
        self.gridLayout.addWidget(self.startScan,0,0)
        self.startScan.setFixedWidth(150)

        self.shuffle=QtWidgets.QCheckBox(ScanSequence)
        self.gridLayout.addWidget(self.shuffle,0,1)
        self.shuffle.setText('Shuffle')



        self.labelSequence=QtWidgets.QLabel(ScanSequence)
        self.gridLayout.addWidget(self.labelSequence,1,0)
        self.labelSequence.setText("Sequence")
        self.sequence=QtWidgets.QLineEdit(ScanSequence)
        self.sequence.setText('test')
        self.sequence.setFixedWidth(150)
        self.gridLayout.addWidget(self.sequence,2,0)

        self.labelScanName=QtWidgets.QLabel(ScanSequence)
        self.gridLayout.addWidget(self.labelScanName,1,1)
        self.labelScanName.setText("ScanName")
        self.scanName=QtWidgets.QLineEdit(ScanSequence)
        self.scanName.setText('scan0')
        self.scanName.setFixedWidth(150)
        self.gridLayout.addWidget(self.scanName,2,1)

################ Box1 ###############
        self.box1=QtWidgets.QGroupBox(ScanSequence)
        self.gridLayout.addWidget(self.box1, 3, 0,2, 2)
        self.box1Layout=QtWidgets.QGridLayout()
        self.box1.setLayout(self.box1Layout)

        self.labelp0=QtWidgets.QLabel(ScanSequence)
        self.box1Layout.addWidget(self.labelp0,0,1)
        self.labelp0.setText("Parameter 0")
        self.labelp0.setFixedWidth(100)
        self.labelp1=QtWidgets.QLabel(ScanSequence)
        self.box1Layout.addWidget(self.labelp1,0,2)
        self.labelp1.setText("Parameter 1")
        self.labelp1.setFixedWidth(100)

        self.labelparameter=QtWidgets.QLabel(ScanSequence)
        self.box1Layout.addWidget(self.labelparameter,1,0)
        self.labelparameter.setText("name")
        self.labelparameter.setFixedWidth(100)

        self.scanedParameter0=QtWidgets.QLineEdit(ScanSequence)
        self.scanedParameter0.setText("Parameter0")
        self.scanedParameter0.setFixedWidth(150)
        self.box1Layout.addWidget(self.scanedParameter0,1,1)
        self.scanedParameter1=QtWidgets.QLineEdit(ScanSequence)
        self.scanedParameter1.setText("none")
        self.scanedParameter1.setFixedWidth(150)
        self.box1Layout.addWidget(self.scanedParameter1,1,2)

        self.labelstartValue=QtWidgets.QLabel(ScanSequence)
        self.box1Layout.addWidget(self.labelstartValue,2,0)
        self.labelstartValue.setText("Start Value")
        self.labelstartValue.setFixedWidth(100)
        self.startValue0=SpinBox(ScanSequence,value=0,int=True, step=10)
        self.startValue0.setRange(-100000000,100000000)
        self.startValue0.setFixedWidth(120)
        self.startValue0.setFixedHeight(30)
        self.box1Layout.addWidget(self.startValue0,2,1)
        self.startValue1=SpinBox(ScanSequence,value=1,int=True, step=1)
        self.startValue1.setRange(-100000000,100000000)
        self.startValue1.setFixedWidth(120)
        self.startValue1.setFixedHeight(30)
        self.box1Layout.addWidget(self.startValue1,2,2)

        self.labelendValue=QtWidgets.QLabel(ScanSequence)
        self.box1Layout.addWidget(self.labelendValue,3,0)
        self.labelendValue.setText("End Value")
        self.labelendValue.setFixedWidth(100)
        self.endValue0=SpinBox(ScanSequence,value=100,int=True, step=10)
        self.endValue0.setRange(-100000000,100000000)
        self.endValue0.setFixedWidth(120)
        self.endValue0.setFixedHeight(30)
        self.box1Layout.addWidget(self.endValue0,3,1)
        self.endValue1=SpinBox(ScanSequence,value=1,int=True, step=1)
        self.endValue1.setRange(-100000000,100000000)
        self.endValue1.setFixedWidth(120)
        self.endValue1.setFixedHeight(30)
        self.box1Layout.addWidget(self.endValue1,3,2)

        self.labelDeltaValue=QtWidgets.QLabel(ScanSequence)
        self.box1Layout.addWidget(self.labelDeltaValue,4,0)
        self.labelDeltaValue.setText("Delta")
        self.labelDeltaValue.setFixedWidth(100)
        self.deltaValue0=SpinBox(ScanSequence,value=10,int=True, step=10)
        self.deltaValue0.setRange(0,100000000)
        self.deltaValue0.setFixedWidth(120)
        self.deltaValue0.setFixedHeight(30)
        self.box1Layout.addWidget(self.deltaValue0,4,1)
        self.deltaValue1=SpinBox(ScanSequence,value=1,int=True, step=1)
        self.deltaValue1.setRange(0,100000000)
        self.deltaValue1.setFixedWidth(120)
        self.deltaValue1.setFixedHeight(30)
        self.box1Layout.addWidget(self.deltaValue1,4,2)

        self.progress=QtWidgets.QProgressBar(ScanSequence)
        self.box1Layout.addWidget(self.progress,5,0,1,3)
        self.progress.setMaximum(100)

        self.scanOverwrite=QtWidgets.QMessageBox(ScanSequence)
        self.scanOverwrite.setText("Overwrite?")
        self.scanOverwrite.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)

    def retranslateUi(self, ScanSequence):
        _translate = QtCore.QCoreApplication.translate
        ScanSequence.setWindowTitle(_translate("ScanSequence", "ScanSequence"))