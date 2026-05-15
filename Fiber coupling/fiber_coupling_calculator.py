#!/usr/bin/env python3
"""Single-mode fiber coupling calculator with a Tkinter UI.

The program uses Gaussian-mode overlap formulas for academic/engineering
estimates. Distances are entered in convenient laboratory units and converted
internally to SI units.
"""

from __future__ import annotations

import math
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk


NM = 1e-9
UM = 1e-6
MM = 1e-3
DEG = math.pi / 180.0


def safe_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class FiberParameters:
    wavelength_m: float
    mode_radius_m: float
    numerical_aperture: float
    core_index: float


@dataclass(frozen=True)
class BeamParameters:
    waist_radius_m: float
    distance_to_fiber_m: float
    wavefront_radius_m: float | None
    lateral_offset_m: float
    angular_tilt_rad: float


def rayleigh_range(waist_radius_m: float, wavelength_m: float, n: float = 1.0) -> float:
    return math.pi * n * waist_radius_m * waist_radius_m / wavelength_m


def gaussian_radius_at_z(waist_radius_m: float, wavelength_m: float, z_m: float, n: float = 1.0) -> float:
    z_r = rayleigh_range(waist_radius_m, wavelength_m, n)
    return waist_radius_m * math.sqrt(1.0 + (z_m / z_r) ** 2)


def gaussian_wavefront_radius(waist_radius_m: float, wavelength_m: float, z_m: float, n: float = 1.0) -> float | None:
    if abs(z_m) < 1e-15:
        return None
    z_r = rayleigh_range(waist_radius_m, wavelength_m, n)
    return z_m * (1.0 + (z_r / z_m) ** 2)


def gaussian_mode_overlap(
    wavelength_m: float,
    beam_radius_m: float,
    fiber_mode_radius_m: float,
    beam_wavefront_radius_m: float | None = None,
    fiber_wavefront_radius_m: float | None = None,
    lateral_offset_m: float = 0.0,
    angular_tilt_rad: float = 0.0,
) -> tuple[float, dict[str, float]]:
    """Return coupling efficiency and individual factors.

    The base overlap is for two coaxial Gaussian fields at the fiber facet:
    eta = 4 / [(w/wf + wf/w)^2 + (pi*w*wf/lambda * DeltaC)^2].
    Offset and tilt are first-order Gaussian penalties.
    """
    if wavelength_m <= 0 or beam_radius_m <= 0 or fiber_mode_radius_m <= 0:
        return 0.0, {"mode": 0.0, "offset": 0.0, "tilt": 0.0}

    inv_r_beam = 0.0 if beam_wavefront_radius_m in (None, 0.0) else 1.0 / beam_wavefront_radius_m
    inv_r_fiber = 0.0 if fiber_wavefront_radius_m in (None, 0.0) else 1.0 / fiber_wavefront_radius_m
    curvature_term = math.pi * beam_radius_m * fiber_mode_radius_m * (inv_r_beam - inv_r_fiber) / wavelength_m

    size_term = beam_radius_m / fiber_mode_radius_m + fiber_mode_radius_m / beam_radius_m
    eta_mode = 4.0 / (size_term * size_term + curvature_term * curvature_term)

    offset_factor = math.exp(-2.0 * lateral_offset_m * lateral_offset_m / (beam_radius_m**2 + fiber_mode_radius_m**2))
    tilt_factor = math.exp(
        -((2.0 * math.pi / wavelength_m) ** 2)
        * angular_tilt_rad**2
        * beam_radius_m**2
        * fiber_mode_radius_m**2
        / (2.0 * (beam_radius_m**2 + fiber_mode_radius_m**2))
    )
    eta_total = clamp(eta_mode * offset_factor * tilt_factor)
    return eta_total, {
        "mode": clamp(eta_mode),
        "offset": clamp(offset_factor),
        "tilt": clamp(tilt_factor),
        "curvature_term": curvature_term,
    }


