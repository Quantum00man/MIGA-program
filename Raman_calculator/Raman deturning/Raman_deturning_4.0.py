import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox

# Constants
vz = 3.34778  # m/s
alpha_deg = 4.9678  # degrees
alpha_rad = np.deg2rad(alpha_deg)
lambda_laser = 780e-9  # m
k = 2 * np.pi / lambda_laser
keff = 2 * k
wr = 2 * np.pi * 15.093e3  # rad/s

def compute_detuning_kHz(vx_mm, trans_case):
    vx = vx_mm / 1000
    term1 = keff * vz * np.sin(alpha_rad)
    term2 = keff * vx * np.cos(alpha_rad)
    # F1->F2: +wr, F2->F1: -wr
    wr_sign = 1 if trans_case == "F1→F2" else -1
    delta_flying_up_pos =  term1 + term2 + wr_sign * wr
    delta_flying_up_neg = -term1 - term2 + wr_sign * wr
    delta_falling_down_pos = term1 - term2 + wr_sign * wr
    delta_falling_down_neg = -term1 + term2 + wr_sign * wr
    to_kHz = lambda omega: omega / (2 * np.pi * 1000)
    return {
        "flying up, Δ>0": to_kHz(delta_flying_up_pos),
        "flying up, Δ<0": to_kHz(delta_flying_up_neg),
        "falling down, Δ>0": to_kHz(delta_falling_down_pos),
        "falling down, Δ<0": to_kHz(delta_falling_down_neg)
    }

def compute_vx_from_detuning_auto(delt_kHz, up_or_down, trans_case):
    delt = delt_kHz * 2 * np.pi * 1000
    term1 = keff * vz * np.sin(alpha_rad)
    coef = keff * np.cos(alpha_rad)
    wr_sign = 1 if trans_case == "F1→F2" else -1
    if up_or_down == "flying up":
        if delt_kHz >= 0:
            vx = (delt - term1 - wr_sign * wr) / coef
            used_case = "flying up, Δ>0"
        else:
            vx = -(delt - wr_sign * wr + term1) / coef
            used_case = "flying up, Δ<0"
    elif up_or_down == "falling down":
        if delt_kHz >= 0:
            vx = -(delt - term1 - wr_sign * wr) / coef
            used_case = "falling down, Δ>0"
        else:
            vx = (delt - wr_sign * wr + term1) / coef
            used_case = "falling down, Δ<0"
    else:
        raise ValueError("Invalid up/down selection.")
    return vx * 1000, used_case  # mm/s, and formula used

class RamanGUI:
    def __init__(self, root):
        self.root = root
        root.title("Raman Detuning Calculator")

        self.mode = tk.StringVar(value="vx2detuning")
        self.input_label_var = tk.StringVar(value="vx (mm/s):")
        self.input_var = tk.StringVar()
        self.updown_var = tk.StringVar(value="flying up")
        self.trans_case_var = tk.StringVar(value="F1→F2")
        self.result_var = tk.StringVar()

        # Mode selection
        mode_frame = tk.LabelFrame(root, text="Choose Function")
        mode_frame.pack(fill="x", padx=10, pady=5)
        tk.Radiobutton(mode_frame, text="vx → Detuning", variable=self.mode, value="vx2detuning", command=self.update_input_label).pack(side="left", padx=10)
        tk.Radiobutton(mode_frame, text="Detuning → vx", variable=self.mode, value="detuning2vx", command=self.update_input_label).pack(side="left", padx=10)

        # Input frame
        input_frame = tk.Frame(root)
        input_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(input_frame, textvariable=self.input_label_var, width=16, anchor="w").pack(side="left")
        tk.Entry(input_frame, textvariable=self.input_var, width=16).pack(side="left")

        # Up/Down selection
        tk.Label(input_frame, text="Mode:", anchor="w").pack(side="left", padx=(20,0))
        self.updown_menu = ttk.Combobox(input_frame, values=["flying up", "falling down"], state="readonly", width=13)
        self.updown_menu.current(0)
        self.updown_menu.pack(side="left")
        self.updown_menu.bind("<<ComboboxSelected>>", self.updown_selected)

        # F1-F2/F2-F1 selection
        tk.Label(input_frame, text="Transition:", anchor="w").pack(side="left", padx=(20,0))
        self.trans_case_menu = ttk.Combobox(input_frame, values=["F1→F2", "F2→F1"], state="readonly", width=8)
        self.trans_case_menu.current(0)
        self.trans_case_menu.pack(side="left")
        self.trans_case_menu.bind("<<ComboboxSelected>>", self.trans_case_selected)

        # Calculate button
        tk.Button(root, text="Calculate", command=self.calculate).pack(pady=8)

        # Result
        tk.Label(root, textvariable=self.result_var, font=("Arial", 12, "bold"), fg="blue").pack(pady=5)

    def update_input_label(self):
        if self.mode.get() == "vx2detuning":
            self.input_label_var.set("vx (mm/s):")
        else:
            self.input_label_var.set("Detuning (kHz):")

    def updown_selected(self, event=None):
        self.updown_var.set(self.updown_menu.get())

    def trans_case_selected(self, event=None):
        self.trans_case_var.set(self.trans_case_menu.get())

    def calculate(self):
        try:
            val = float(self.input_var.get())
        except ValueError:
            messagebox.showerror("Input Error", "Please enter a valid number.")
            return
        updown = self.updown_menu.get()
        trans_case = self.trans_case_menu.get()
        if self.mode.get() == "vx2detuning":
            detunings = compute_detuning_kHz(val, trans_case)
            result = f"Results (kHz) for {trans_case}:\n"
            for label, dval in detunings.items():
                result += f"{label}: {dval:.3f}\n"
        else:
            vx_mm, case_used = compute_vx_from_detuning_auto(val, updown, trans_case)
            result = f"vx = {vx_mm:.3f} mm/s\n(using {case_used} formula, {trans_case})"
        self.result_var.set(result)

if __name__ == "__main__":
    root = tk.Tk()
    app = RamanGUI(root)
    root.mainloop()
