import numpy as np
from scipy.integrate import quad

# =========================
# Physical constants
# =========================
hbar = 1.054571817e-34      # J*s
epsilon_0 = 8.8541878128e-12  # F/m
c = 299792458.0             # m/s
pi = np.pi

# =========================
# Rb87 D2 parameters
# (same convention as the reference)
# =========================
Gamma = 2 * pi * 6.07e6     # natural linewidth, rad/s
d = 2.0e-29                 # dipole moment, C*m
I_sat_cm2 = 1.6             # mW/cm^2
I_sat = I_sat_cm2 * 10.0    # convert mW/cm^2 -> W/m^2

# =========================
# Experimental parameters
# =========================
Delta = -2 * pi * 5.0e9     # detuning, rad/s
P_per_beam = 65e-3          # power per beam, W
w0 = 12e-3                  # beam waist (1/e^2 radius), m
FWHM_t = 43e-6              # Gaussian intensity FWHM, s

# =========================
# Convert FWHM to tau in:
# I(t) = I0 * exp(-t^2 / (2*tau^2))
# =========================
tau = FWHM_t / (2 * np.sqrt(2 * np.log(2)))

# Peak intensity of one Gaussian beam:
# I0 = 2P / (pi w0^2)
I0 = 2 * P_per_beam / (pi * w0**2)

# =========================
# Functions
# =========================
def I_t(t):
    """Single-beam intensity vs time."""
    return I0 * np.exp(-t**2 / (2 * tau**2))

def R_sc(t):
    """
    Spontaneous scattering rate from the reference:
    R(I(t), Delta) = Gamma/(4*pi) * [2 I(t)/I_sat] /
                     [1 + 2 I(t)/I_sat + 4 Delta^2 / Gamma^2]
    Note: 2*I(t) appears because the Bragg lattice is formed by two counter-propagating beams.
    """
    It = I_t(t)
    numerator = 2 * It / I_sat
    denominator = 1 + 2 * It / I_sat + 4 * Delta**2 / Gamma**2
    return (Gamma / (4 * pi)) * (numerator / denominator)

def Omega_t(t):
    """
    Two-photon Rabi frequency from the reference:
    Omega(t) = (d^2 / (hbar^2 * epsilon_0 * c)) * I(t) / Delta
    """
    return (d**2 / (hbar**2 * epsilon_0 * c)) * I_t(t) / Delta

# =========================
# Integrals
# =========================
# Total spontaneous-scattering probability
tmin = -10 * tau
tmax =  10 * tau

S, S_err = quad(R_sc, tmin, tmax)
pulse_area, pulse_area_err = quad(Omega_t, tmin, tmax)

# Peak two-photon Rabi frequency
Omega0 = Omega_t(0.0)

# =========================
# Print results
# =========================
print("===== Input parameters =====")
print(f"Gamma / 2pi      = {Gamma / (2*pi):.3e} Hz")
print(f"Delta / 2pi      = {Delta / (2*pi):.3e} Hz")
print(f"P per beam       = {P_per_beam*1e3:.3f} mW")
print(f"w0               = {w0*1e3:.3f} mm")
print(f"FWHM_t           = {FWHM_t*1e6:.3f} us")
print(f"tau              = {tau*1e6:.3f} us")
print(f"I_sat            = {I_sat:.3f} W/m^2")
print(f"I0 (per beam)    = {I0:.3f} W/m^2 = {I0/10:.3f} mW/cm^2")

print("\n===== Derived quantities =====")
print(f"Omega0           = {Omega0:.3e} rad/s")
print(f"Omega0 / 2pi     = {Omega0 / (2*pi):.3e} Hz")
print(f"Pulse area       = {pulse_area:.6f} rad")
print(f"Pulse area / pi  = {pulse_area/pi:.6f}")

print("\n===== Spontaneous scattering =====")
print(f"S                = {S:.6e}")
print(f"S (%)            = {100*S:.6f} %")