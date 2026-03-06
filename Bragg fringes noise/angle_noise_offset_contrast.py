import numpy as np
import matplotlib.pyplot as plt

# =========================
# 参数
# =========================
n = 1
lambda_laser = 780.24e-9      # 激光波长 (m)
k = 2 * np.pi / lambda_laser  # 波矢 (1/m)
g = 9.80665                   # 重力加速度 (m/s^2)
alpha = 1.35e-3               # 之前算出的 alpha

noise_level = 0.05            # alpha 的相对噪声，10%

# 可自定义参数
contrast = 0.6                # 对比度 C
offset = 0                  # 偏置 P_offset

# =========================
# 横坐标 T^2 (ms^2)
# =========================
T2_ms2 = np.linspace(20, 120, 600)
T2_s2 = T2_ms2 * 1e-6         # 转换成 s^2

# =========================
# 原始相位
# =========================
phi_clean = 2 * n * k * alpha * g * T2_s2

# 原始曲线：带 offset 和 contrast
P_clean = offset + 0.5 * contrast * (1 + np.cos(phi_clean))

# =========================
# alpha 加 10% 白噪声
# =========================
alpha_noise = alpha * (1 + noise_level * np.random.randn(len(T2_s2)))
phi_noise = 2 * n * k * alpha_noise * g * T2_s2

# 带噪声曲线
P_noise = offset + 0.5 * contrast * (1 + np.cos(phi_noise))

# 如果希望概率限制在 0~1，可裁剪
#P_clean = np.clip(P_clean, 0, 1)
#P_noise = np.clip(P_noise, 0, 1)

# =========================
# 绘图
# =========================
plt.figure(figsize=(9, 5))
plt.plot(T2_ms2, P_clean, label='Clean fringe', linewidth=2)
plt.plot(T2_ms2, P_noise, label='Noisy fringe (10% alpha noise)', alpha=0.8)

plt.xlabel(r'$T^2$ (ms$^2$)', fontsize=12)
plt.ylabel('Probability P', fontsize=12)
plt.title('Atom Interferometer Fringe with Offset and Contrast')

plt.xlim(20, 120)
plt.ylim(-0.05, 1.05)
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.show()