def focused_waist_from_lens(wavelength_m: float, input_radius_m: float, focal_length_m: float, m2: float = 1.0) -> float:
    """Diffraction-limited thin-lens waist estimate for a collimated Gaussian beam."""
    if wavelength_m <= 0 or input_radius_m <= 0 or focal_length_m <= 0 or m2 <= 0:
        return 0.0
    return m2 * wavelength_m * focal_length_m / (math.pi * input_radius_m)


def required_focal_length(target_waist_m: float, wavelength_m: float, input_radius_m: float, m2: float = 1.0) -> float:
    if target_waist_m <= 0 or wavelength_m <= 0 or input_radius_m <= 0 or m2 <= 0:
        return 0.0
    return math.pi * input_radius_m * target_waist_m / (m2 * wavelength_m)


def required_input_radius(target_waist_m: float, wavelength_m: float, focal_length_m: float, m2: float = 1.0) -> float:
    if target_waist_m <= 0 or wavelength_m <= 0 or focal_length_m <= 0 or m2 <= 0:
        return 0.0
    return m2 * wavelength_m * focal_length_m / (math.pi * target_waist_m)


def mode_field_radius_from_v_number(core_radius_m: float, numerical_aperture: float, wavelength_m: float) -> tuple[float, float]:
    """Marcuse approximation for step-index single-mode fibers.

    w/a = 0.65 + 1.619/V^(3/2) + 2.879/V^6, valid mainly for 1.5 < V < 2.4.
    """
    if core_radius_m <= 0 or numerical_aperture <= 0 or wavelength_m <= 0:
        return 0.0, 0.0
    v_number = 2.0 * math.pi * core_radius_m * numerical_aperture / wavelength_m
    if v_number <= 0:
        return 0.0, v_number
    mode_radius = core_radius_m * (0.65 + 1.619 / (v_number**1.5) + 2.879 / (v_number**6))
    return mode_radius, v_number


