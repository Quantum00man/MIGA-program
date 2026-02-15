import numpy as np
from math import erf, sqrt, pi
import numpy as np
import matplotlib.pyplot as plt

# -----------------------------
# Physical constants
# -----------------------------
kB = 1.380649e-23            # J/K
amu = 1.66053906660e-27      # kg
m_rb87 = 87 * amu            # kg (Rb-87)

# -----------------------------
# Default detection geometry & motion
# -----------------------------
# Rectangular "bar" probe beam in x-y (uniform intensity):
BAR_WIDTH_Y = 0.01   # 1 cm  (meters)
BAR_LENGTH_X = 0.04  # 4 cm  (meters)

# Slab thickness along z (fall direction):
LZ = 0.01            # 1 cm (meters)

# Atom velocity along z through the detection region:
VZ = 3.7             # m/s

# Time-of-flight to the detection plane:
TOF = 0.065         # 800 ms (seconds)


def sigma_thermal(T_K: float, m: float = m_rb87) -> float:
    """Thermal RMS velocity scale: sqrt(kB*T/m)."""
    return sqrt(kB * T_K / m)


def sigma_at_time(sigma0: float, T_K: float, t: float, m: float = m_rb87) -> float:
    """RMS size after free expansion: sigma(t) = sqrt(sigma0^2 + (v_rms*t)^2)."""
    v_rms = sigma_thermal(T_K, m)
    return sqrt(sigma0**2 + (v_rms * t)**2)


def frac_in_rect_xy(sigma: float, x_half: float, y_half: float) -> float:
    """
    Fraction of a 2D Gaussian (RMS = sigma in both x and y) inside
    rectangle x∈[-x_half,x_half], y∈[-y_half,y_half].
    """
    ax = x_half / (sqrt(2) * sigma)
    ay = y_half / (sqrt(2) * sigma)
    return erf(ax) * erf(ay)


def gaussian_z_pdf(z: np.ndarray, sigma: float) -> np.ndarray:
    """1D Gaussian PDF with RMS sigma."""
    return np.exp(-0.5 * (z / sigma) ** 2) / (sqrt(2 * pi) * sigma)


def rect_slab_mask(z: np.ndarray, half_thickness: float) -> np.ndarray:
    """1 inside [-half_thickness, +half_thickness], else 0."""
    return (np.abs(z) <= half_thickness).astype(float)


