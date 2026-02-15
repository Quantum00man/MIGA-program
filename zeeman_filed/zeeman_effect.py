import numpy as np
import matplotlib.pyplot as plt

# -------------------------------
# Constants and atomic parameters
# -------------------------------
mu_B = 9.274009994e-24   # Bohr magneton (J/T)
h = 6.62607015e-34       # Planck constant (J·s)

# Rb-87 parameters
I = 3/2
J = 1/2
g_J = 2.00233113
g_I = -0.0009951414
delta_hfs = 6.8346826109e9  # Ground-state hyperfine splitting (Hz)

# -------------------------------
# Breit–Rabi formula
# -------------------------------
def breit_rabi(B_T):
    """
    Compute the Rb-87 ground-state hyperfine energies in a magnetic field B_T (Tesla)
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

# -------------------------------
# Magnetic field range (μT)
# -------------------------------
B_uT = np.linspace(0, 1000, 500)   # 0–1000 μT
B_T = B_uT * 1e-6

# -------------------------------
# Compute energies (Hz)
# -------------------------------
E1_levels = {mF: [] for mF in range(-1, 2)}
E2_levels = {mF: [] for mF in range(-2, 3)}

for B in B_T:
    E1, E2 = breit_rabi(B)
    for mF in E1:
        E1_levels[mF].append(E1[mF])
    for mF in E2:
        E2_levels[mF].append(E2[mF])

# -------------------------------
# Plot F=1
# -------------------------------
plt.figure(figsize=(7,5))
for mF, E in E1_levels.items():
    plt.plot(B_uT, np.array(E)/1e6, label=f'mF={mF}')
plt.xlabel('Magnetic field B (μT)', fontsize=12)
plt.ylabel('Energy (MHz)', fontsize=12)
plt.title('Rb-87 Ground State F=1 Hyperfine Zeeman Splitting', fontsize=13)
plt.legend(title="mF")
plt.grid(True)
plt.tight_layout()
plt.show()

# -------------------------------
# Plot F=2
# -------------------------------
plt.figure(figsize=(7,5))
for mF, E in E2_levels.items():
    plt.plot(B_uT, np.array(E)/1e6, label=f'mF={mF}')
plt.xlabel('Magnetic field B (μT)', fontsize=12)
plt.ylabel('Energy (MHz)', fontsize=12)
plt.title('Rb-87 Ground State F=2 Hyperfine Zeeman Splitting', fontsize=13)
plt.legend(title="mF")
plt.grid(True)
plt.tight_layout()
plt.show()