TRANSLATIONS = {
    "en": {
        "window_title": "Single-Mode Fiber Coupling Calculator",
        "title": "Single-Mode Fiber Coupling Calculator",
        "language": "Language",
        "fiber_section": "Fiber Parameters",
        "beam_section": "Gaussian Beam at Fiber Facet",
        "lens_section": "Lens and Design Parameters",
        "results_section": "Results",
        "notes_section": "Model and Academic Notes",
        "calculate": "Calculate",
        "reset": "Reset defaults",
        "wavelength": "Wavelength lambda",
        "mfd": "Mode-field diameter MFD",
        "fiber_na": "Numerical aperture NA",
        "core_radius": "Core radius a",
        "core_index": "Core refractive index n",
        "beam_radius": "Beam radius w",
        "z_distance": "Waist-to-facet distance z",
        "offset": "Lateral offset d",
        "tilt": "Angular mismatch theta",
        "focal_length": "Lens focal length f",
        "input_radius": "Collimated beam radius win",
        "m2": "Beam quality factor M^2",
        "target_waist": "Target facet waist radius",
        "total_eta": "Total coupling efficiency eta",
        "mode_factor": "Mode/curvature overlap factor",
        "offset_factor": "Lateral-offset factor",
        "tilt_factor": "Angular-mismatch factor",
        "fiber_mode_radius": "Fiber mode radius wf",
        "beam_radius_facet": "Beam radius at facet w(z)",
        "rayleigh_length": "Input waist Rayleigh length zR",
        "wavefront_radius": "Facet wavefront radius R",
        "focused_waist": "Focused waist estimated from current lens w0",
        "suggest_f": "For target waist {target}, suggested focal length f",
        "suggest_win": "For fixed focal length {focal}, suggested input beam radius win",
        "v_number": "Step-index fiber V-number",
        "marcuse_radius": "Marcuse estimated mode radius",
        "acceptance_angle": "Approximate internal acceptance half-angle",
        "warning_header": "Notes:",
        "infinity": "infinity (waist located at facet)",
        "warn_positive": "Wavelength and mode-field diameter must be positive.",
        "warn_na": "NA should be positive; otherwise acceptance angle and V-number cannot be evaluated.",
        "warn_multimode": "V >= 2.405, so a step-index fiber may not be strictly single-mode; check core radius, NA, and wavelength.",
        "warn_marcuse": "The Marcuse mode-radius approximation has limited accuracy outside this V-number range.",
        "warn_mismatch": "The lens-estimated focus differs from the fiber mode radius by more than 20%; mode matching may be poor.",
        "warn_tilt": "Angular mismatch is approaching the fiber acceptance half-angle scale; practical alignment will be sensitive.",
        "warn_model": "Results use a scalar Gaussian approximation; high NA, lens aberrations, facet reflection, and polarization effects require additional corrections.",
        "notes": (
            "1. The single-mode fiber fundamental mode is approximated as an LP01 Gaussian mode. "
            "The entered MFD is treated as the 1/e^2 intensity diameter, and wf = MFD/2 is used as the mode radius.\n\n"
            "2. The facet coupling efficiency is computed from the normalized overlap integral of two Gaussian fields. "
            "Size and curvature mismatch enter the mode/curvature factor; lateral offset and small angular tilt are treated as Gaussian penalty factors.\n\n"
            "3. The lens estimate uses the thin-lens formula for a collimated Gaussian beam, "
            "w0 = M^2 lambda f/(pi win). A rigorous optical design should also include focal-length tolerance, clear aperture, aberration, coating, working distance, and mechanical adjustment range.\n\n"
            "4. The step-index fiber V-number is V = 2 pi a NA/lambda. The single-mode condition is V < 2.405. "
            "The Marcuse mode-radius approximation is mainly valid for 1.5 < V < 2.4.\n\n"
            "5. The default wavelength is 780.24 nm, suitable for experiments near the rubidium D2 line. Input units are shown in the interface."
        ),
    },
    "fr": {
        "window_title": "Calculateur de couplage dans une fibre monomode",
        "title": "Calculateur de couplage dans une fibre monomode",
        "language": "Langue",
        "fiber_section": "Parametres de la fibre",
        "beam_section": "Faisceau gaussien sur la face de fibre",
        "lens_section": "Lentille et parametres de conception",
        "results_section": "Resultats",
        "notes_section": "Modele et notes academiques",
        "calculate": "Calculer",
        "reset": "Valeurs par defaut",
        "wavelength": "Longueur d'onde lambda",
        "mfd": "Diametre de champ modal MFD",
        "fiber_na": "Ouverture numerique NA",
        "core_radius": "Rayon du coeur a",
        "core_index": "Indice du coeur n",
        "beam_radius": "Rayon du faisceau w",
        "z_distance": "Distance waist-face z",
        "offset": "Decalage lateral d",
        "tilt": "Desaccord angulaire theta",
        "focal_length": "Distance focale f",
        "input_radius": "Rayon du faisceau collimaté win",
        "m2": "Facteur de qualite M^2",
        "target_waist": "Rayon de waist cible sur la face",
        "total_eta": "Efficacite totale de couplage eta",
        "mode_factor": "Facteur de recouvrement mode/courbure",
        "offset_factor": "Facteur de decalage lateral",
        "tilt_factor": "Facteur de desaccord angulaire",
        "fiber_mode_radius": "Rayon de mode de la fibre wf",
        "beam_radius_facet": "Rayon du faisceau sur la face w(z)",
        "rayleigh_length": "Longueur de Rayleigh du waist incident zR",
        "wavefront_radius": "Rayon de courbure du front d'onde R",
        "focused_waist": "Waist focal estime avec la lentille courante w0",
        "suggest_f": "Pour un waist cible de {target}, distance focale conseillee f",
        "suggest_win": "Pour une focale fixe de {focal}, rayon incident conseille win",
        "v_number": "Nombre V de la fibre a saut d'indice",
        "marcuse_radius": "Rayon de mode estime par Marcuse",
        "acceptance_angle": "Demi-angle d'acceptance interne approx.",
        "warning_header": "Notes :",
        "infinity": "infini (waist place sur la face)",
        "warn_positive": "La longueur d'onde et le diametre de champ modal doivent etre positifs.",
        "warn_na": "La NA doit etre positive ; sinon l'angle d'acceptance et le nombre V ne peuvent pas etre evalues.",
        "warn_multimode": "V >= 2.405 : une fibre a saut d'indice peut ne pas etre strictement monomode ; verifier le rayon du coeur, la NA et la longueur d'onde.",
        "warn_marcuse": "L'approximation de Marcuse pour le rayon de mode est moins precise hors de cette plage de nombre V.",
        "warn_mismatch": "Le foyer estime par la lentille differe du rayon de mode de plus de 20 %, le couplage modal peut etre faible.",
        "warn_tilt": "Le desaccord angulaire approche l'echelle du demi-angle d'acceptance ; l'alignement pratique sera sensible.",
        "warn_model": "Les resultats utilisent une approximation gaussienne scalaire ; NA elevee, aberrations, reflexion de face et effets de polarisation demandent des corrections.",
        "notes": (
            "1. Le mode fondamental de la fibre monomode est approxime par un mode gaussien LP01. "
            "Le MFD saisi est traite comme le diametre d'intensite a 1/e^2, avec wf = MFD/2 comme rayon modal.\n\n"
            "2. L'efficacite de couplage sur la face est calculee par l'integrale de recouvrement normalisee de deux champs gaussiens. "
            "Les desaccords de taille et de courbure entrent dans le facteur mode/courbure ; le decalage lateral et la petite inclinaison angulaire sont traites comme des penalites gaussiennes.\n\n"
            "3. L'estimation par lentille utilise la formule de lentille mince pour un faisceau gaussien collimaté, "
            "w0 = M^2 lambda f/(pi win). Une conception optique rigoureuse doit aussi inclure tolerance de focale, ouverture utile, aberrations, traitements, distance de travail et plage de reglage mecanique.\n\n"
            "4. Le nombre V d'une fibre a saut d'indice est V = 2 pi a NA/lambda. La condition monomode est V < 2.405. "
            "L'approximation de Marcuse est surtout valable pour 1.5 < V < 2.4.\n\n"
            "5. La longueur d'onde par defaut est 780.24 nm, adaptee aux experiences proches de la raie D2 du rubidium. Les unites d'entree sont indiquees dans l'interface."
        ),
    },
    "zh": {
        "window_title": "单模光纤耦合效率计算器",
        "title": "单模光纤耦合效率计算器",
        "language": "语言",
        "fiber_section": "光纤参数",
        "beam_section": "入射到光纤端面的高斯光束",
        "lens_section": "透镜与设计参数",
        "results_section": "计算结果",
        "notes_section": "模型与学术注释",
        "calculate": "计算",
        "reset": "恢复默认值",
        "wavelength": "波长 lambda",
        "mfd": "模场直径 MFD",
        "fiber_na": "数值孔径 NA",
        "core_radius": "纤芯半径 a",
        "core_index": "纤芯折射率 n",
        "beam_radius": "光束半径 w",
        "z_distance": "束腰到端面距离 z",
        "offset": "端面横向偏移 d",
        "tilt": "角度失配 theta",
        "focal_length": "透镜焦距 f",
        "input_radius": "透镜前准直光束半径 win",
        "m2": "光束质量因子 M^2",
        "target_waist": "目标端面束腰半径",
        "total_eta": "总耦合效率 eta",
        "mode_factor": "模式/曲率重叠因子",
        "offset_factor": "横向偏移因子",
        "tilt_factor": "角度失配因子",
        "fiber_mode_radius": "光纤模场半径 wf",
        "beam_radius_facet": "端面光束半径 w(z)",
        "rayleigh_length": "输入束腰瑞利长度 zR",
        "wavefront_radius": "端面波前曲率 R",
        "focused_waist": "由当前透镜估计的焦斑半径 w0",
        "suggest_f": "若目标束腰为 {target}，建议焦距 f",
        "suggest_win": "若焦距固定为 {focal}，建议入射光束半径 win",
        "v_number": "阶跃光纤 V 数",
        "marcuse_radius": "Marcuse 估计模场半径",
        "acceptance_angle": "光纤介质内近似接收半角",
        "warning_header": "注意:",
        "infinity": "infinity (束腰位于端面)",
        "warn_positive": "波长和模场直径必须为正数。",
        "warn_na": "NA 应为正数；否则无法评估接收角和 V 数。",
        "warn_multimode": "V >= 2.405，阶跃光纤可能不是严格单模；请核对纤芯半径、NA 和波长。",
        "warn_marcuse": "Marcuse 模场半径近似在该 V 数范围外精度有限。",
        "warn_mismatch": "透镜估计焦斑与光纤模场半径相差超过 20%，模式匹配可能较差。",
        "warn_tilt": "角度失配已接近光纤接收半角量级，实际耦合对准会较敏感。",
        "warn_model": "结果基于标量高斯近似；高 NA、非理想透镜、端面反射和偏振效应需另行修正。",
        "notes": (
            "1. 单模光纤基模近似为 LP01 高斯模式，用户输入的 MFD 对应 1/e^2 强度直径，"
            "程序使用 wf = MFD/2 作为模式半径。\n\n"
            "2. 端面重叠效率采用两个高斯场的归一化重叠积分。尺寸失配和曲率失配同时进入"
            "模式/曲率重叠因子；横向偏移和小角度倾斜作为独立高斯惩罚因子处理。\n\n"
            "3. 透镜估算使用准直入射高斯光束的薄透镜公式 w0 = M^2 lambda f/(pi win)。"
            "严格设计时应结合实际透镜焦距、有效孔径、像差、镀膜、工作距离和机械调节范围。\n\n"
            "4. 阶跃光纤 V 数使用 V = 2 pi a NA/lambda。V < 2.405 是阶跃光纤单模条件。"
            "Marcuse 模场半径近似主要适用于 1.5 < V < 2.4。\n\n"
            "5. 默认波长为 780.24 nm，适用于常见铷原子 D2 线附近实验。输入单位已在界面标注。"
        ),
    },
}