def tof_fluorescence_signal(
    T_uK: float,
    D0_mm: float,
    tof: float = TOF,
    vz: float = VZ,
    lz: float = LZ,
    bar_length_x: float = BAR_LENGTH_X,
    bar_width_y: float = BAR_WIDTH_Y,
    t_window: float = 0.20,
    dt: float = 2e-4,
    relative_N: float = 1.0,
) -> dict:
    """
    Simulate fluorescence signal vs time as the cloud passes through a z-slab probe beam.
    Assumptions:
      - 3D isotropic Gaussian cloud at time = tof with RMS sigma (same in x,y,z).
      - Uniform rectangular probe beam in x-y, uniform slab in z of thickness lz.
      - Scattering rate per atom is constant (same I, same detuning), so signal ∝ illuminated atoms.
      - The cloud center crosses z=0 at t=0 with speed vz.
    Returns:
      dict with time array, signal array (relative), peak value, sigma(tof), xy fraction, etc.
    """

    # Units
    T_K = T_uK * 1e-6
    # Interpret input diameter as RMS diameter: D ≈ 2σ
    sigma0 = (D0_mm * 1e-3) / 2.0  # meters

    # Cloud RMS size at the detection time
    sigma = sigma_at_time(sigma0=sigma0, T_K=T_K, t=tof, m=m_rb87)

    # XY fraction inside the bar (time-independent if cloud shape doesn't change during crossing)
    x_half = bar_length_x / 2.0
    y_half = bar_width_y / 2.0
    f_xy = frac_in_rect_xy(sigma=sigma, x_half=x_half, y_half=y_half)

    # Time axis centered so that cloud center crosses z=0 at t=0
    t = np.arange(-t_window / 2, t_window / 2 + dt, dt)

    # Cloud center position vs time (z-axis)
    z_center = vz * t  # meters

    # For each time, illuminated fraction along z is the overlap integral:
    # f_z(t) = ∫ dz  Gaussian(z - z_center) * slab_mask(z)
    # = (Gaussian PDF shifted) convolved with rectangular window.
    # Numerically integrate on a z grid that covers several sigma.
    z_half = lz / 2.0
    z_max = max(6 * sigma + z_half, 0.05)  # ensure enough span; 5 cm min for stability
    dz = min(2e-4, sigma / 200 if sigma > 0 else 2e-4)  # adaptive-ish, capped
    z = np.arange(-z_max, z_max + dz, dz)
    slab = rect_slab_mask(z, z_half)

    # Compute f_z(t) via numerical integration
    f_z = np.empty_like(t)
    for i, zc in enumerate(z_center):
        pdf = gaussian_z_pdf(z - zc, sigma)
        f_z[i] = np.trapz(pdf * slab, z)

    # Total illuminated atoms fraction at time t
    f_illum = f_xy * f_z

    # Relative fluorescence signal (proportional to illuminated atoms)
    signal = relative_N * f_illum

    # Outputs
    peak = float(signal.max())
    t_peak = float(t[np.argmax(signal)])

    # Also provide an analytic peak factor for sanity:
    # f_z_peak_analytic = erf((lz/2)/(sqrt(2)*sigma))
    f_z_peak_analytic = erf((z_half) / (sqrt(2) * sigma))
    f_peak_analytic = f_xy * f_z_peak_analytic

    return {
        "t_s": t,
        "signal_rel": signal,
        "peak_rel": peak,
        "t_peak_s": t_peak,
        "sigma_tof_m": sigma,
        "sigma_tof_cm": sigma * 100,
        "f_xy": f_xy,
        "f_z_peak_analytic": f_z_peak_analytic,
        "peak_rel_analytic": f_peak_analytic,
        "params": {
            "T_uK": T_uK,
            "D0_mm": D0_mm,
            "tof_s": tof,
            "vz_mps": vz,
            "lz_m": lz,
            "bar_length_x_m": bar_length_x,
            "bar_width_y_m": bar_width_y,
        }
    }
def plot_tof(T_uK_list, D0_mm, title_suffix=""):
    plt.figure()
    peaks = []

    for T_uK in T_uK_list:
        out = tof_fluorescence_signal(
            T_uK=T_uK,
            D0_mm=D0_mm,
            tof=0.800,      # 800 ms
            vz=3.7,         # m/s
            lz=0.01,        # 1 cm
            t_window=0.20,  # 200 ms 
            dt=2e-4         # 0.2 ms 
        )

        t_ms = out["t_s"] * 1e3
        sig = out["signal_rel"]
        peaks.append(out["peak_rel"])

        plt.plot(t_ms, sig, label=f"T={T_uK} µK, peak={out['peak_rel']:.4g}")

    plt.xlabel("Time (ms)  [cloud center crosses z=0 at t=0]")
    plt.ylabel("Fluorescence signal (relative)")
    plt.title(f"TOF fluorescence @ 800 ms, D0={D0_mm} mm (RMS diameter){title_suffix}")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()

    # 
    if len(T_uK_list) == 2:
        ratio = peaks[0] / peaks[1]
        print(f"Peak ratio: {T_uK_list[0]} µK / {T_uK_list[1]} µK = {ratio:.3f}")
