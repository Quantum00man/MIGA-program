import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import quad

# =========================
# Physical constants
# =========================
hbar = 1.054571817e-34
epsilon_0 = 8.8541878128e-12
c = 299792458.0
pi = np.pi

# =========================
# Rb87 D2 parameters
# (same convention as your reference)
# =========================
Gamma = 2 * pi * 6.07e6       # rad/s
d = 2.0e-29                   # C*m
I_sat_cm2 = 1.6               # mW/cm^2
I_sat = I_sat_cm2 * 10.0      # W/m^2

# =========================
# Fixed experimental parameters
# =========================
P_per_beam = 65e-3            # W
w0 = 12e-3                    # m

# Peak intensity of one beam (fixed)
I0 = 2 * P_per_beam / (pi * w0**2)

# coefficient in Omega = A * I / Delta
A = d**2 / (hbar**2 * epsilon_0 * c)

def omega0_from_detuning(Delta):
    """Peak two-photon Rabi frequency for fixed power."""
    return A * I0 / Delta

def tau_for_pi_pulse(Delta):
    """Gaussian tau required for a pi pulse at fixed power."""
    Omega0 = abs(omega0_from_detuning(Delta))
    return pi / (Omega0 * np.sqrt(2 * pi))

def fwhm_from_tau(tau):
    """Convert Gaussian tau to intensity FWHM."""
    return 2 * np.sqrt(2 * np.log(2)) * tau

def scattering_probability_fixed_power_pi(Delta):
    """
    For a given detuning Delta:
    - keep power fixed
    - adjust pulse width to make a Gaussian pi pulse
    - compute spontaneous scattering probability
    """
    tau = tau_for_pi_pulse(Delta)

    def I_t(t):
        return I0 * np.exp(-t**2 / (2 * tau**2))

    def R_sc(t):
        It = I_t(t)
        numerator = 2 * It / I_sat
        denominator = 1 + 2 * It / I_sat + 4 * Delta**2 / Gamma**2
        return (Gamma / (4 * pi)) * (numerator / denominator)

    def Omega_t(t):
        return A * I_t(t) / Delta

    tmin = -10 * tau
    tmax =  10 * tau

    S, _ = quad(R_sc, tmin, tmax, limit=200)
    pulse_area, _ = quad(Omega_t, tmin, tmax, limit=200)

    return {
        "tau_s": tau,
        "FWHM_s": fwhm_from_tau(tau),
        "Omega0_rad_s": omega0_from_detuning(Delta),
        "pulse_area_rad": pulse_area,
        "S": S
    }

# =========================
# Scan detuning
# =========================
detuning_GHz = np.linspace(0.5, 10.0, 200)

tau_us_list = []
fwhm_us_list = []
S_list = []
pulse_area_over_pi_list = []

for delta_GHz in detuning_GHz:
    Delta = 2 * pi * delta_GHz * 1e9   # positive magnitude scan
    res = scattering_probability_fixed_power_pi(Delta)

    tau_us_list.append(res["tau_s"] * 1e6)
    fwhm_us_list.append(res["FWHM_s"] * 1e6)
    S_list.append(res["S"])
    pulse_area_over_pi_list.append(res["pulse_area_rad"] / pi)

tau_us_arr = np.array(tau_us_list)
fwhm_us_arr = np.array(fwhm_us_list)
S_arr = np.array(S_list)
pulse_area_over_pi_arr = np.array(pulse_area_over_pi_list)

# =========================
# Print example at 5 GHz
# =========================
idx_5GHz = np.argmin(np.abs(detuning_GHz - 5.0))

print("===== Fixed power scan, example near 5 GHz =====")
print(f"Detuning           = {detuning_GHz[idx_5GHz]:.3f} GHz")
print(f"I0                 = {I0:.3f} W/m^2 = {I0/10:.3f} mW/cm^2")
print(f"Required tau       = {tau_us_arr[idx_5GHz]:.3f} us")
print(f"Required FWHM      = {fwhm_us_arr[idx_5GHz]:.3f} us")
print(f"Pulse area / pi    = {pulse_area_over_pi_arr[idx_5GHz]:.6f}")
print(f"S                  = {S_arr[idx_5GHz]:.6e}")
print(f"S (%)              = {100*S_arr[idx_5GHz]:.6f} %")

# =========================
# Plot 1: spontaneous scattering
# =========================
plt.figure(figsize=(7,5))
plt.plot(detuning_GHz, 100 * S_arr)
plt.xlabel(r"Single-photon detuning magnitude $|\Delta|/2\pi$ (GHz)")
plt.ylabel("Spontaneous scattering per π pulse (%)")
plt.title("Spontaneous scattering vs detuning\n(fixed power, pulse width adjusted for π pulse)")
plt.grid(True)
plt.tight_layout()
plt.show()

# =========================
# Plot 2: required pulse width
# =========================
plt.figure(figsize=(7,5))
plt.plot(detuning_GHz, fwhm_us_arr)
plt.xlabel(r"Single-photon detuning magnitude $|\Delta|/2\pi$ (GHz)")
plt.ylabel("Required intensity FWHM for π pulse (us)")
plt.title("Pulse width vs detuning\n(fixed power per beam)")
plt.grid(True)
plt.tight_layout()
plt.show()