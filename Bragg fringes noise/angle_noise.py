import numpy as np
import matplotlib.pyplot as plt

# ----------- 参数 -----------
n = 1
lambda_laser = 780.24e-9      # 激光波长 (m)
k = 2*np.pi / lambda_laser    # 波矢
g = 9.80665                   # 重力加速度 (m/s^2)
alpha = 1.35e-3               # alpha
#alpha = 0.6e-3               # alpha

noise_level = 0.01             # 10% 白噪声

# ----------- 横坐标 T^2 (ms^2) -----------
T2_ms2 = np.linspace(1, 120, 600)

# 转换为 s^2
T2_s2 = T2_ms2 * 1e-6

# ----------- 原始干涉信号 (0-1概率) -----------
P_clean = 0.5 * (1 + np.cos(2 * n * k * alpha * g * T2_s2))

# ----------- alpha 加白噪声 -----------
alpha_noise = alpha * (1 + noise_level * np.random.randn(len(T2_s2)))

P_noise = 0.5 * (1 + np.cos(2 * n * k * alpha_noise * g * T2_s2))

# ----------- 绘图 -----------
plt.figure(figsize=(8,5))

plt.plot(T2_ms2, P_clean, label='Clean interferometer fringe', linewidth=2)
plt.plot(T2_ms2, P_noise, label='With 10% alpha noise', alpha=0.8)

plt.xlabel(r'$T^2$ (ms$^2$)', fontsize=12)
plt.ylabel('Probability P', fontsize=12)
plt.title('Atom Interferometer Fringe')

plt.ylim(-0.05,1.05)
plt.grid(True)
plt.legend()

plt.show()