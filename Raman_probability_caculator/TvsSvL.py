import numpy as np

# ==== 常数定义 ====
hbar = 1.0545718e-34       # J·s
kB = 1.380649e-23          # J/K
lambda0 = 780e-9           # m, 激光波长 (Rb D2 线)
m = 1.443160e-25           # kg, Rb-87 质量

# ==== 基本量计算 ====
k = 2 * np.pi / lambda0    # 波矢
vrec = hbar * k / m        # 单光子反冲速度

def sv_ratio(T_nK):
    """
    输入: T_nK (温度, 单位 nK)
    输出: (s_vL, 倍数 s_vL/v_rec)
    """
    T = T_nK * 1e-9  # 转为 K
    svL = np.sqrt(kB * T / m)
    ratio = svL / vrec
    return svL, ratio

# ==== 示例 ====
for T in [ 90, 100,150,200,250,2000,2200,2400]:  # 50nK, 90nK, 200nK, 1uK
    sv, r = sv_ratio(T)
    print(f"T = {T:6.1f} nK → svL = {sv:.3e} m/s = {r:.3f} vrec")

# 输出示例：
# T =   50.0 nK → svL = 2.195e-03 m/s = 0.373 vrec
# T =   90.0 nK → svL = 2.945e-03 m/s = 0.501 vrec
# T =  200.0 nK → svL = 4.384e-03 m/s = 0.745 vrec
# T = 1000.0 nK → svL = 9.803e-03 m/s = 1.667 vrec

