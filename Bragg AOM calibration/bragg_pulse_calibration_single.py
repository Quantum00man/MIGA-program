import numpy as np
import os
import re
from scipy.interpolate import interp1d

# --- 新增：加载标定数据的函数 ---
def get_inverse_calibration_func(csv_path):
    """
    读取标定文件，返回一个插值函数：DAC_value = f(Target_Optical_Power)
    假设 csv 文件没有表头，第一列是光功率(PD电压)，第二列是DAC值。
    """
    if not os.path.exists(csv_path):
        print(f"Warning: 找不到标定文件 '{csv_path}'，将使用理想线性输出。")
        # 如果没有标定文件，直接返回一个 y=x 的线性函数
        return lambda x: x 
        
    data = np.loadtxt(csv_path, delimiter=',')
    optical_power = data[:, 0]
    dac_values = data[:, 1]
    
    # 确保数据严格单调递增以避免插值报错
    # （实际操作中，你可能需要用代码或Excel提前把数据平滑、截断一下）
    
    # 生成反向插值函数 (通过输入期望的光功率，输出需要的DAC值)
    # bounds_error=False, fill_value="extrapolate" 允许轻微越界时不报错
    inv_func = interp1d(optical_power, dac_values, kind='cubic', bounds_error=False, fill_value="extrapolate")
    return inv_func

def generate_mot_file(template_path, fwhm, amplitude, calib_func, clock_res=0.2, target_y=0.01):
    # 1. 计算高斯标准差 (sigma)
    std_dev = fwhm / (2 * np.sqrt(2 * np.log(2)))
    
    # 2. 计算 mean (使得 x=0 时理想光功率 = target_y)
    mean = np.sqrt(-2 * std_dev ** 2 * np.log(target_y / amplitude))
    
    # 3. 生成脉冲点
    x_end = 2 * mean
    num_points = int(x_end / clock_res)
    x_values = np.linspace(0, x_end, num_points)
    
    # --- 关键修改点 ---
    # 这里的 y_values 变成了“理想的输出光功率形状”
    ideal_optical_shape = amplitude * np.exp(-((x_values - mean) ** 2) / (2 * std_dev ** 2))
    
    # 使用标定函数的反函数，将“理想光功率”映射为“实际需要的DAC控制值”
    y_values = calib_func(ideal_optical_shape)
    
    # 限制极值，防止DAC给入负值或超出硬件量程 (假设下限是0)
    y_values = np.clip(y_values, 0, None)
    
    # 4. 生成指令列表并处理第一行
    pulse_commands = []
    for i, y in enumerate(y_values):
        time_step = 500.0 if i == 0 else clock_res
        # 将映射后的DAC值写入命令
        cmd = f"+{time_step:.1f}us Gaussian_pulse = {y:.3f}\t\t(32)"
        pulse_commands.append(cmd)
    
    # 5. 计算 PARAMETER0 补偿量
    pulse_logic_duration = num_points * clock_res
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
    print(f"脉冲点数: {num_points}")
    print(f"是否使用非线性补偿: {'是' if calib_func.__name__ != '<lambda>' else '否 (线性回退)'}")
    print("-" * 40)

# --- 参数配置 ---
template_name = "templet.mot"  
target_fwhm = 20.0         
target_amp = 0.173            # 这里的 7.0 现在代表你标定数据里的目标光功率（PD电压）上限

# 1. 生成或加载标定函数
# 假设你测出了数据并存成了 calibration.csv。如果没有这个文件，它会默认线性输出。
calibration_file = "calibration.csv" 
inverse_calib_function = get_inverse_calibration_func(calibration_file)

# 2. 生成带补偿的文件
generate_mot_file(template_name, target_fwhm, target_amp, inverse_calib_function)