class FiberCouplingApp(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=14)
        self.master.geometry("1060x740")
        self.master.minsize(980, 680)

        self.language = "en"
        self.vars: dict[str, tk.StringVar] = {}
        self.i18n_widgets: list[tuple[tk.Widget, str]] = []
        self.notes_text: tk.Text | None = None
        self.output = tk.StringVar()
        self._configure_style()
        self._build_ui()
        self.set_language("en")
        self.calculate()

    def _configure_style(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#f7f7f4")
        style.configure("TLabelframe", background="#f7f7f4")
        style.configure("TLabelframe.Label", background="#f7f7f4", font=("TkDefaultFont", 10, "bold"))
        style.configure("TLabel", background="#f7f7f4")
        style.configure("Result.TLabel", background="#ffffff", font=("TkDefaultFont", 10), justify="left")
        style.configure("Title.TLabel", background="#f7f7f4", font=("TkDefaultFont", 16, "bold"))
        style.configure("Accent.TButton", font=("TkDefaultFont", 10, "bold"))

    def _var(self, name: str, value: str) -> tk.StringVar:
        var = tk.StringVar(value=value)
        self.vars[name] = var
        var.trace_add("write", lambda *_: self.calculate())
        return var

    def tr(self, key: str) -> str:
        return TRANSLATIONS[self.language][key]

    def _register_i18n(self, widget: tk.Widget, key: str) -> tk.Widget:
        self.i18n_widgets.append((widget, key))
        return widget

    def set_language(self, language: str) -> None:
        self.language = language
        self.master.title(self.tr("window_title"))
        for widget, key in self.i18n_widgets:
            widget.configure(text=self.tr(key))
        if self.notes_text is not None:
            self.notes_text.configure(state="normal")
            self.notes_text.delete("1.0", "end")
            self.notes_text.insert("1.0", self.tr("notes"))
            self.notes_text.configure(state="disabled")
        self.calculate()

    def _build_ui(self) -> None:
        self.grid(sticky="nsew")
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(2, weight=1)

        header = ttk.Frame(self)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        header.columnconfigure(0, weight=1)

        title = self._register_i18n(ttk.Label(
            header,
            style="Title.TLabel",
        ), "title")
        title.grid(row=0, column=0, sticky="w")

        language_bar = ttk.Frame(header)
        language_bar.grid(row=0, column=1, sticky="e")
        self._register_i18n(ttk.Label(language_bar), "language").pack(side="left", padx=(0, 6))
        ttk.Button(language_bar, text="English", command=lambda: self.set_language("en")).pack(side="left", padx=2)
        ttk.Button(language_bar, text="Français", command=lambda: self.set_language("fr")).pack(side="left", padx=2)
        ttk.Button(language_bar, text="中文", command=lambda: self.set_language("zh")).pack(side="left", padx=2)

        input_panel = ttk.Frame(self)
        input_panel.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        input_panel.columnconfigure(0, weight=1)

        right_panel = ttk.Frame(self)
        right_panel.grid(row=1, column=1, rowspan=2, sticky="nsew", padx=(8, 0))
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=1)

        self._fiber_section(input_panel).grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self._beam_section(input_panel).grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self._lens_section(input_panel).grid(row=2, column=0, sticky="ew", pady=(0, 8))

        button_row = ttk.Frame(input_panel)
        button_row.grid(row=3, column=0, sticky="ew")
        self._register_i18n(ttk.Button(button_row, style="Accent.TButton", command=self.calculate), "calculate").pack(side="left")
        self._register_i18n(ttk.Button(button_row, command=self.reset_defaults), "reset").pack(side="left", padx=8)

        result_box = self._register_i18n(ttk.LabelFrame(right_panel), "results_section")
        result_box.grid(row=0, column=0, sticky="ew")
        result_box.columnconfigure(0, weight=1)
        result = ttk.Label(result_box, textvariable=self.output, style="Result.TLabel", padding=12, anchor="nw")
        result.grid(row=0, column=0, sticky="ew")

        notes = self._register_i18n(ttk.LabelFrame(right_panel), "notes_section")
        notes.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        notes.columnconfigure(0, weight=1)
        notes.rowconfigure(0, weight=1)
        self.notes_text = tk.Text(notes, wrap="word", height=18, bg="#ffffff", relief="flat", padx=10, pady=10)
        self.notes_text.grid(row=0, column=0, sticky="nsew")
        self.notes_text.configure(state="disabled")

    def _add_entry(self, parent: ttk.Frame, row: int, label_key: str, name: str, value: str, unit: str) -> None:
        label = self._register_i18n(ttk.Label(parent), label_key)
        label.grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        entry = ttk.Entry(parent, textvariable=self._var(name, value), width=14)
        entry.grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Label(parent, text=unit).grid(row=row, column=2, sticky="w", padx=(8, 0), pady=4)

    def _fiber_section(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = self._register_i18n(ttk.LabelFrame(parent), "fiber_section")
        frame.columnconfigure(1, weight=1)
        self._add_entry(frame, 0, "wavelength", "wavelength_nm", "780.24", "nm")
        self._add_entry(frame, 1, "mfd", "mfd_um", "5.0", "um")
        self._add_entry(frame, 2, "fiber_na", "fiber_na", "0.12", "")
        self._add_entry(frame, 3, "core_radius", "core_radius_um", "2.25", "um")
        self._add_entry(frame, 4, "core_index", "core_index", "1.45", "")
        return frame

    def _beam_section(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = self._register_i18n(ttk.LabelFrame(parent), "beam_section")
        frame.columnconfigure(1, weight=1)
        self._add_entry(frame, 0, "beam_radius", "beam_radius_um", "2.5", "um")
        self._add_entry(frame, 1, "z_distance", "z_um", "0.0", "um")
        self._add_entry(frame, 2, "offset", "offset_um", "0.0", "um")
        self._add_entry(frame, 3, "tilt", "tilt_mrad", "0.0", "mrad")
        return frame

    def _lens_section(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = self._register_i18n(ttk.LabelFrame(parent), "lens_section")
        frame.columnconfigure(1, weight=1)
        self._add_entry(frame, 0, "focal_length", "focal_length_mm", "8.0", "mm")
        self._add_entry(frame, 1, "input_radius", "input_radius_mm", "0.8", "mm")
        self._add_entry(frame, 2, "m2", "m2", "1.0", "")
        self._add_entry(frame, 3, "target_waist", "target_waist_um", "2.5", "um")
        return frame

    def reset_defaults(self) -> None:
        defaults = {
            "wavelength_nm": "780.24",
            "mfd_um": "5.0",
            "fiber_na": "0.12",
            "core_radius_um": "2.25",
            "core_index": "1.45",
            "beam_radius_um": "2.5",
            "z_um": "0.0",
            "offset_um": "0.0",
            "tilt_mrad": "0.0",
            "focal_length_mm": "8.0",
            "input_radius_mm": "0.8",
            "m2": "1.0",
            "target_waist_um": "2.5",
        }
        for name, value in defaults.items():
            self.vars[name].set(value)

    def calculate(self) -> None:
        wavelength = safe_float(self.vars.get("wavelength_nm", tk.StringVar(value="780.24")).get()) * NM
        mfd = safe_float(self.vars.get("mfd_um", tk.StringVar(value="5.0")).get()) * UM
        fiber_mode_radius = 0.5 * mfd
        fiber_na = safe_float(self.vars.get("fiber_na", tk.StringVar(value="0.12")).get())
        core_radius = safe_float(self.vars.get("core_radius_um", tk.StringVar(value="2.25")).get()) * UM
        core_index = safe_float(self.vars.get("core_index", tk.StringVar(value="1.45")).get(), 1.45)

        waist = safe_float(self.vars.get("beam_radius_um", tk.StringVar(value="2.5")).get()) * UM
        z = safe_float(self.vars.get("z_um", tk.StringVar(value="0.0")).get()) * UM
        offset = safe_float(self.vars.get("offset_um", tk.StringVar(value="0.0")).get()) * UM
        tilt = safe_float(self.vars.get("tilt_mrad", tk.StringVar(value="0.0")).get()) * 1e-3

        focal_length = safe_float(self.vars.get("focal_length_mm", tk.StringVar(value="8.0")).get()) * MM
        input_radius = safe_float(self.vars.get("input_radius_mm", tk.StringVar(value="0.8")).get()) * MM
        m2 = safe_float(self.vars.get("m2", tk.StringVar(value="1.0")).get(), 1.0)
        target_waist = safe_float(self.vars.get("target_waist_um", tk.StringVar(value="2.5")).get()) * UM

        beam_radius_at_fiber = gaussian_radius_at_z(waist, wavelength, z) if waist > 0 and wavelength > 0 else 0.0
        beam_r = gaussian_wavefront_radius(waist, wavelength, z) if waist > 0 and wavelength > 0 else None
        eta, factors = gaussian_mode_overlap(
            wavelength,
            beam_radius_at_fiber,
            fiber_mode_radius,
            beam_r,
            None,
            offset,
            tilt,
        )

        z_r = rayleigh_range(waist, wavelength) if waist > 0 and wavelength > 0 else 0.0
        focused_waist = focused_waist_from_lens(wavelength, input_radius, focal_length, m2)
        ideal_f = required_focal_length(target_waist, wavelength, input_radius, m2)
        ideal_win = required_input_radius(target_waist, wavelength, focal_length, m2)
        estimated_mode_radius, v_number = mode_field_radius_from_v_number(core_radius, fiber_na, wavelength)
        acceptance_angle = math.asin(clamp(fiber_na / max(core_index, 1e-12), -1.0, 1.0))

        target_text = f"{target_waist / UM:.4g} um"
        focal_text = f"{focal_length / MM:.4g} mm"
        lines = [
            f"{self.tr('total_eta')} = {100.0 * eta:.3f} %",
            f"{self.tr('mode_factor')} = {100.0 * factors['mode']:.3f} %",
            f"{self.tr('offset_factor')} = {100.0 * factors['offset']:.3f} %",
            f"{self.tr('tilt_factor')} = {100.0 * factors['tilt']:.3f} %",
            "",
            f"{self.tr('fiber_mode_radius')} = {fiber_mode_radius / UM:.4g} um",
            f"{self.tr('beam_radius_facet')} = {beam_radius_at_fiber / UM:.4g} um",
            f"{self.tr('rayleigh_length')} = {z_r / UM:.4g} um",
            f"{self.tr('wavefront_radius')} = {self._format_radius(beam_r)}",
            "",
            f"{self.tr('focused_waist')} = {focused_waist / UM:.4g} um",
            f"{self.tr('suggest_f').format(target=target_text)} = {ideal_f / MM:.4g} mm",
            f"{self.tr('suggest_win').format(focal=focal_text)} = {ideal_win / MM:.4g} mm",
            "",
            f"{self.tr('v_number')} = {v_number:.4g}",
            f"{self.tr('marcuse_radius')} = {estimated_mode_radius / UM:.4g} um",
            f"{self.tr('acceptance_angle')} = {acceptance_angle / DEG:.4g} deg",
        ]

        warnings = self._warnings(wavelength, fiber_mode_radius, fiber_na, v_number, focused_waist, acceptance_angle, tilt)
        if warnings:
            lines.extend(["", self.tr("warning_header")])
            lines.extend(f"- {item}" for item in warnings)
        self.output.set("\n".join(lines))

    def _warnings(
        self,
        wavelength: float,
        fiber_mode_radius: float,
        fiber_na: float,
        v_number: float,
        focused_waist: float,
        acceptance_angle: float,
        tilt: float,
    ) -> list[str]:
        warnings: list[str] = []
        if wavelength <= 0 or fiber_mode_radius <= 0:
            warnings.append(self.tr("warn_positive"))
        if fiber_na <= 0:
            warnings.append(self.tr("warn_na"))
        if v_number >= 2.405:
            warnings.append(self.tr("warn_multimode"))
        if 0 < v_number < 1.5:
            warnings.append(self.tr("warn_marcuse"))
        if focused_waist > 0 and fiber_mode_radius > 0:
            mismatch = abs(focused_waist / fiber_mode_radius - 1.0)
            if mismatch > 0.2:
                warnings.append(self.tr("warn_mismatch"))
        if acceptance_angle > 0 and abs(tilt) > 0.5 * acceptance_angle:
            warnings.append(self.tr("warn_tilt"))
        warnings.append(self.tr("warn_model"))
        return warnings

    def _format_radius(self, radius_m: float | None) -> str:
        if radius_m is None:
            return self.tr("infinity")
        if abs(radius_m) >= 1e-3:
            return f"{radius_m / MM:.4g} mm"
        return f"{radius_m / UM:.4g} um"


def main() -> None:
    root = tk.Tk()
    FiberCouplingApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
