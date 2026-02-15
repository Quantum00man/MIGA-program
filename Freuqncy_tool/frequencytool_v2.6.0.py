import sys
import matplotlib
matplotlib.use('Qt5Agg')
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.uic import loadUiType
import os
import numpy as np
import matplotlib.pyplot as plt
import math
Ui_RbCalculator, _ = loadUiType("rb_calculator2.ui")

class RbCalculator(QMainWindow, Ui_RbCalculator):
    global gravity, mass, Kb
    gravity = 9.81  # m/s 
    mass = 1.443160648*10**(-25) #kg
    Kb = 1.3806504*10**(-23) #J/K
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle('Rb Frequency Calculator')
        self.calculated = False
        self.labels = {
            "Basef": self.label_Basef,
            "F3D": self.label_F3D,
            "F2D": self.label_F2D,
            "FRep2D": self.label_FRep2D,
            "FRepump": self.label_FRepump,
            "FRaman2": self.label_FRaman2,
            "FRaman1": self.label_FRaman1
        }
        

        self.btnCalculate.clicked.connect(self.calculateFrequencies)
        self.btnCalculate2.clicked.connect(self.calculateFrequencies_Raman)
        self.btnWriteDDS1.clicked.connect(lambda: self.writeToXML('DDS1'))
        self.btnWriteDDS5.clicked.connect(lambda: self.writeToXML('DDS5'))
        self.btnCalculate_gmot.clicked.connect(self.executeGMOTCommand)
        self.calculate_initial_velocity.clicked.connect(self.Velocity_calculator)
        self.generate_cuve.clicked.connect(self.Curve_generator)
        self.btnGenerate.clicked.connect(lambda: self.writeToXML_scan())

    def initUI(self):
        pass

    def calculateFrequencies(self):
        number_GAMMA_2D = float(self.inputGamma2D.text())
        number_GAMMA_3D = float(self.inputGamma3D.text())
        DELT = float(self.inputDELT.text())
        delt = float(self.inputdelt.text())


        FreqRb85 = 384230406.373
        FreqRb87 = 384230484.468
        GAMMA = 6.065
        Freq34 = FreqRb85 - 1264.889 + 100.205
        Freq23 = FreqRb87 - 2563.005 + 193.741
        Basef = Freq34 - 120.640/2 - Freq23
        Basef_2D = Freq34 - 120.640/2 - (Freq23 - number_GAMMA_2D * GAMMA)
        Basef_3D = Freq34 - 120.640/2 - (Freq23 - number_GAMMA_3D * GAMMA)
        Basef_Raman1 = Freq34 - 120.640/2 - (Freq23)
        Basef_Raman2 = Freq34 - 120.640/2 - (Freq23 -delt)
        AOM_3D = 110
        AOM_3DDOWN = 111.575
        self.F3D = (Basef_3D + AOM_3D) / 16
        self.F2D = Basef_2D / 8
        EOMRep2D = 6834.682610904290 - 266.650090 + number_GAMMA_2D * GAMMA
        FRep2D = (7000 - EOMRep2D) / 4
        self.FRepump = (3500 - (6834.682610904290 - 266.650 + number_GAMMA_3D * GAMMA + AOM_3DDOWN) / 2 + 80) / 2
       
        self.number_GAMMA_2D = number_GAMMA_2D
        self.number_GAMMA_3D = number_GAMMA_3D

        self.labels["Basef"].setText(f"Basef={Basef:.6f}")
        self.labels["F3D"].setText(f"F3D={self.F3D:.6f}")
        self.labels["F2D"].setText(f"F2D={self.F2D:.6f}")
        self.labels["FRep2D"].setText(f"FRep2D={FRep2D:.6f}")
        self.labels["FRepump"].setText(f"FRepump={self.FRepump:.6f}")
       

        self.calculated = True
    def calculateFrequencies_Raman(self):
        
        DELT = float(self.inputDELT.text())
        delt = float(self.inputdelt.text())
        
        FreqRb85 = 384230406.373
        FreqRb87 = 384230484.468
        GAMMA = 6.065
        Freq34 = FreqRb85 - 1264.889 + 100.205
        Freq23 = FreqRb87 - 2563.005 + 193.741
        Basef = Freq34 - 120.640/2 - Freq23
        Basef_Raman1 = Freq34 - 120.640/2 - (Freq23)
        Basef_Raman2 = Freq34 - 120.640/2 - (Freq23 -delt)
        AOM_3D = 110
        AOM_3DDOWN = 111.575

        self.FRaman2 = (Basef_Raman2+ 160 +266.65 +156.95+DELT) / 16
        self.FRaman1 = (3500-(6834.682610904290+ 160+delt) / 2 + 80) / 2
        self.labels["FRaman2"].setText(f"FRaman2={self.FRaman2:.6f}")
        self.labels["FRaman1"].setText(f"FRaman1={self.FRaman1:.6f}")

        self.calculated = True
        

    def writeToXML(self, target):
        if not self.calculated:
            print("Please calculate before writing to XML")
            return

        # 获取当前日期，并创建以日期命名的文件夹
        today = datetime.now().strftime("%Y%m%d")
        directory = os.path.join(os.getcwd(), today)
        if not os.path.exists(directory):
            os.makedirs(directory)

        # 生成文件名并包括日期文件夹路径
        filename = os.path.join(directory, datetime.now().strftime(f"%H%M%S_{today}_{target}.xml"))

        root = ET.Element('ad9958')
        comment = ET.Comment(f'COOLER : - {self.number_GAMMA_2D if target == "DDS1" else self.number_GAMMA_3D} GAMMA')
        root.append(comment)
        elem = ET.SubElement(root, 'elem', n="0")
        ch0 = ET.SubElement(elem, 'ch0')
        ET.SubElement(ch0, 'mode').text = 'sf'
        ET.SubElement(ch0, 'fr').text = str(self.F3D * 1e6) if target == "DDS1" else '119000000.000'
        ET.SubElement(ch0, 'am').text = '220' if target == "DDS1" else '70'
        ch1 = ET.SubElement(elem, 'ch1')
        ET.SubElement(ch1, 'mode').text = 'sf'
        ET.SubElement(ch1, 'fr').text = str(self.FRepump * 1e6) if target == "DDS1" else str(self.F2D * 1e6)
        ET.SubElement(ch1, 'am').text = '220' if target == "DDS1" else '150'

        tree = ET.ElementTree(root)
        tree.write(filename, encoding='ISO-8859-1', xml_declaration=True)
        print(f"Written to {filename}")

        if (target == "DDS1" and self.checkBoxDDS1.isChecked()) or (target == "DDS5" and self.checkBoxDDS5.isChecked()):
            command = f'python3 "../writetable.py" -w "{os.path.basename(filename)}"'
            subprocess.run(command, shell=True, cwd=directory, check=True)
            print(f"Command executed: {command}")

    def executeGMOTCommand(self):
        # 在终端中执行命令 './gmot4 &'
        command1 = './gmot4 &'
        try:
            subprocess.Popen(command, shell=True)
            print("Command executed successfully: {}".format(command1))
        except Exception as e:
            print("Shit! Error executing command '{}': {}".format(command1, e))
    
    def Curve_generator(self):
        
        f = float(self.input_f.text())
    
    
        initial_velocity = math.sqrt(3)*f*1000000*780.24*10**(-9)  
        

        # Calculate the height
        def calculate_height(time):
        
            return initial_velocity * time - 0.5 * gravity * time ** 2
    

        # generate the curve, step = 0.01s
        max_time = (initial_velocity / gravity) * 2  
        time_points = np.arange(0, max_time, 0.01)

        # 
        height_points = [calculate_height(t) for t in time_points]

        # 
        plt.plot(time_points, height_points)
        plt.title(f'Projectile Trajectory \n v0={initial_velocity :.6f}m/s\n Max_height={calculate_height(max_time/2) :.6f}m')
        plt.xlabel('Time (s)')
        plt.ylabel('Height (m)')
        plt.grid(True)
        plt.show()
    
    def Velocity_calculator(self):
        #number_GAMMA_2D = float(self.inputGamma2D.text())
        #f = float(self.input_f.text())
        flying_time = float(self.input_flying_time.text())/1000 #s
        FWHM_det = float(self.input_HWHM_det.text())/1000 #s
        HWHM_det = FWHM_det/2
        height_Det_down = 0.26138 #unit: m 
        height_Det_up = 0.26338 #unit: m 
        real_velocity = (height_Det_down + 0.5*gravity*flying_time**2)/flying_time
        v_det = abs(real_velocity-gravity*flying_time)
        Temp = ((v_det*HWHM_det)**2*mass)/(flying_time**2*2*math.log(2)*Kb)*10**6 # uK
        
        self.display_velocity.setText(str(real_velocity))
        #self.display_temp.setText(str(Temp))
        self.display_temp.setText(f"{Temp:.3f}")




    def float_range(self, start, stop, step):
        """Generate a range of floating point values."""
        current = start
        while current <= stop:
            yield current
            current += step
    

    def writeToXML_scan(self):
        

        # 获取当前日期，并创建以日期命名的文件夹
        today = datetime.now().strftime("%Y%m%d")
        directory = os.path.join(os.getcwd(), today)
        if not os.path.exists(directory):
            os.makedirs(directory)

        #reinit the DDSvalue
            
      

        filename = os.path.join(directory, datetime.now().strftime(f"%H%M%S_{today}_DDS1.xml"))

        root = ET.Element('ad9958')

        elem_id = 0
        for scan_current_value in self.float_range(float(self.scan_start.text()), float(self.scan_end.text()), float(self.scan_step.text())):
            AOM_3D = 110
            AOM_3DDOWN = 111.575   
            FreqRb85 = 384230406.373
            FreqRb87 = 384230484.468
            GAMMA = 6.065
            Freq34 = FreqRb85 - 1264.889 + 100.205
            Freq23 = FreqRb87 - 2563.005 + 193.741
            Basef = Freq34 - 120.640/2 - Freq23
            #Basef_2D = Freq34 - 120.640/2 - (Freq23 - number_GAMMA_2D * GAMMA)
            Basef_3D = Freq34 - 120.640/2 - (Freq23 - scan_current_value * GAMMA)
            scan_F3D = (Basef_3D + AOM_3D) / 16
            scan_FRepump = (3500 - (6834.682610904290 - 266.650 + scan_current_value * GAMMA + AOM_3D) / 2 + 80) / 2  
            comment = ET.Comment(f'3DCOOLER : - {scan_current_value} GAMMA')
            root.append(comment)

            elem = ET.SubElement(root, 'elem', n=str(elem_id))
            ch0 = ET.SubElement(elem, 'ch0')
            ET.SubElement(ch0, 'mode').text = 'sf'
            ET.SubElement(ch0, 'fr').text = str(scan_F3D * 1e6) 
            ET.SubElement(ch0, 'am').text = '220' 
            ch1 = ET.SubElement(elem, 'ch1')
            ET.SubElement(ch1, 'mode').text = 'sf'
            ET.SubElement(ch1, 'fr').text = str(scan_FRepump * 1e6) 
            ET.SubElement(ch1, 'am').text = '220' 
            

            elem_id += 1  # Increment elem_id for each iteration

        tree = ET.ElementTree(root)
        tree.write(filename, encoding='ISO-8859-1', xml_declaration=True)
        print(f"Written to {filename}")
        


def main():
    app = QApplication(sys.argv)
    window = RbCalculator()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
