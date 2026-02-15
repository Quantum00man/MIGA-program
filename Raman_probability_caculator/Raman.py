import numpy as np
import matplotlib.pyplot as plt
from scipy.constants import pi, k as kB
import tkinter as tk
from tkinter import ttk

# -------------------- Physical Constants --------------------
vrec = 5.88e-3
sp = 0.5e-3
svL = 3.2 * vrec
svT = 3.2 * vrec
keff = 4 * pi / (780e-9)

Isat = 16.69
delta2 = 2 * pi * 157e6
desacc = -2 * pi * 1360e6
gamma = 2 * pi * 6.065e6

M = 1.443160e-25
wavelength = 780e-9

# -------------------- Distribution Functions --------------------
def f_v(v):
    return 0.5 / svL * np.sqrt(2 / pi) * np.exp(-0.5 * (v / svL) ** 2)

def h_r(r, T):
    sigma2 = sp ** 2 + (T ** 2) * svT ** 2
    return (1 / (2 * pi * sigma2)) * np.exp(-r ** 2 / (2 * sigma2))

# -------------------- Intensity and Rabi Functions --------------------
def Intens(P, r, w0):
    return 2 * P / (pi * w0 ** 2) * np.exp(-2 * r ** 2 / w0 ** 2)

def Weff(r, w0, attn, P1, P2):
    I1 = Intens(P1, r, w0)
    I2 = Intens(P2, r, w0)
    pre = gamma ** 2 / (2 * Isat) * (1 / (24 * desacc) + 1 / (8 * (desacc - delta2))) / 2
    return pre * np.sqrt(I1 * I2) / attn

def WR(r, delta, w0, attn, P1, P2):
    return np.sqrt(Weff(r, w0, attn, P1, P2) ** 2 + delta ** 2)

# -------------------- Transition Probability (Monte Carlo Integration) --------------------
def Ptrans(T=0.093, d=0, w0=2.5e-3, attn=1, P1=145e-3, P2=None, tau_vals=None, samples=10000):
    if P2 is None:
        P2 = P1 / 1.8
    if tau_vals is None:
        tau_vals = np.linspace(0, 40e-6, 200)

    vL_samples = np.random.normal(0, svL, samples)
    r_samples = np.sqrt(-2 * np.log(np.random.uniform(0, 1, samples))) * (np.sqrt(sp**2 + T**2 * svT**2))

    results = []
    for tau in tau_vals:
        total = 0
        for vL, r in zip(vL_samples, r_samples):
            delta = keff * vL - d
            wr = WR(r, delta, w0, attn, P1, P2)
            weff = Weff(r, w0, attn, P1, P2)
            if wr == 0:
                prob = 0
            else:
                prob = (weff / wr * np.sin(wr * tau / 2)) ** 2
            total += prob
        avg_prob = total / samples
        results.append(avg_prob)
    return tau_vals, np.array(results)

# -------------------- Visualization --------------------
def plot_rabi_multi(param_list, tau_range=(0, 40e-6), num_points=200):
    tau_vals = np.linspace(tau_range[0], tau_range[1], num_points)
    plt.figure()
    for T, d, w0, attn, P1, P2 in param_list:
        tau_vals, probs = Ptrans(T, d, w0, attn, P1, P2, tau_vals)
        max_prob = np.max(probs)
        max_tau = tau_vals[np.argmax(probs)]
        label = f"T={T}, w0={w0*1e3:.1f}mm, d={d}, P1={P1*1e3:.0f}mW, max={max_prob*100:.1f}% at {max_tau*1e6:.2f}µs"
        plt.plot(tau_vals * 1e6, probs * 100, label=label)
    plt.xlabel("Pulse Duration τ (µs)")
    plt.ylabel("Transition Probability (%)")
    plt.title("Rabi Oscillations")
    plt.grid(True)
    plt.legend()
    plt.show()

# -------------------- GUI --------------------
def launch_gui():
    root = tk.Tk()
    root.title("Raman Rabi Oscillation Calculator")

    entries = {}
    labels = ["T (s)", "d (Hz)", "w0 (mm)", "attn", "τ min (µs)", "τ max (µs)", "P1 (mW)", "P2 (mW, optional)"]
    defaults = ["0.096", "0", "2.5", "1", "0", "40", "145", ""]

    for i, (label, default) in enumerate(zip(labels, defaults)):
        tk.Label(root, text=label).grid(row=i, column=0)
        e = tk.Entry(root)
        e.insert(0, default)
        e.grid(row=i, column=1)
        entries[label] = e

    def run():
        try:
            T = float(entries["T (s)"].get())
            d = float(entries["d (Hz)"].get())
            w0 = float(entries["w0 (mm)"].get()) * 1e-3
            attn = float(entries["attn"].get())
            tau_min = float(entries["τ min (µs)"].get()) * 1e-6
            tau_max = float(entries["τ max (µs)"].get()) * 1e-6
            P1 = float(entries["P1 (mW)"].get()) * 1e-3
            P2_text = entries["P2 (mW, optional)"].get()
            P2 = float(P2_text) * 1e-3 if P2_text else None
            plot_rabi_multi([(T, d, w0, attn, P1, P2)], tau_range=(tau_min, tau_max))
        except ValueError:
            print("Invalid input.")

    def run_multi():
        presets = [
            (0.093, 0, 2.5e-3, 1, 145e-3, None),
            (0.05, 0, 2.5e-3, 0.5, 145e-3, None),
            (0.093, 0, 1.5e-3, 1, 145e-3, None)
        ]
        plot_rabi_multi(presets)

    tk.Button(root, text="Plot", command=run).grid(row=len(labels), column=0)
    tk.Button(root, text="Plot Multiple", command=run_multi).grid(row=len(labels), column=1)
    root.mainloop()

# -------------------- Entry Point --------------------
if __name__ == "__main__":
    launch_gui()
