from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from mot_model import (
    ATOM_MASSES_AMU,
    BODY_DIAGONAL_ANGLE_DEG,
    BODY_DIAGONAL_PROJECTION,
    G,
    LaunchParameters,
    axial_acceleration_m_s2,
    ballistic_apex_height_m,
    force_profile,
    ideal_launch_velocity_m_s,
    simulate_launch,
    steady_state_velocity,
    total_frequency_difference_mhz,
)

BG = "#f4f7fb"
SURFACE = "#ffffff"
SURFACE_ALT = "#e9eef6"
ACCENT = "#1d5fa7"
ACCENT_SOFT = "#dce8f7"
TEXT = "#17324d"
MUTED = "#5f738a"
SUCCESS = "#1f7a5f"
WARNING = "#b56900"
GRID = "#cad7e5"


def bi(zh: str, en: str) -> str:
    return f"{zh} / {en}"


ATOM_OPTION_LABELS = {
    key: key if key != "custom" else bi("自定义", "Custom") for key in ATOM_MASSES_AMU
}


class LaunchCalculatorApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(bi("3D MOT 发射速度计算器", "3D MOT Launch Velocity Calculator"))
        self.root.geometry("1480x960")
        self.root.minsize(1260, 860)
        self.root.configure(bg=BG)

        self._create_styles()
        self._create_variables()
        self._build_layout()
        self._bind_events()
        self._update_mass_entry_state()
        self.calculate()

    def _create_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure("App.TFrame", background=BG)
        style.configure("Surface.TFrame", background=SURFACE)
        style.configure("Section.TLabelframe", background=SURFACE, borderwidth=0)
        style.configure(
            "Section.TLabelframe.Label",
            background=SURFACE,
            foreground=TEXT,
            font=("Helvetica", 12, "bold"),
        )
        style.configure("Header.TLabel", background=BG, foreground=TEXT, font=("Helvetica", 22, "bold"))
        style.configure("SubHeader.TLabel", background=BG, foreground=MUTED, font=("Helvetica", 11))
        style.configure("Body.TLabel", background=SURFACE, foreground=TEXT, font=("Helvetica", 10))
        style.configure("Muted.TLabel", background=SURFACE, foreground=MUTED, font=("Helvetica", 9))
        style.configure("CardTitle.TLabel", background=SURFACE, foreground=MUTED, font=("Helvetica", 9, "bold"))
        style.configure("CardValue.TLabel", background=SURFACE, foreground=TEXT, font=("Helvetica", 16, "bold"))
        style.configure(
            "Accent.TButton",
            background=ACCENT,
            foreground="white",
            borderwidth=0,
            focusthickness=0,
            padding=(14, 9),
            font=("Helvetica", 10, "bold"),
        )
        style.map("Accent.TButton", background=[("active", "#174f8c")])
        style.configure(
            "Secondary.TButton",
            background=SURFACE_ALT,
            foreground=TEXT,
            borderwidth=0,
            padding=(14, 9),
            font=("Helvetica", 10),
        )
        style.map("Secondary.TButton", background=[("active", "#dae4f1")])
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(14, 8), font=("Helvetica", 10))
        style.map("TNotebook.Tab", background=[("selected", SURFACE)], foreground=[("selected", TEXT)])
        style.configure("TCheckbutton", background=SURFACE, foreground=TEXT, font=("Helvetica", 10))
        style.configure("TCombobox", fieldbackground=SURFACE, background=SURFACE)

    def _create_variables(self) -> None:
        self.delta_f_var = tk.StringVar(value="3.0")
        self.wavelength_var = tk.StringVar(value="780.0")
        self.atom_var = tk.StringVar(value=ATOM_OPTION_LABELS["87Rb"])
        self.mass_var = tk.StringVar(value=f"{ATOM_MASSES_AMU['87Rb']:.9f}")
        self.mean_detuning_var = tk.StringVar(value="-12.0")
        self.linewidth_var = tk.StringVar(value="6.065")
        self.saturation_var = tk.StringVar(value="0.30")
        self.interaction_time_var = tk.StringVar(value="3.0")
        self.include_gravity_var = tk.BooleanVar(value=True)

        self.result_vars = {
            "theta": tk.StringVar(value="--"),
            "delta_total": tk.StringVar(value="--"),
            "v_ideal": tk.StringVar(value="--"),
            "v_steady": tk.StringVar(value="--"),
            "v_sim": tk.StringVar(value="--"),
            "launch_height": tk.StringVar(value="--"),
            "apex_height": tk.StringVar(value="--"),
            "status": tk.StringVar(value=bi("等待计算", "Waiting for calculation")),
        }

        self.formula_text = tk.StringVar(value="")

    def _build_layout(self) -> None:
        outer = ttk.Frame(self.root, style="App.TFrame", padding=22)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer, style="App.TFrame")
        header.pack(fill="x")
        ttk.Label(
            header,
            text=bi("3D MOT 发射速度计算器", "3D MOT Launch Velocity Calculator"),
            style="Header.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            header,
            text=(
                "面向以立方体体对角线为竖直轴的 6 束 MOT 几何；输入的是 DOWN / UP 两组频率"
                "相对共同平均频率的单边偏移 Δf。\n"
                "Designed for a 6-beam MOT whose vertical axis follows the cube body diagonal; "
                "the input Δf is the single-sided frequency offset of the DOWN / UP groups from "
                "their shared mean frequency."
            ),
            style="SubHeader.TLabel",
            wraplength=1220,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        content = ttk.Frame(outer, style="App.TFrame")
        content.pack(fill="both", expand=True, pady=(18, 0))
        content.columnconfigure(0, weight=0)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        self.left_panel = ttk.Frame(content, style="Surface.TFrame", padding=18)
        self.left_panel.grid(row=0, column=0, sticky="nsw", padx=(0, 18))

        self.right_panel = ttk.Frame(content, style="App.TFrame")
        self.right_panel.grid(row=0, column=1, sticky="nsew")
        self.right_panel.rowconfigure(2, weight=1)
        self.right_panel.columnconfigure(0, weight=1)

        self._build_input_panel()
        self._build_result_panel()
        self._build_formula_panel()
        self._build_plot_panel()

    def _build_input_panel(self) -> None:
        basic_frame = ttk.LabelFrame(
            self.left_panel,
            text=bi("基础参数", "Basic Parameters"),
            style="Section.TLabelframe",
            padding=14,
        )
        basic_frame.pack(fill="x", pady=(0, 14))

        self._add_entry_row(
            basic_frame,
            bi("单边频移 Δf (MHz)", "Single-sided offset Δf (MHz)"),
            self.delta_f_var,
            bi("三束 DOWN 为 +Δf，三束 UP 为 -Δf。", "Three DOWN beams use +Δf and three UP beams use -Δf."),
        )
        self._add_entry_row(
            basic_frame,
            bi("波长 λ (nm)", "Wavelength λ (nm)"),
            self.wavelength_var,
            bi("默认 780 nm，对应 Rb D2 线。", "Default: 780 nm for the Rb D2 line."),
        )

        atom_label = ttk.Label(basic_frame, text=bi("原子种类", "Atomic species"), style="Body.TLabel")
        atom_label.grid(row=4, column=0, sticky="w", pady=(6, 0))
        atom_box = ttk.Combobox(
            basic_frame,
            textvariable=self.atom_var,
            state="readonly",
            values=[ATOM_OPTION_LABELS[key] for key in ATOM_MASSES_AMU],
            width=18,
        )
        atom_box.grid(row=4, column=1, sticky="ew", padx=(12, 0), pady=(6, 0))
        atom_box.bind("<<ComboboxSelected>>", lambda _event: self._update_mass_entry_state())

        self._mass_label = ttk.Label(basic_frame, text=bi("原子质量 (amu)", "Atomic mass (amu)"), style="Body.TLabel")
        self._mass_label.grid(row=5, column=0, sticky="w", pady=(6, 0))
        self.mass_entry = ttk.Entry(basic_frame, textvariable=self.mass_var, width=20)
        self.mass_entry.grid(row=5, column=1, sticky="ew", padx=(12, 0), pady=(6, 0))
        ttk.Label(
            basic_frame,
            text=bi("预设质量会自动填入；若选自定义可自行修改。", "Preset masses autofill; choose Custom to edit."),
            style="Muted.TLabel",
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(3, 0))

        advanced_frame = ttk.LabelFrame(
            self.left_panel,
            text=bi("高级散射模型", "Advanced Scattering Model"),
            style="Section.TLabelframe",
            padding=14,
        )
        advanced_frame.pack(fill="x", pady=(0, 14))

        self._add_entry_row(
            advanced_frame,
            bi("平均失谐 Δ0 (MHz)", "Mean detuning Δ0 (MHz)"),
            self.mean_detuning_var,
            bi("相对原子共振频率；通常取负值。", "Relative to atomic resonance; usually negative."),
        )
        self._add_entry_row(
            advanced_frame,
            bi("线宽 Γ/2π (MHz)", "Linewidth Γ/2π (MHz)"),
            self.linewidth_var,
            bi("默认 6.065 MHz，适用于 Rb D2 线。", "Default: 6.065 MHz for the Rb D2 line."),
        )
        self._add_entry_row(
            advanced_frame,
            bi("单束饱和参数 s0", "Single-beam saturation s0"),
            self.saturation_var,
            bi("使用六束总饱和近似：sΣ ≈ 6s0。", "Uses the six-beam saturation approximation: sΣ ≈ 6s0."),
        )
        self._add_entry_row(
            advanced_frame,
            bi("发射作用时间 (ms)", "Launch interaction time (ms)"),
            self.interaction_time_var,
            bi("数值积分从静止原子出发得到有限时间速度。", "Integrates from rest to get the finite-time velocity."),
        )

        gravity_check = ttk.Checkbutton(
            advanced_frame,
            text=bi("计入重力修正", "Include gravity"),
            variable=self.include_gravity_var,
        )
        gravity_check.grid(row=8, column=0, columnspan=2, sticky="w", pady=(8, 0))

        action_frame = ttk.Frame(self.left_panel, style="Surface.TFrame")
        action_frame.pack(fill="x")
        ttk.Button(action_frame, text=bi("计算并绘图", "Calculate & Plot"), style="Accent.TButton", command=self.calculate).pack(
            fill="x", pady=(0, 10)
        )
        ttk.Button(
            action_frame,
            text=bi("恢复默认值", "Reset Defaults"),
            style="Secondary.TButton",
            command=self.reset_defaults,
        ).pack(fill="x")

        note_frame = ttk.LabelFrame(
            self.left_panel,
            text=bi("输入约定", "Input Convention"),
            style="Section.TLabelframe",
            padding=14,
        )
        note_frame.pack(fill="both", expand=True, pady=(14, 0))
        note_text = (
            "1. 本程序中的 Δf 指每组三束光相对共同平均频率的单边偏移。\n"
            "   Here Δf is the single-sided offset of each three-beam group from the shared mean frequency.\n"
            "2. 若你手里的是 UP 与 DOWN 的总频差 Δf_total，请先输入 Δf = Δf_total / 2。\n"
            "   If you have the total UP-DOWN frequency gap Δf_total, enter Δf = Δf_total / 2.\n"
            "3. 理想模型只由几何与频差决定；高级模型额外考虑线宽、饱和、重力与有限发射时间。\n"
            "   The ideal model depends only on geometry and frequency offset; the advanced model also includes linewidth, saturation, gravity, and finite launch time."
        )
        ttk.Label(note_frame, text=note_text, style="Body.TLabel", wraplength=360, justify="left").pack(anchor="w")

    def _build_result_panel(self) -> None:
        results_frame = ttk.Frame(self.right_panel, style="App.TFrame")
        results_frame.grid(row=0, column=0, sticky="ew")
        for column in range(3):
            results_frame.columnconfigure(column, weight=1)

        cards = [
            (bi("几何夹角 θ", "Beam angle θ"), "theta"),
            (bi("总频差 2Δf", "Total 2Δf"), "delta_total"),
            (bi("理想发射速度", "Ideal velocity"), "v_ideal"),
            (bi("稳态速度", "Steady velocity"), "v_steady"),
            (bi("有限时间速度", "Finite-time velocity"), "v_sim"),
            (bi("发射段位移", "Launch displacement"), "launch_height"),
            (bi("抛体顶点高度", "Ballistic apex"), "apex_height"),
        ]

        for index, (title, key) in enumerate(cards):
            row = index // 3
            column = index % 3
            card = tk.Frame(results_frame, bg=SURFACE, highlightthickness=1, highlightbackground=ACCENT_SOFT)
            card.grid(row=row, column=column, sticky="nsew", padx=(0, 14 if column < 2 else 0), pady=(0, 14))
            accent_bar = tk.Frame(card, bg=ACCENT, height=5)
            accent_bar.pack(fill="x")
            content = ttk.Frame(card, style="Surface.TFrame", padding=14)
            content.pack(fill="both", expand=True)
            ttk.Label(content, text=title, style="CardTitle.TLabel").pack(anchor="w")
            ttk.Label(content, textvariable=self.result_vars[key], style="CardValue.TLabel").pack(anchor="w", pady=(12, 0))

        status_frame = tk.Frame(results_frame, bg=SURFACE, highlightthickness=1, highlightbackground=ACCENT_SOFT)
        status_frame.grid(row=2, column=1, columnspan=2, sticky="nsew", pady=(0, 14))
        status_bar = tk.Frame(status_frame, bg=SUCCESS, height=5)
        status_bar.pack(fill="x")
        status_content = ttk.Frame(status_frame, style="Surface.TFrame", padding=14)
        status_content.pack(fill="both", expand=True)
        ttk.Label(status_content, text=bi("求解状态", "Solver status"), style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(status_content, textvariable=self.result_vars["status"], style="Body.TLabel", wraplength=360, justify="left").pack(
            anchor="w", pady=(10, 0)
        )

    def _build_formula_panel(self) -> None:
        formula_frame = ttk.LabelFrame(
            self.right_panel,
            text=bi("模型说明", "Model summary"),
            style="Section.TLabelframe",
            padding=14,
        )
        formula_frame.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        self.formula_label = ttk.Label(
            formula_frame,
            textvariable=self.formula_text,
            style="Body.TLabel",
            justify="left",
            wraplength=980,
        )
        self.formula_label.pack(anchor="w")

    def _build_plot_panel(self) -> None:
        plot_shell = ttk.Frame(self.right_panel, style="App.TFrame")
        plot_shell.grid(row=2, column=0, sticky="nsew")
        plot_shell.rowconfigure(0, weight=1)
        plot_shell.columnconfigure(0, weight=1)

        notebook = ttk.Notebook(plot_shell)
        notebook.grid(row=0, column=0, sticky="nsew")

        acceleration_tab = ttk.Frame(notebook, style="Surface.TFrame")
        trajectory_tab = ttk.Frame(notebook, style="Surface.TFrame")
        notebook.add(acceleration_tab, text=bi("轴向加速度 a(v)", "Axial acceleration a(v)"))
        notebook.add(trajectory_tab, text=bi("速度演化 v(t)", "Velocity evolution v(t)"))

        self.force_canvas = tk.Canvas(acceleration_tab, bg=SURFACE, highlightthickness=0)
        self.force_canvas.pack(fill="both", expand=True)

        self.trajectory_canvas = tk.Canvas(trajectory_tab, bg=SURFACE, highlightthickness=0)
        self.trajectory_canvas.pack(fill="both", expand=True)

        self.force_canvas.bind("<Configure>", lambda _event: self.calculate(show_errors=False))
        self.trajectory_canvas.bind("<Configure>", lambda _event: self.calculate(show_errors=False))

    def _bind_events(self) -> None:
        self.root.bind("<Return>", lambda _event: self.calculate())

    def _add_entry_row(self, parent: ttk.LabelFrame, label_text: str, variable: tk.StringVar, helper: str) -> None:
        row = parent.grid_size()[1]
        ttk.Label(parent, text=label_text, style="Body.TLabel").grid(row=row, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(parent, textvariable=variable, width=20).grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=(6, 0))
        ttk.Label(parent, text=helper, style="Muted.TLabel").grid(row=row + 1, column=0, columnspan=2, sticky="w", pady=(3, 0))
        parent.columnconfigure(1, weight=1)

    def _selected_atom_key(self) -> str:
        atom_label = self.atom_var.get()
        for key, display in ATOM_OPTION_LABELS.items():
            if atom_label in (key, display):
                return key
        return atom_label

    def _update_mass_entry_state(self) -> None:
        atom = self._selected_atom_key()
        if atom != "custom":
            self.mass_var.set(f"{ATOM_MASSES_AMU[atom]:.9f}")
            self.mass_entry.state(["disabled"])
        else:
            self.mass_entry.state(["!disabled"])

    def reset_defaults(self) -> None:
        self.delta_f_var.set("3.0")
        self.wavelength_var.set("780.0")
        self.atom_var.set(ATOM_OPTION_LABELS["87Rb"])
        self.mass_var.set(f"{ATOM_MASSES_AMU['87Rb']:.9f}")
        self.mean_detuning_var.set("-12.0")
        self.linewidth_var.set("6.065")
        self.saturation_var.set("0.30")
        self.interaction_time_var.set("3.0")
        self.include_gravity_var.set(True)
        self._update_mass_entry_state()
        self.calculate()

    def _read_parameters(self) -> LaunchParameters:
        atom_key = self._selected_atom_key()
        mass_amu = float(self.mass_var.get()) if atom_key == "custom" else ATOM_MASSES_AMU[atom_key]

        return LaunchParameters(
            delta_f_mhz=float(self.delta_f_var.get()),
            wavelength_nm=float(self.wavelength_var.get()),
            mean_detuning_mhz=float(self.mean_detuning_var.get()),
            linewidth_mhz=float(self.linewidth_var.get()),
            saturation_parameter=float(self.saturation_var.get()),
            interaction_time_ms=float(self.interaction_time_var.get()),
            mass_amu=mass_amu,
            include_gravity=self.include_gravity_var.get(),
            projection=BODY_DIAGONAL_PROJECTION,
        )

    def calculate(self, show_errors: bool = True) -> None:
        try:
            params = self._read_parameters()

            ideal_velocity = ideal_launch_velocity_m_s(params)
            steady_result = steady_state_velocity(params)
            simulation = simulate_launch(params)
            velocities, forces = force_profile(params, points=401)
            accelerations = [force / (params.mass_amu * 1.660_539_066_60e-27) for force in forces]

            self.result_vars["theta"].set(f"{BODY_DIAGONAL_ANGLE_DEG:.3f}°")
            self.result_vars["delta_total"].set(f"{total_frequency_difference_mhz(params):.3f} MHz")
            self.result_vars["v_ideal"].set(f"{ideal_velocity:.4f} m/s")
            self.result_vars["v_steady"].set(f"{steady_result.velocity_m_s:.4f} m/s")
            self.result_vars["v_sim"].set(f"{simulation.final_velocity_m_s:.4f} m/s")
            self.result_vars["launch_height"].set(f"{simulation.final_height_m * 1e3:.3f} mm")
            apex = ballistic_apex_height_m(simulation.final_height_m, simulation.final_velocity_m_s)
            self.result_vars["apex_height"].set(f"{apex * 1e3:.3f} mm")

            if steady_result.converged:
                status = (
                    "在所设参数下，轴向辐射压力与重力的平衡点已找到。"
                    f" 残余力约 {steady_result.residual_force_n:.2e} N。\n"
                    "A force-balance point between axial radiation pressure and gravity was found."
                    f" Residual force ≈ {steady_result.residual_force_n:.2e} N."
                )
            else:
                status = (
                    "未在扫描范围内找到严格零点，已返回最小残余力附近的速度。"
                    f" 当前残余力约 {steady_result.residual_force_n:.2e} N。\n"
                    "No exact zero crossing was found in the scan range, so the velocity with the smallest residual force was returned."
                    f" Current residual force ≈ {steady_result.residual_force_n:.2e} N."
                )
            self.result_vars["status"].set(status)

            self.formula_text.set(self._build_formula_summary(params, ideal_velocity, steady_result.velocity_m_s))
            self._draw_acceleration_plot(
                velocities=velocities,
                accelerations=accelerations,
                ideal_velocity=ideal_velocity,
                steady_velocity=steady_result.velocity_m_s,
            )
            self._draw_trajectory_plot(
                times_s=simulation.times_s,
                velocities=simulation.velocities_m_s,
                ideal_velocity=ideal_velocity,
                steady_velocity=steady_result.velocity_m_s,
            )
        except Exception as exc:  # noqa: BLE001
            if show_errors:
                messagebox.showerror(bi("输入或计算错误", "Input or Calculation Error"), str(exc))

    def _build_formula_summary(self, params: LaunchParameters, ideal_velocity: float, steady_velocity: float) -> str:
        delta_total = total_frequency_difference_mhz(params)
        upward_pull = axial_acceleration_m_s2(params, 0.0)
        gravity_text_zh = "已计入" if params.include_gravity else "未计入"
        gravity_text_en = "included" if params.include_gravity else "ignored"
        return (
            "几何：设发射轴为立方体体对角线，任一束光对轴向的投影因子为 "
            f"cosθ = 1/√3 ≈ {BODY_DIAGONAL_PROJECTION:.4f}，因此 θ = {BODY_DIAGONAL_ANGLE_DEG:.3f}°。\n"
            "Geometry: the launch axis is the cube body diagonal, so each beam contributes an axial projection factor "
            f"cosθ = 1/√3 ≈ {BODY_DIAGONAL_PROJECTION:.4f}, giving θ = {BODY_DIAGONAL_ANGLE_DEG:.3f}°.\n"
            "理想 moving-molasses 条件：δ_DOWN - k_z v = δ_UP + k_z v，其中 "
            "δ_DOWN = δ0 + 2πΔf、δ_UP = δ0 - 2πΔf、k_z = (2π/λ)/√3。\n"
            "Ideal moving-molasses condition: δ_DOWN - k_z v = δ_UP + k_z v, with "
            "δ_DOWN = δ0 + 2πΔf, δ_UP = δ0 - 2πΔf, and k_z = (2π/λ)/√3.\n"
            f"因此 v_ideal = λΔf / cosθ = √3 λΔf = {ideal_velocity:.4f} m/s；这里 Δf = {params.delta_f_mhz:.3f} MHz，"
            f"对应总频差 2Δf = {delta_total:.3f} MHz。\n"
            f"Therefore v_ideal = λΔf / cosθ = √3 λΔf = {ideal_velocity:.4f} m/s; here Δf = {params.delta_f_mhz:.3f} MHz "
            f"and the total UP-DOWN frequency difference is 2Δf = {delta_total:.3f} MHz.\n"
            "高级模型采用六束总饱和近似 sΣ ≈ 6s0，并计算 DOWN 与 UP 两组光在轴向上的净辐射压力；"
            f"{gravity_text_zh}重力。v = 0 处的初始轴向加速度约为 {upward_pull:.2f} m/s²，稳态速度约为 {steady_velocity:.4f} m/s。\n"
            "The advanced model uses the six-beam saturation approximation sΣ ≈ 6s0 and computes the net axial radiation pressure "
            f"from the DOWN and UP beam groups; gravity is {gravity_text_en}. The initial axial acceleration at v = 0 is about "
            f"{upward_pull:.2f} m/s², and the steady-state velocity is about {steady_velocity:.4f} m/s."
        )

    def _draw_acceleration_plot(
        self,
        velocities: list[float],
        accelerations: list[float],
        ideal_velocity: float,
        steady_velocity: float,
    ) -> None:
        self._draw_line_plot(
            canvas=self.force_canvas,
            xs=velocities,
            ys=accelerations,
            title=bi("轴向加速度 a(v)", "Axial acceleration a(v)"),
            x_label="速度 v / Velocity (m/s)",
            y_label="加速度 a / Accel. (m/s²)",
            highlight_xs=[
                (ideal_velocity, bi("理想", "Ideal"), ACCENT),
                (steady_velocity, bi("稳态", "Steady"), SUCCESS),
            ],
        )

    def _draw_trajectory_plot(
        self,
        times_s: list[float],
        velocities: list[float],
        ideal_velocity: float,
        steady_velocity: float,
    ) -> None:
        self._draw_line_plot(
            canvas=self.trajectory_canvas,
            xs=[time_s * 1e3 for time_s in times_s],
            ys=velocities,
            title=bi("有限时间发射速度演化", "Finite-time velocity evolution"),
            x_label="时间 t / Time (ms)",
            y_label="速度 v / Velocity (m/s)",
            highlight_ys=[
                (ideal_velocity, bi("理想", "Ideal"), ACCENT),
                (steady_velocity, bi("稳态", "Steady"), SUCCESS),
            ],
        )

    def _draw_line_plot(
        self,
        canvas: tk.Canvas,
        xs: list[float],
        ys: list[float],
        title: str,
        x_label: str,
        y_label: str,
        highlight_xs: list[tuple[float, str, str]] | None = None,
        highlight_ys: list[tuple[float, str, str]] | None = None,
    ) -> None:
        highlight_xs = highlight_xs or []
        highlight_ys = highlight_ys or []

        width = max(canvas.winfo_width(), 720)
        height = max(canvas.winfo_height(), 360)
        canvas.delete("all")

        left = 78
        right = 28
        top = 32
        bottom = 58
        plot_width = width - left - right
        plot_height = height - top - bottom

        x_min = min(xs)
        x_max = max(xs)
        y_min = min(min(ys), 0.0)
        y_max = max(max(ys), 0.0)

        if abs(x_max - x_min) < 1e-12:
            x_max = x_min + 1.0
        if abs(y_max - y_min) < 1e-12:
            y_max = y_min + 1.0

        y_padding = 0.08 * (y_max - y_min)
        y_min -= y_padding
        y_max += y_padding

        def map_x(value: float) -> float:
            return left + (value - x_min) / (x_max - x_min) * plot_width

        def map_y(value: float) -> float:
            return top + (y_max - value) / (y_max - y_min) * plot_height

        canvas.create_rectangle(left, top, left + plot_width, top + plot_height, outline=GRID, width=1)

        for index in range(6):
            fraction = index / 5
            x = left + fraction * plot_width
            y = top + fraction * plot_height
            canvas.create_line(x, top, x, top + plot_height, fill=GRID, dash=(2, 4))
            canvas.create_line(left, y, left + plot_width, y, fill=GRID, dash=(2, 4))

        zero_y = map_y(0.0)
        canvas.create_line(left, zero_y, left + plot_width, zero_y, fill=MUTED, width=1)

        points = []
        for x_value, y_value in zip(xs, ys, strict=True):
            points.extend((map_x(x_value), map_y(y_value)))
        canvas.create_line(*points, fill=ACCENT, width=2.5, smooth=False)

        for value, label, color in highlight_xs:
            x = map_x(value)
            canvas.create_line(x, top, x, top + plot_height, fill=color, dash=(5, 4), width=1.5)
            canvas.create_text(x + 4, top + 14, anchor="w", text=label, fill=color, font=("Helvetica", 10, "bold"))

        for value, label, color in highlight_ys:
            y = map_y(value)
            canvas.create_line(left, y, left + plot_width, y, fill=color, dash=(5, 4), width=1.5)
            canvas.create_text(left + 8, y - 8, anchor="w", text=label, fill=color, font=("Helvetica", 10, "bold"))

        canvas.create_text(left, 16, anchor="w", text=title, fill=TEXT, font=("Helvetica", 13, "bold"))
        canvas.create_text(left + plot_width / 2, height - 18, anchor="center", text=x_label, fill=MUTED, font=("Helvetica", 10))
        canvas.create_text(24, top + plot_height / 2, anchor="center", text=y_label, fill=MUTED, font=("Helvetica", 10), angle=90)

        canvas.create_text(left, top + plot_height + 18, anchor="w", text=f"{x_min:.2f}", fill=MUTED, font=("Helvetica", 9))
        canvas.create_text(left + plot_width, top + plot_height + 18, anchor="e", text=f"{x_max:.2f}", fill=MUTED, font=("Helvetica", 9))
        canvas.create_text(left - 10, top + plot_height, anchor="e", text=f"{y_min:.1f}", fill=MUTED, font=("Helvetica", 9))
        canvas.create_text(left - 10, top, anchor="e", text=f"{y_max:.1f}", fill=MUTED, font=("Helvetica", 9))

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    LaunchCalculatorApp().run()
