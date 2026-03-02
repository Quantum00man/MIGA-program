import numpy as np
import os
import re
import pandas as pd
from scipy.interpolate import interp1d

def get_inverse_calibration_func(csv_path):
    if not os.path.exists(csv_path):
        print(f"Warning: 找不到标定文件 '{csv_path}'，将使用理想线性输出。")
        return lambda x: x 
        
    # 读取去偏置后的单调标定数据
    data = pd.read_csv(csv_path, header=None)
    optical_power = data.iloc[:, 0].values
    dac_values = data.iloc[:, 1].values
    
    # 改进1：改用 'linear' 插值。
    # 改进2：使用 fill_value=(0.0, dac_values[-1])，即要求的光功率≤0时，强制DAC给0V；超出最大能力时，给最大DAC值
    inv_func = interp1d(
        optical_power, 
        dac_values, 
        kind='linear', 
        bounds_error=False, 
        fill_value=(0.0, dac_values[-1])
    )
    return inv_func

def generate_mot_file(template_path, fwhm, amplitude, calib_func, clock_res=0.2):
    # 1. 计算高斯标准差 (sigma)
    std_dev = fwhm / (2 * np.sqrt(2 * np.log(2)))
    
    # 2. 改进3：不再使用 target_y 截断，而是直接让高斯波形延伸到 ±4 个 sigma 处
    # 在 4*sigma 处，e^(-8) 约为 0.0003，光功率已经衰减到绝对零点
    mean = 4.0 * std_dev
    x_end = 2.0 * mean
    
    # 3. 生成脉冲点
    num_points = int(x_end / clock_res)
    x_values = np.linspace(0, x_end, num_points)
    
    # 计算理想光功率，并通过反函数映射为实际需要的DAC值
    ideal_optical_shape = amplitude * np.exp(-((x_values - mean) ** 2) / (2 * std_dev ** 2))
    y_values = calib_func(ideal_optical_shape)
    y_values = np.clip(y_values, 0, None)
    
    # 4. 生成指令列表
    pulse_commands = []
    
    # 改进4：在最前面强制插入一条 0.0V 的初始化指令，并维持第一行的 500us 延时
    pulse_commands.append(f"+500.0us Gaussian_pulse = 0.000\t\t(32)")
    
    # 处理高斯曲线主体（所有点都使用 clock_res = +0.2us）
    for y in y_values:
        cmd = f"+{clock_res:.1f}us Gaussian_pulse = {y:.3f}\t\t(32)"
        pulse_commands.append(cmd)
        
    # 改进4：在最后面再强制追加一条 0.0V 的指令，确保波形结束后 AOM 彻底关死（保持 0.2us 即可）
    pulse_commands.append(f"+{clock_res:.1f}us Gaussian_pulse = 0.000\t\t(32)")
    
    # 计算点数（主体点数 + 头尾2个强制0V点）
    total_generated_points = num_points + 2
    
    # 5. 计算 PARAMETER0 补偿量
    # 注意：第一行的500us不计算在脉冲逻辑点数中，按照你的原逻辑计算逻辑时长：
    pulse_logic_duration = total_generated_points * clock_res
    param0_value = 331119 - pulse_logic_duration
    
    # 6. 处理文件内容
    if not os.path.exists(template_path):
        print(f"Error: 找不到模板文件 '{template_path}'")
        return

    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()

    new_content = content.replace("<PARAMETER0>", f"{param0_value:.1f}")
    pattern = re.compile(r'###bragg###.*?###bragg###', re.DOTALL)
    replacement_block = f"###bragg###\n" + "\n".join(pulse_commands) + f"\n###bragg###"
    new_content = re.sub(pattern, replacement_block, new_content)

    # 7. 保存文件
    new_filename = f"{fwhm}us_compensated.mot"
    with open(new_filename, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print("-" * 40)
    print(f"文件已生成: {new_filename}")
    print(f"脉冲总指令行数: {total_generated_points}")
    print(f"起点 DAC 设定: 0.000 V")
    print(f"终点 DAC 设定: 0.000 V")
    print(f"计算出的 PARAMETER0: {param0_value:.1f}")
    print("-" * 40)

# --- 参数配置 ---
template_name = "templet.mot"  
target_fwhm = 20.0         
target_amp = 0.170  # 使用前面对齐的最大光电管电压

# 加载上一次我帮你生成的去偏置、单调的校准文件
calibration_file = "calibration_clean.csv" 
inverse_calib_function = get_inverse_calibration_func(calibration_file)

# 生成带补偿的文件
generate_mot_file(template_name, target_fwhm, target_amp, inverse_calib_function)