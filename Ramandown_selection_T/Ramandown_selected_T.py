import math

# =========================
# Constants (fixed)
# =========================
kB = 1.380649e-23          # J/K
amu = 1.66053906660e-27    # kg

# Rb-87
MASS_RB87 = 86.909 * amu  # kg

# Laser wavelength
LAMBDA = 780.24e-9        # m

# Effective Raman wave vector (counter-propagating)
K_EFF = 4.0 * math.pi / LAMBDA


def temperature_from_fwhm_khz(fwhm_khz: float) -> float:
    """
    Compute the 1D atomic temperature (K) of Rb-87 from the Raman spectral
    line FWHM (kHz, relative frequency axis).

    Assumptions:
    - Counter-propagating Raman
    - A Doppler-dominated Gaussian line shape
    - FWHM is the frequency width measured directly from the curve
    """
    if fwhm_khz <= 0:
        raise ValueError("FWHM must be positive")

    # kHz -> Hz
    fwhm_hz = fwhm_khz * 1e3

    # FWHM -> sigma_nu
    sigma_nu = fwhm_hz / (2.0 * math.sqrt(2.0 * math.log(2.0)))

    # Frequency width -> velocity width
    sigma_v = (2.0 * math.pi / K_EFF) * sigma_nu

    # Temperature (1D)
    T = MASS_RB87 * sigma_v**2 / kB
    return T


# =========================
# Command-line usage
# =========================
if __name__ == "__main__":
    print("=== Raman FWHM -> Rb-87 Atomic Temperature (1D) ===")
    fwhm_khz = float(input("Please enter FWHM (kHz): ").strip())

    T = temperature_from_fwhm_khz(fwhm_khz)

    print(f"\nTemperature = {T:.6e} K")
    print(f"            = {T*1e6:.3f} µK")
