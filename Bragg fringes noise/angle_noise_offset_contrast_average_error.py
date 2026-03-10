import numpy as np
import matplotlib.pyplot as plt

# =========================
# Parameters
# =========================
n = 1
lambda_laser = 780.24e-9      # Laser wavelength (m)
k = 2 * np.pi / lambda_laser  # Wave vector (1/m)
g = 9.80665                   # Gravitational acceleration (m/s^2)
alpha = 1.35e-3               # Alpha

noise_level = 0.1            # Relative noise level of alpha
contrast = 0.6                # Contrast C
offset = 0.0                  # Probability offset

average_time = 500             # Number of measurements averaged at each T^2 point
seed = 42                     # Random seed for reproducibility

# Phase threshold for selecting middle fringe points
middle_phase_threshold = 0.1 # In radians

# =========================
# T^2 axis (ms^2)
# =========================
T2_ms2 = np.linspace(20, 150, 200)
T2_s2 = T2_ms2 * 1e-6

# =========================
# Clean signal
# =========================
phase_offset = np.pi
phi_clean = 2 * n * k * alpha * g * T2_s2+ phase_offset
P_clean = offset + 0.5 * contrast * (1 + np.cos(phi_clean))

# =========================
# Noisy repeated measurements and averaging
# =========================
rng = np.random.default_rng(seed)

alpha_noise = alpha * (1 + noise_level * rng.standard_normal((len(T2_s2), average_time)))
T2_matrix = T2_s2[:, np.newaxis]

phi_noise = 2 * n * k * alpha_noise * g * T2_matrix + phase_offset
P_samples = offset + 0.5 * contrast * (1 + np.cos(phi_noise))

P_mean = np.mean(P_samples, axis=1)
P_std = np.std(P_samples, axis=1, ddof=1)
P_sem = P_std / np.sqrt(average_time)

# =========================
# Select middle fringe points by phase:
# phi ~= (m + 1/2) * pi
# =========================
phase_index = np.round(phi_clean / np.pi - 0.5)
phi_middle_nearest = (phase_index + 0.5) * np.pi
phase_distance = np.abs(phi_clean - phi_middle_nearest)

middle_mask = phase_distance < middle_phase_threshold

T2_middle = T2_ms2[middle_mask]
P_mean_middle = P_mean[middle_mask]
P_std_middle = P_std[middle_mask]
phi_middle_selected = phi_clean[middle_mask]

# =========================
# Plot with dual y-axis
# =========================
fig, ax1 = plt.subplots(figsize=(10, 6))

# Left y-axis: Probability P
ax1.plot(T2_ms2, P_clean, label='Clean fringe', linewidth=2)
ax1.errorbar(
    T2_ms2,
    P_mean,
    yerr=P_std,
    fmt='o-',
    markersize=4,
    capsize=3,
    linewidth=1.2,
    label=f'Noisy averaged data (N={average_time})'
)

# Highlight middle fringe points on the P curve
ax1.plot(
    T2_middle,
    P_mean_middle,
    's',
    markersize=6,
    label='Middle fringe points (phase selected)'
)

ax1.set_xlabel(r'$T^2$ (ms$^2$)', fontsize=12)
ax1.set_ylabel('Probability P', fontsize=12)
ax1.set_xlim(20, 150)
ax1.set_ylim(-0.05, 1.05)
ax1.grid(True)

# Right y-axis: STD deviation
ax2 = ax1.twinx()
ax2.plot(
    T2_middle,
    P_std_middle,
    'd--',
    linewidth=1.8,
    markersize=5,
    label='STD deviation at middle fringe'
)
ax2.set_ylabel('STD deviation', fontsize=12)

# Combine legends
lines_1, labels_1 = ax1.get_legend_handles_labels()
lines_2, labels_2 = ax2.get_legend_handles_labels()
ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc='best')

plt.title('Atom Interferometer Fringe and STD Deviation at Phase-Selected Middle Fringe')
plt.tight_layout()
plt.show()