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

noise_level = 0.05            # Relative noise level of alpha
contrast = 0.6                # Contrast C
offset = 0.0                  # Probability offset

average_time = 5             # Number of measurements averaged at each T^2 point
seed = 42                     # Random seed for reproducibility

# =========================
# T^2 axis (ms^2)
# =========================
T2_ms2 = np.linspace(20, 120, 60)   # Fewer points to make error bars clearer
T2_s2 = T2_ms2 * 1e-6               # Convert to s^2

# =========================
# Clean signal
# =========================
phi_clean = 2 * n * k * alpha * g * T2_s2
P_clean = offset + 0.5 * contrast * (1 + np.cos(phi_clean))

# =========================
# Noisy repeated measurements and averaging
# =========================
rng = np.random.default_rng(seed)

# Create repeated noisy alpha values for each T^2 point
# Shape: (number_of_points, average_time)
alpha_noise = alpha * (1 + noise_level * rng.standard_normal((len(T2_s2), average_time)))

# Expand T2_s2 for vectorized calculation
T2_matrix = T2_s2[:, np.newaxis]

# Calculate noisy phase and noisy probability for every repetition
phi_noise = 2 * n * k * alpha_noise * g * T2_matrix
P_samples = offset + 0.5 * contrast * (1 + np.cos(phi_noise))

# Average result at each T^2 point
P_mean = np.mean(P_samples, axis=1)

# Error bar choice:
# Standard deviation of repeated measurements
P_std = np.std(P_samples, axis=1, ddof=1)

# Standard error of the mean
P_sem = P_std / np.sqrt(average_time)

# =========================
# Plot
# =========================
plt.figure(figsize=(9, 5))

plt.plot(T2_ms2, P_clean, label='Clean fringe', linewidth=2)

plt.errorbar(
    T2_ms2,
    P_mean,
    yerr=P_std,
    fmt='o-',
    markersize=4,
    capsize=3,
    linewidth=1.2,
    label=f'Noisy averaged data (N={average_time})'
)

plt.xlabel(r'$T^2$ (ms$^2$)', fontsize=12)
plt.ylabel('Probability P', fontsize=12)
plt.title('Atom Interferometer Fringe with Averaging and Error Bars')

plt.xlim(20, 120)
plt.ylim(-0.05, 1.05)
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.show()