import numpy as np

# ------------------------------------
# Constants and atomic parameters
# ------------------------------------
mu_B = 9.274009994e-24   # Bohr magneton (J/T)
h = 6.62607015e-34       # Planck constant (J·s)

# Rb-87 parameters
I = 3/2
J = 1/2
g_J = 2.00233113
g_I = -0.0009951414
delta_hfs = 6.8346826109e9  # Hyperfine splitting (Hz)

# ------------------------------------
# Breit–Rabi formula
# ------------------------------------
def breit_rabi(B_T):
    """
    Compute Rb-87 ground-state hyperfine energies at magnetic field B_T (Tesla)
    Returns dictionaries E1 (F=1) and E2 (F=2) with energies in Hz
    """
    x = (g_J - g_I) * mu_B * B_T / (h * delta_hfs)
    E1, E2 = {}, {}
    # F=1
    for mF in range(-1, 2):
        E1[mF] = (-delta_hfs / (2 * (2 * I + 1))
                  + g_I * mu_B * mF * B_T / h
                  - (delta_hfs / 2) * np.sqrt(1 + (4 * mF * x) / (2 * I + 1) + x**2))
    # F=2
    for mF in range(-2, 3):
        E2[mF] = (-delta_hfs / (2 * (2 * I + 1))
                  + g_I * mu_B * mF * B_T / h
                  + (delta_hfs / 2) * np.sqrt(1 + (4 * mF * x) / (2 * I + 1) + x**2))
    return E1, E2

# ------------------------------------
# Main calculation
# ------------------------------------
def transition_frequencies(B_uT):
    """Compute the 3 transitions at given magnetic field (μT)"""
    B_T = B_uT * 1e-6
    E1, E2 = breit_rabi(B_T)

    # Calculate transition frequencies (Hz)
    freq_plus1 = (E2[+1] - E1[+1]) / 1e6  # MHz
    freq_0     = (E2[0]  - E1[0])  / 1e6
    freq_minus1= (E2[-1] - E1[-1]) / 1e6

    print(f"\nMagnetic field: {B_uT:.3f} μT")
    print("--------------------------------------------")
    print(f"Δν(F=2,mF=+1 → F=1,mF=+1): {freq_plus1:.6f} MHz")
    print(f"Δν(F=2,mF= 0 → F=1,mF= 0): {freq_0:.6f} MHz")
    print(f"Δν(F=2,mF=-1 → F=1,mF=-1): {freq_minus1:.6f} MHz")
    print("--------------------------------------------")
    print(f"Zero-field splitting ≈ {delta_hfs/1e6:.6f} MHz")

# ------------------------------------
# User input
# ------------------------------------
if __name__ == "__main__":
    B_input = float(input("Enter magnetic field strength (μT): "))
    transition_frequencies(B_input)
