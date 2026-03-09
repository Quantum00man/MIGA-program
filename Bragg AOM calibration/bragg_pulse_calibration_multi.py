import numpy as np
import os
import re
import pandas as pd
from scipy.interpolate import interp1d

def get_inverse_calibration_func(csv_path):
    """
    Reads the calibration data and returns an inverse interpolation function:
    DAC_value = f(Target_Optical_Power)
    """
    if not os.path.exists(csv_path):
        print(f"Warning: Calibration file '{csv_path}' not found. Using ideal linear output.")
        return lambda x: x 
        
    # Read the monotonic, offset-removed calibration data
    data = pd.read_csv(csv_path, header=None)
    optical_power = data.iloc[:, 0].values
    dac_values = data.iloc[:, 1].values
    
    # Use 'linear' interpolation and force 0.0V output for negative or zero target power
    inv_func = interp1d(
        optical_power, 
        dac_values, 
        kind='linear', 
        bounds_error=False, 
        fill_value=(0.0, dac_values[-1])
    )
    return inv_func

def generate_mot_file(template_path, fwhm, amplitude, calib_func, shape='gaussian', clock_res=0.2):
    """
    Generates a .mot file with the specified FWHM, amplitude, and pulse shape.
    """
    shape = shape.lower()
    
    # 1. Calculate pulse array based on chosen shape
    if shape == 'gaussian':
        std_dev = fwhm / (2 * np.sqrt(2 * np.log(2)))
        # Extend to 4 sigma (ideal optical power drops to ~0.03% of peak, smoothly reaching 0)
        mean = 4.0 * std_dev
        x_end = 2.0 * mean
        num_points = int(x_end / clock_res)
        x_values = np.linspace(0, x_end, num_points)
        ideal_optical_shape = amplitude * np.exp(-((x_values - mean) ** 2) / (2 * std_dev ** 2))
        
    elif shape == 'blackman':
        # The FWHM of a standard Blackman window is roughly 0.405 * total_duration
        total_duration = fwhm / 0.405
        num_points = int(total_duration / clock_res)
        ideal_optical_shape = amplitude * np.blackman(num_points)
        
    else:
        print(f"Error: Unsupported shape '{shape}'. Please choose 'gaussian' or 'blackman'.")
        return

    # 2. Map ideal optical power to actual DAC voltage using calibration function
    y_values = calib_func(ideal_optical_shape)
    y_values = np.clip(y_values, 0, None)
    
    # 3. Generate command list
    pulse_commands = []
    pulse_name = f"{shape.capitalize()}_pulse"
    
    # Insert 0.0V command at the beginning and hold for 500us
    pulse_commands.append(f"+500.0us {pulse_name} = 0.000\t\t(32)")
    
    # Main waveform body
    for y in y_values:
        cmd = f"+{clock_res:.1f}us {pulse_name} = {y:.3f}\t\t(32)"
        pulse_commands.append(cmd)
        
    # Append 0.0V command at the end to ensure AOM is completely off
    pulse_commands.append(f"+{clock_res:.1f}us {pulse_name} = 0.000\t\t(32)")
    
    # 4. Calculate total points and PARAMETER0 compensation
    total_generated_points = num_points + 2
    pulse_logic_duration = total_generated_points * clock_res
    param0_value = 331119 - pulse_logic_duration
    
    # 5. Read, replace, and save template content
    if not os.path.exists(template_path):
        print(f"Error: Template file '{template_path}' not found.")
        return

    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()

    new_content = content.replace("<PARAMETER0>", f"{param0_value:.1f}")
    pattern = re.compile(r'###bragg###.*?###bragg###', re.DOTALL)
    replacement_block = f"###bragg###\n" + "\n".join(pulse_commands) + f"\n###bragg###"
    new_content = re.sub(pattern, replacement_block, new_content)

    # Format filename (e.g., 20.0us_gaussian.mot)
    new_filename = f"{fwhm:.1f}us_{shape}.mot"
    with open(new_filename, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"Generated: {new_filename:<25} | Max DAC mapped: {max(y_values):.3f} V | Total Commands: {total_generated_points + 1}")

# ================= Configuration =================
template_name = "templet.mot"             
calibration_file = "calibration.csv" 
target_amp = 0.1733                         

# --- Batch Processing Settings ---
fwhm_start = 10.0
fwhm_end = 50.0
fwhm_step = 10.0

# --- Shape Selection ---
# Options: 'gaussian' or 'blackman'
pulse_shape = 'gaussian'                   

print("-" * 60)
print(f"Starting Batch Generation ({pulse_shape.capitalize()} pulses)...")
print("-" * 60)

# Load the monotonic, offset-free calibration file
inverse_calib_function = get_inverse_calibration_func(calibration_file)

# Loop through the FWHM range and generate files
# Using np.arange with a small buffer on the end to ensure the exact end value is included
for current_fwhm in np.arange(fwhm_start, fwhm_end + (fwhm_step * 0.1), fwhm_step):
    generate_mot_file(
        template_path=template_name, 
        fwhm=current_fwhm, 
        amplitude=target_amp, 
        calib_func=inverse_calib_function, 
        shape=pulse_shape
    )

print("-" * 60)
print("Batch generation completed successfully.")