def compute_fwhm(t, y):
    """
    Compute FWHM of a single-peaked curve y(t).
    Returns (fwhm, t_left, t_right). If not found, returns (nan, nan, nan).
    """
    y = np.asarray(y)
    t = np.asarray(t)

    peak = y.max()
    half = 0.5 * peak

    above = y >= half
    if not np.any(above):
        return np.nan, np.nan, np.nan

    idx = np.where(above)[0]
    i_left, i_right = idx[0], idx[-1]

    # linear interpolation for better accuracy
    def interp(i1, i2):
        return t[i1] + (half - y[i1]) * (t[i2] - t[i1]) / (y[i2] - y[i1])

    t_left = interp(i_left - 1, i_left) if i_left > 0 else t[i_left]
    t_right = interp(i_right, i_right + 1) if i_right < len(t) - 1 else t[i_right]

    return t_right - t_left, t_left, t_right


def plot_tof_with_metrics(T_uK_list, D0_mm):
    plt.figure(figsize=(8, 5))

    for T_uK in T_uK_list:
        out = tof_fluorescence_signal(
            T_uK=T_uK,
            D0_mm=D0_mm,
            tof=0.065, #0.800
            vz=3.7,
            lz=0.01,
            t_window=0.060,
            dt=2e-4
        )

        t = out["t_s"]
        y = out["signal_rel"]

        # --- metrics ---
        peak = y.max()
        area = np.trapz(y, t)
        fwhm, tL, tR = compute_fwhm(t, y)

        # --- plot ---
        plt.plot(t * 1e3, y, label=f"T={T_uK} µK")

        # peak marker
        t_peak = t[np.argmax(y)]
        plt.plot(t_peak * 1e3, peak, "o")

        # FWHM marker
        plt.hlines(
            0.5 * peak,
            tL * 1e3,
            tR * 1e3,
            linestyles="dashed"
        )

        # annotation text
        text = (
            f"T = {T_uK} µK\n"
            f"Peak = {peak:.3g}\n"
            f"FWHM = {fwhm*1e3:.2f} ms\n"
            f"Area = {area:.3g}"
        )

        plt.text(
            0.02, 0.95 - 0.22 * T_uK_list.index(T_uK),
            text,
            transform=plt.gca().transAxes,
            verticalalignment="top",
            bbox=dict(boxstyle="round", alpha=0.85)
        )

    plt.xlabel("Time (ms)")
    plt.ylabel("Fluorescence signal (relative)")
    plt.title(f"TOF fluorescence @ {TOF}s, D0={D0_mm} mm (RMS diameter)")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()
#if __name__ == "__main__":
    # 示例 1：对比 5 µK vs 20 µK，初始直径 8.2 mm
   # plot_tof([5, 20], D0_mm=8.2)

    # 示例 2：只画一个温度
    # plot_tof([10], D0_mm=8.2)


# -----------------------------
# Example usage
# -----------------------------
'''if __name__ == "__main__":
    # Example: compare 5 uK vs 20 uK with same initial RMS diameter
    for T_uK in [5, 20]:
        out = tof_fluorescence_signal(T_uK=T_uK, D0_mm=10.0)  # D0=10 mm
        print(f"\nT = {T_uK} uK, D0 = 10 mm (RMS diameter)")
        print(f"  sigma(TOF=800ms) = {out['sigma_tof_cm']:.2f} cm")
        print(f"  f_xy = {out['f_xy']:.4f}")
        print(f"  peak_rel (numeric)   = {out['peak_rel']:.6f} at t={out['t_peak_s']*1e3:.2f} ms")
        print(f"  peak_rel (analytic)  = {out['peak_rel_analytic']:.6f}")
    plot_tof([5,20], D0_mm=8.2)

    # If you want to compute peak ratio directly:
    out5 = tof_fluorescence_signal(T_uK=5, D0_mm=8.2)
    out20 = tof_fluorescence_signal(T_uK=20, D0_mm=8.2)
    print("\nPeak ratio (5uK / 20uK) =", out5["peak_rel"] / out20["peak_rel"])
'''
if __name__ == "__main__":
    plot_tof_with_metrics([5, 20], D0_mm=8.2)
