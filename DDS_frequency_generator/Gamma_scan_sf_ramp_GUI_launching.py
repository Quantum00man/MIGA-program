
import sys
import numpy as np
import xml.etree.ElementTree as ET
from xml.dom.minidom import parseString
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QButtonGroup
from PyQt5.uic import loadUi

# Constants for frequency calculation
FreqRb85 = 384230406.373
FreqRb87 = 384230484.468
GAMMA = 6.065
Freq34 = FreqRb85 - 1264.889 + 100.205
Freq23 = FreqRb87 - 2563.005 + 193.741
AOM_3D = 111.1#108.9 for cooling;  119 for det; 
AOM_3DDOWN = 114.2

def calculate_frequencies(gamma_2d, gamma_3d):
    """Calculate F2D, F3D, FRepump based on the given gamma values."""
    Basef_2D = Freq34 - 120.640 / 2 - (Freq23 - gamma_2d * GAMMA)
    Basef_3D = Freq34 - 120.640 / 2 - (Freq23 - gamma_3d * GAMMA)
    F3D = (Basef_3D + AOM_3D) / 16
    F2D = Basef_2D / 8
    FRepump = (3500 - (6834.682610904290 - 266.650 + gamma_3d * GAMMA + AOM_3DDOWN) / 2 + 80) / 2
    return F2D, F3D, FRepump

class XMLGeneratorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        loadUi("xml_generator.ui", self)

        # Set up button groups for scan mode and fixed type
        self.sf_scan_mode_group = QButtonGroup(self)
        self.sf_scan_mode_group.addButton(self.radioButton_F3D)
        self.sf_scan_mode_group.addButton(self.radioButton_F2D)

        self.ramp_mode_group = QButtonGroup(self)
        self.ramp_mode_group.addButton(self.radioButton_beginningFixed)
        self.ramp_mode_group.addButton(self.radioButton_endFixed)
        self.ramp_mode_group.addButton(self.radioButton_rampTimeScan)

        # Connect buttons for SF and Ramp functionalities
        self.pushButton_generate.clicked.connect(self.generate_sf_xml)
        self.pushButton_generate_ramp.clicked.connect(self.generate_ramp_xml)

        self.radioButton_beginningFixed.toggled.connect(self.update_ramp_mode_ui)
        self.radioButton_endFixed.toggled.connect(self.update_ramp_mode_ui)
        self.radioButton_rampTimeScan.toggled.connect(self.update_ramp_mode_ui)

        self.radioButton_F3D.setChecked(True)
        self.radioButton_beginningFixed.setChecked(True)
        self.update_ramp_mode_ui()

    def update_ramp_mode_ui(self):
        is_ramp_time_scan = self.radioButton_rampTimeScan.isChecked()

        self.label_fixedValue.setText("Scan Mode:")
        self.label_fixedGamma.setEnabled(not is_ramp_time_scan)
        self.lineEdit_fixedGamma.setEnabled(not is_ramp_time_scan)

        self.label_stepRamp.setText("Ramp Time Step (ms):" if is_ramp_time_scan else "Step Size:")
        self.label_rampTime.setText("Start Ramp Time (ms):" if is_ramp_time_scan else "Ramp Time (ms):")
        self.label_endRampTime.setVisible(is_ramp_time_scan)
        self.lineEdit_endRampTime.setVisible(is_ramp_time_scan)

    def generate_sf_xml(self):
        try:
            # Determine scan mode based on radio button selection
            scan_mode = "F3D" if self.radioButton_F3D.isChecked() else "F2D"
            start_gamma = float(self.lineEdit_startGamma.text())
            end_gamma = float(self.lineEdit_endGamma.text())
            step = float(self.lineEdit_stepSize.text())
            start_index = int(self.lineEdit_startIndex.text())

            filename = f"{scan_mode}_sf_{start_gamma}_{end_gamma}_{step}.xml"
            self.create_sf_xml(scan_mode, start_gamma, end_gamma, step, start_index, filename)
            QMessageBox.information(self, "Success", f"SF XML File Generated Successfully: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {e}")

    def create_sf_xml(self, scan_mode, start_gamma, end_gamma, step, start_index, filename):
        root = ET.Element("root")
        gamma_values = np.arange(start_gamma, end_gamma + step, step)
        for idx, gamma in enumerate(gamma_values):
            comment = ET.Comment(f"Current GAMMA = {gamma:.2f}")
            root.append(comment)

            if scan_mode == "F2D":
                F2D, _, _ = calculate_frequencies(gamma, 0)
                elem = ET.SubElement(root, "elem", n=str(start_index + idx))
                ch0 = ET.SubElement(elem, "ch0")
                ET.SubElement(ch0, "mode").text = "sf"
                ET.SubElement(ch0, "fr").text = "119000000.0"
                ET.SubElement(ch0, "am").text = "380"

                ch1 = ET.SubElement(elem, "ch1")
                ET.SubElement(ch1, "mode").text = "sf"
                ET.SubElement(ch1, "fr").text = f"{F2D * 1e6:.1f}"
                ET.SubElement(ch1, "am").text = "188"
            elif scan_mode == "F3D":
                _, F3D, FRepump = calculate_frequencies(0, gamma)
                elem = ET.SubElement(root, "elem", n=str(start_index + idx))
                ch0 = ET.SubElement(elem, "ch0")
                ET.SubElement(ch0, "mode").text = "sf"
                ET.SubElement(ch0, "fr").text = f"{F3D * 1e6:.1f}"
                ET.SubElement(ch0, "am").text = "96"

                ch1 = ET.SubElement(elem, "ch1")
                ET.SubElement(ch1, "mode").text = "sf"
                ET.SubElement(ch1, "fr").text = f"{FRepump * 1e6:.1f}"
                ET.SubElement(ch1, "am").text = "85"

        formatted_xml = parseString(ET.tostring(root)).toprettyxml(indent="  ")
        with open(filename, 'w') as f:
            f.write(formatted_xml)

    def generate_ramp_xml(self):
        try:
            start_index = int(self.lineEdit_startIndexRamp.text())
            if self.radioButton_rampTimeScan.isChecked():
                begin_gamma = float(self.lineEdit_startGammaRamp.text())
                end_gamma = float(self.lineEdit_endGammaRamp.text())
                start_ramp_time_ms = float(self.lineEdit_rampTime.text())
                end_ramp_time_ms = float(self.lineEdit_endRampTime.text())
                step_ramp_time_ms = float(self.lineEdit_stepRamp.text())

                filename = (
                    f"ramp_time_scan_{begin_gamma}_{end_gamma}_"
                    f"{start_ramp_time_ms}_{end_ramp_time_ms}_{step_ramp_time_ms}.xml"
                )
                self.create_ramp_time_scan_xml(
                    begin_gamma,
                    end_gamma,
                    start_ramp_time_ms,
                    end_ramp_time_ms,
                    step_ramp_time_ms,
                    start_index,
                    filename,
                )
            else:
                fixed_value = "beginning_fixed" if self.radioButton_beginningFixed.isChecked() else "end_fixed"
                fixed_gamma = float(self.lineEdit_fixedGamma.text())
                start_gamma = float(self.lineEdit_startGammaRamp.text())
                end_gamma = float(self.lineEdit_endGammaRamp.text())
                step = float(self.lineEdit_stepRamp.text())
                ramp_time_ms = float(self.lineEdit_rampTime.text())

                filename = f"ramp_{fixed_value}_{fixed_gamma}_{start_gamma}_{end_gamma}.xml"
                self.create_ramp_xml(
                    fixed_value,
                    fixed_gamma,
                    start_gamma,
                    end_gamma,
                    step,
                    ramp_time_ms,
                    start_index,
                    filename,
                )
            QMessageBox.information(self, "Success", f"Ramp XML File Generated Successfully: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {e}")

    def create_ramp_xml(self, fixed_value, fixed_gamma, start_gamma, end_gamma, step, ramp_time_ms, start_index, filename):
        root = ET.Element("root")
        gamma_values = np.arange(start_gamma, end_gamma + step, step)
        for idx, gamma in enumerate(gamma_values):
            if fixed_value == "beginning_fixed":
                begin_gamma, final_gamma = fixed_gamma, gamma
            else:
                begin_gamma, final_gamma = gamma, fixed_gamma

            self.append_ramp_element(root, start_index + idx, begin_gamma, final_gamma, ramp_time_ms)

        formatted_xml = parseString(ET.tostring(root)).toprettyxml(indent="  ")
        with open(filename, 'w') as f:
            f.write(formatted_xml)

    def create_ramp_time_scan_xml(
        self,
        begin_gamma,
        end_gamma,
        start_ramp_time_ms,
        end_ramp_time_ms,
        step_ramp_time_ms,
        start_index,
        filename,
    ):
        root = ET.Element("root")
        ramp_time_values = np.arange(start_ramp_time_ms, end_ramp_time_ms + step_ramp_time_ms, step_ramp_time_ms)
        for idx, ramp_time_ms in enumerate(ramp_time_values):
            self.append_ramp_element(root, start_index + idx, begin_gamma, end_gamma, ramp_time_ms)

        formatted_xml = parseString(ET.tostring(root)).toprettyxml(indent="  ")
        with open(filename, 'w') as f:
            f.write(formatted_xml)

    def append_ramp_element(self, root, elem_index, begin_gamma, end_gamma, ramp_time_ms):
        rr = 1
        comment = ET.Comment(
            f"SUBDOPPLER COOLING: FROM {begin_gamma:.2f} GAMMA TO {end_gamma:.2f} GAMMA, duration time: {ramp_time_ms:.2f} ms"
        )
        root.append(comment)

        _, start_F3D, start_FRepump = calculate_frequencies(0, begin_gamma)
        _, end_F3D, end_FRepump = calculate_frequencies(0, end_gamma)

        dv_F3D = abs(start_F3D - end_F3D) / (ramp_time_ms * 1e6 / (10 * rr))
        dv_FRepump = abs(start_FRepump - end_FRepump) / (ramp_time_ms * 1e6 / (10 * rr))

        elem = ET.SubElement(root, "elem", n=str(elem_index))
        ch0 = ET.SubElement(elem, "ch0")
        ET.SubElement(ch0, "mode").text = "ramp"
        ET.SubElement(ch0, "fr").text = f"{start_F3D * 1e6:.1f}"
        ET.SubElement(ch0, "am").text = "103"
        ET.SubElement(ch0, "var").text = "fr"
        ET.SubElement(ch0, "ev").text = f"{end_F3D * 1e6:.1f}"
        ET.SubElement(ch0, "dv").text = f"{dv_F3D * 1e6:.6f}"
        ET.SubElement(ch0, "rr").text = str(rr)

        ch1 = ET.SubElement(elem, "ch1")
        ET.SubElement(ch1, "mode").text = "ramp"
        ET.SubElement(ch1, "fr").text = f"{start_FRepump * 1e6:.1f}"
        ET.SubElement(ch1, "am").text = "79"
        ET.SubElement(ch1, "var").text = "fr"
        ET.SubElement(ch1, "ev").text = f"{end_FRepump * 1e6:.1f}"
        ET.SubElement(ch1, "dv").text = f"{dv_FRepump * 1e6:.6f}"
        ET.SubElement(ch1, "rr").text = str(rr)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = XMLGeneratorApp()
    window.show()
    sys.exit(app.exec_())
