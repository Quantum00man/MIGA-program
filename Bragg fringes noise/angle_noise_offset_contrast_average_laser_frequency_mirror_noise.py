import numpy as np
import matplotlib.pyplot as plt

# =========================
# Parameters
# =========================
c = 299792458.0               # Speed of light (m/s)

n = 1
lambda_laser = 780.24e-9      # Laser wavelength (m)
k = 2 * np.pi / lambda_laser  # Wave vector (1/m)
nu0 = c / lambda_laser        # Laser optical frequency (Hz)

g = 9.80665                   # Gravitational acceleration (m/s^2)
alpha = 1.35e-3               # Alpha for clean AI phase model

contrast = 0.32                # Contrast C
offset = 0.22               # Probability offset
phase_offset = np.pi

average_time = 500            # Number of repeated measurements at each T^2 point
seed = 42                     # Random seed

middle_phase_threshold = 0.1  # In radians

# =========================
# Free-space noise parameters
# =========================
L = 2                       # Free-space propagation length (m)

# Mirror vibration noise (shot-to-shot RMS displacement)
sigma_x1 = 0               # Input mirror vibration RMS (m)
sigma_x2 = 0               # End mirror vibration RMS (m)

# Laser frequency noise (shot-to-shot RMS)
sigma_nu = 2e7              # Laser frequency fluctuation RMS (Hz)

# Optional: enable/disable each noise source
include_mirror_noise = True
include_laser_freq_noise = True

# =========================
# T^2 axis (ms^2)
# =========================
T2_ms2 = np.linspace(20, 150, 200)
T2_s2 = T2_ms2 * 1e-6

# =========================
# Clean signal
# =========================
phi_clean = 2 * n * k * alpha * g * T2_s2 + phase_offset
P_clean = offset + 0.5 * contrast * (1 + np.cos(phi_clean))

# =========================
# Repeated measurements with free-space phase noise
# =========================
rng = np.random.default_rng(seed)

# Shape: [number of T^2 points, average_time]
shape = (len(T2_s2), average_time)

# Mirror displacements
x1 = sigma_x1 * rng.standard_normal(shape) if include_mirror_noise else np.zeros(shape)
x2 = sigma_x2 * rng.standard_normal(shape) if include_mirror_noise else np.zeros(shape)

# Path-length fluctuation
delta_L = x2 - x1

# Laser frequency fluctuation
delta_nu = sigma_nu * rng.standard_normal(shape) if include_laser_freq_noise else np.zeros(shape)

# =========================
# Free-space phase noise:
# delta_phi = 2*k*deltaL + 2*L*deltak
#           = (4*pi/lambda)*deltaL + (4*pi*L/c)*delta_nu
# =========================
delta_phi_mirror = 2 * k * delta_L
delta_phi_laser = (4 * np.pi * L / c) * delta_nu
delta_phi_total = delta_phi_mirror + delta_phi_laser

# Add noise to the clean AI phase
phi_noise = phi_clean[:, np.newaxis] + delta_phi_total

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
# Print phase-noise RMS contributions
# =========================
phi_mirror_rms = np.std(delta_phi_mirror)
phi_laser_rms = np.std(delta_phi_laser)
phi_total_rms = np.std(delta_phi_total)

print("===== Free-space phase noise summary =====")
print(f"L = {L:.3f} m")
print(f"sigma_x1 = {sigma_x1:.3e} m")
print(f"sigma_x2 = {sigma_x2:.3e} m")
print(f"sigma_nu = {sigma_nu:.3e} Hz")
print(f"Mirror-induced phase RMS = {phi_mirror_rms:.3e} rad")
print(f"Laser-frequency phase RMS = {phi_laser_rms:.3e} rad")
print(f"Total phase RMS = {phi_total_rms:.3e} rad")

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

# Highlight middle fringe points
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

plt.title('Free-space AI Fringe with Mirror Vibration and Laser Frequency Noise')
plt.tight_layout()
plt.show()