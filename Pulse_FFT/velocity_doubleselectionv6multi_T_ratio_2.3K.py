import numpy as np
import matplotlib.pyplot as plt

# -----------------------------
# Physical constants
# -----------------------------
hbar = 1.054571817e-34
kb = 1.380649e-23
m_rb87 = 1.44316060e-25
lambda_Rb = 780e-9

# -----------------------------
# Temperature and recoil
# -----------------------------
T = 2.3e-6
k = 2 * np.pi / lambda_Rb
v_rec = hbar * k / m_rb87
sigma_v = np.sqrt(kb * T / m_rb87)
k_eff = 2 * k  # counter-propagating beams

# -----------------------------
# sinc and distributions
# -----------------------------
def sinc(x):
    return np.sinc(x/np.pi)

def N_sel(v, sigma_sel):
    arg = np.pi * np.sqrt(1 + (v/sigma_sel)**2) / 2
    return ((np.pi/2)**2) * sinc(arg)**2

def thermal(v):
    return np.exp(-v**2/(2*sigma_v**2)) / (np.sqrt(2*np.pi)*sigma_v)

def get_fwhm(x, y):
    y_max = np.max(y)
    half_max = y_max * 0.5
    indices = np.where(y < half_max)[0]
    center_idx = np.argmin(np.abs(x))
    right_idx = indices[indices > center_idx][0]
    left_idx  = indices[indices < center_idx][-1]
    return x[right_idx] - x[left_idx]

# ===================================================================
# =============== USER-DEFINED π PULSE TIMES =========================
# ===================================================================

Tpi1_list = [115]     # μs (first selection)
Tpi2_list = [30,90,135]     # μs (second selection)

# ===================================================================
# ========================== Velocity Grid ============================
# ===================================================================

v = np.linspace(-10*sigma_v, 10*sigma_v, 4000)
thermal_v = thermal(v)
N_tot = np.trapz(thermal_v, v)

# ===================================================================
# ======================= FIRST SELECTION GROUP =======================
# ===================================================================

fig1, axs = plt.subplots(1, len(Tpi1_list), figsize=(6*len(Tpi1_list), 5))
if len(Tpi1_list) == 1:
    axs = [axs]

for idx, Tpi1_us in enumerate(Tpi1_list):

    Tpi1 = Tpi1_us * 1e-6
    Omega1 = np.pi / Tpi1
    sigma_sel1 = Omega1 / k_eff
    alpha1 = sigma_sel1 / v_rec

    # First selection distribution
    N1 = N_sel(v, sigma_sel1)
    P1 = N1 / np.max(N1)
    n1 = thermal_v * P1
    n1_norm = n1 / np.max(n1)

    # === Numerical remaining atoms ===
    N1_num = np.trapz(n1, v)

    # === Theoretical remaining atoms ===
    N1_th = 0.84 * N_tot * (sigma_sel1 / sigma_v)

    # ----- Effective temperature of n1 -----
    fwhm1 = get_fwhm(v, n1_norm)
    sigma_eff1 = fwhm1 / 2.335
    T_eff1 = m_rb87 * sigma_eff1**2 / kb * 1e6   # in μK

    # First convolution: thermal ⋆ P1
    resp1 = P1 / np.trapz(P1, v)
    conv1 = np.convolve(thermal_v, resp1, mode='same') * (v[1]-v[0])
    conv1_norm = conv1 / np.max(conv1)

    # ----- Effective temperature of conv1 -----
    fwhm_conv1 = get_fwhm(v, conv1_norm)
    sigma_eff_conv1 = fwhm_conv1 / 2.335
    T_eff_conv1 = m_rb87 * sigma_eff_conv1**2 / kb * 1e6  # μK

    # ----- Plot -----
    ax = axs[idx]
    ax.plot(
        v/v_rec,
        thermal_v/np.max(thermal_v),
        'k--',
        label="T = 2.3 μK (original)"
    )
    ax.plot(
        v/v_rec,
        n1_norm,
        label=(
            f"n1 after 1st sel (α={alpha1:.2f}, T_eff={T_eff1:.2f} μK)\n"
            f"N_num={N1_num/N_tot:.3f},  N_th={N1_th/N_tot:.3f}"
        )
    )
    ax.plot(
        v/v_rec,
        conv1_norm,
        label=f"conv1 (T_eff={T_eff_conv1:.2f} μK)"
    )

    ax.set_xlim(-15, 15)

    ax.axvline(alpha1/2, linestyle='--', color='C0')
    ax.axvline(-alpha1/2, linestyle='--', color='C0')

    ax.set_title(f"1st selection: Tπ1={Tpi1_us} μs")
    ax.set_xlabel("v / v_rec")
    ax.set_ylabel("Normalized")
    ax.grid(True)
    ax.legend(loc='upper right')

plt.tight_layout()
plt.show(block=False)

# ===================================================================
# ===================== SECOND SELECTION GROUPS ======================
# ===================================================================

for Tpi1_us in Tpi1_list:

    Tpi1 = Tpi1_us * 1e-6
    Omega1 = np.pi / Tpi1
    sigma_sel1 = Omega1 / k_eff
    alpha1 = sigma_sel1 / v_rec

    # First selection
    N1 = N_sel(v, sigma_sel1)
    P1 = N1 / np.max(N1)
    n1 = thermal_v * P1
    n1_norm = n1 / np.max(n1)

    fig, axs = plt.subplots(1, len(Tpi2_list), figsize=(6*len(Tpi2_list), 5))
    if len(Tpi2_list) == 1:
        axs = [axs]

    for j, Tpi2_us in enumerate(Tpi2_list):

        Tpi2 = Tpi2_us * 1e-6
        Omega2 = np.pi / Tpi2
        sigma_sel2 = Omega2 / k_eff
        alpha2 = sigma_sel2 / v_rec

        N2 = N_sel(v, sigma_sel2)
        P2 = N2 / np.max(N2)
        # ===== participating fraction at delta = 0 =====
        N1_tot = np.trapz(n1, v)
        N2_part = np.trapz(n1 * P2, v)
        eta2 = N2_part / N1_tot


        resp2 = P2 / np.trapz(P2, v)
        conv2 = np.convolve(n1, resp2, mode='same') * (v[1]-v[0])
        conv2_norm = conv2 / np.max(conv2)

        ax = axs[j]
        ax.plot(v/v_rec, n1_norm, label="ideal labelling spec (after 1st)")
        ax.plot(
            v/v_rec,
            P2/np.max(P2),
            '--',
            label=f"P2 (α={alpha2:.2f})"
        )
        ax.plot(v/v_rec, conv2_norm, label=f"conv2 (η2={eta2:.3f})")

        ax.axvline(2, color='red', linestyle='--')
        ax.axvline(-2, color='red', linestyle='--')

        ax.set_xlim(-10, 10)

        ax.set_title(f"Tπ1={Tpi1_us} μs, Tπ2={Tpi2_us} μs")
        ax.set_xlabel("v / v_rec")
        ax.set_ylabel("Normalized")
        ax.grid(True)
        ax.legend()

    plt.tight_layout()
    plt.show(block=False)

print("所有图已绘制，按 Enter 退出...")
input()
