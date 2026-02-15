import xml.etree.ElementTree as ET
import os
from xml.dom import minidom

def generate_xml_element(n, framan1, framan2, delt_khz):
    comment_text = f"# RAMAN : delt={delt_khz:.1f} kHz  DELTA=1000 MHz"
    comment = ET.Comment(comment_text)
    
    elem = ET.Element('elem', n=str(n))
    ch0 = ET.SubElement(elem, 'ch0')
    mode0 = ET.SubElement(ch0, 'mode')
    mode0.text = 'sf'
    fr0 = ET.SubElement(ch0, 'fr')
    fr0.text = f"{framan2:.3f}"
    am0 = ET.SubElement(ch0, 'am')
    am0.text = '220'
    
    ch1 = ET.SubElement(elem, 'ch1')
    mode1 = ET.SubElement(ch1, 'mode')
    mode1.text = 'sf'
    fr1 = ET.SubElement(ch1, 'fr')
    fr1.text = f"{framan1:.4f}"
    am1 = ET.SubElement(ch1, 'am')
    am1.text = '220'
    
    return comment, elem

def calculate_frequencies(delt_khz, DELT):
    FreqRb85 = 384230406.373
    FreqRb87 = 384230484.468
    GAMMA = 6.065
    Freq34 = FreqRb85 - 1264.889 + 100.205
    Freq23 = FreqRb87 - 2563.005 + 193.741
    Basef = Freq34 - 120.640/2 - Freq23
    Basef_Raman1 = Freq34 - 120.640/2 - Freq23
    Basef_Raman2 = Freq34 - 120.640/2 - (Freq23 - delt_khz/1000)  # Convert kHz to MHz

    AOM_3D = 108.9
    AOM_3DDOWN = 108.9

    FRaman2 = (Basef_Raman2 + 160 + 266.65 + 156.95 + DELT) / 16 * 1e6
    FRaman1 = (3500 - (6834.682610904290 + 160 + delt_khz/1000) / 2 + 80) / 2 * 1e6  # Convert kHz to MHz

    return FRaman1, FRaman2

def main():
    user_input = input("Enter the initial value of delt (kHz), final value of delt (kHz), number of steps, and starting value for n, separated by spaces:\n")
    start_delt_khz, end_delt_khz, steps, start_n = map(float, user_input.split())
    steps = int(steps)
    start_n = int(start_n)
    DELT = 1000  # 1000 MHz
    
    delt_values_khz = [start_delt_khz + x * (end_delt_khz - start_delt_khz) / (steps - 1) for x in range(steps)]
    
    root = ET.Element('root')
    
    for i, delt_khz in enumerate(delt_values_khz):
        FRaman1, FRaman2 = calculate_frequencies(delt_khz, DELT)
        comment, elem = generate_xml_element(start_n + i, FRaman1, FRaman2, delt_khz)
        root.append(comment)
        root.append(elem)
        print(f"Added config with n={start_n + i}, delt={delt_khz:.3f} kHz")

    tree = ET.ElementTree(root)
    xml_str = ET.tostring(root, encoding='ISO-8859-1', method='xml')
    
    # Use minidom for pretty printing
    dom = minidom.parseString(xml_str)
    pretty_xml_str = dom.toprettyxml(indent="    ", encoding="ISO-8859-1")
    
    # Get the current script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_name = f"{start_delt_khz}_{end_delt_khz}_{steps}.xml"
    file_path = os.path.join(script_dir, file_name)
    
    with open(file_path, 'wb') as file:
        file.write(pretty_xml_str)
    
    print(f"Generated configurations.xml with all elements at {file_path}")

if __name__ == "__main__":
    main()
