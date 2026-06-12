#!/usr/bin/env python3
from __future__ import annotations

import ast
import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

TWO_PI = 2.0 * math.pi
DEFAULT_FORMULA = (
    "offset + 0.5*peak_to_peak*cos(2*pi*t2_ms2/period_t2_ms2 + phase_rad + phase_scan_rad)"
)

_FORMULA_FUNCTIONS = {
    "abs": np.abs,
    "arccos": np.arccos,
    "arcsin": np.arcsin,
    "arctan": np.arctan,
    "ceil": np.ceil,
    "clip": np.clip,
    "cos": np.cos,
    "cosh": np.cosh,
    "exp": np.exp,
    "floor": np.floor,
    "log": np.log,
    "log10": np.log10,
    "maximum": np.maximum,
    "minimum": np.minimum,
    "sin": np.sin,
    "sinh": np.sinh,
    "sqrt": np.sqrt,
    "tan": np.tan,
    "tanh": np.tanh,
    "where": np.where,
}
_FORMULA_CONSTANTS = {
    "e": math.e,
    "pi": math.pi,
}
_FORMULA_VARIABLES = {
    "offset",
    "peak_to_peak",
    "period_t2_ms2",
    "phase_rad",
    "phase_scan_rad",
    "t2_ms2",
    "t_ms",
}
_ALLOWED_FORMULA_NAMES = set(_FORMULA_FUNCTIONS) | set(_FORMULA_CONSTANTS) | _FORMULA_VARIABLES
_ALLOWED_FORMULA_NODES = (
    ast.Add,
    ast.And,
    ast.BinOp,
    ast.BoolOp,
    ast.Call,
    ast.Compare,
    ast.Constant,
    ast.Div,
    ast.Eq,
    ast.Expression,
    ast.Gt,
    ast.GtE,
    ast.IfExp,
    ast.Load,
    ast.Lt,
    ast.LtE,
    ast.Mod,
    ast.Mult,
    ast.Name,
    ast.NotEq,
    ast.Or,
    ast.Pow,
    ast.Sub,
    ast.UAdd,
    ast.UnaryOp,
    ast.USub,
)


@dataclass(frozen=True)
class ScanSettings:
    t_min_ms: float = 0.0
    t_max_ms: float = 12.0
    n_points: int = 600
    clip_to_probability: bool = False


@dataclass(frozen=True)
class PhaseScanSettings:
    fixed_t_ms: float = 4.0
    phase_min_rad: float = 0.0
    phase_max_rad: float = TWO_PI
    n_points: int = 600


@dataclass(frozen=True)
class FringeParameters:
    label: str
    period_t2_ms2: float
    phase_rad: float
    offset: float
    peak_to_peak: float
    color: str
    model_type: str = "cosine"
    formula: str = DEFAULT_FORMULA


@dataclass(frozen=True)
class SimulationResult:
    scan: ScanSettings
    upper: FringeParameters
    lower: FringeParameters
    t_ms: np.ndarray
    t2_ms2: np.ndarray
    upper_probability: np.ndarray
    lower_probability: np.ndarray


@dataclass(frozen=True)
class PhaseScanResult:
    settings: PhaseScanSettings
    fixed_t2_ms2: float
    phase_rad: np.ndarray
    upper_probability: np.ndarray
    lower_probability: np.ndarray


@dataclass(frozen=True)
class SavedConfiguration:
    scan: ScanSettings
    upper: FringeParameters
    lower: FringeParameters
    lissajous_mode: str = "t_scan"
    phase_scan: PhaseScanSettings | None = None


def default_configuration() -> tuple[ScanSettings, FringeParameters, FringeParameters]:
    scan = ScanSettings(
        t_min_ms=0.0,
        t_max_ms=12.0,
        n_points=600,
        clip_to_probability=False,
    )
    upper = FringeParameters(
        label="MIGA21",
        period_t2_ms2=20.0,
        phase_rad=0.0,
        offset=0.50,
        peak_to_peak=0.90,
        color="#0f6c5c",
    )
    lower = FringeParameters(
        label="MIGA22",
        period_t2_ms2=20.0,
        phase_rad=0.75,
        offset=0.48,
        peak_to_peak=0.82,
        color="#c45b12",
    )
    return scan, upper, lower


def default_phase_scan_settings() -> PhaseScanSettings:
    return PhaseScanSettings(
        fixed_t_ms=4.0,
        phase_min_rad=0.0,
        phase_max_rad=TWO_PI,
        n_points=600,
    )


def _read_mapping(value: object, field_name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"Configuration JSON field {field_name!r} must be an object.")
    return value


def _read_float_value(
    payload: dict[str, object],
    key: str,
    default: float,
    *,
    field_name: str,
) -> float:
    raw_value = payload.get(key, default)
    try:
        return float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name}.{key} must be a number.") from exc


def _read_int_value(
    payload: dict[str, object],
    key: str,
    default: int,
    *,
    field_name: str,
) -> int:
    raw_value = payload.get(key, default)
    try:
        return int(float(raw_value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name}.{key} must be an integer.") from exc


def _read_bool_value(
    payload: dict[str, object],
    key: str,
    default: bool,
    *,
    field_name: str,
) -> bool:
    raw_value = payload.get(key, default)
    if isinstance(raw_value, bool):
        return raw_value
    if isinstance(raw_value, (int, float)):
        return bool(raw_value)
    if isinstance(raw_value, str):
        lowered = raw_value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    raise ValueError(f"{field_name}.{key} must be a boolean.")


def _read_text_value(
    payload: dict[str, object],
    key: str,
    default: str,
) -> str:
    raw_value = payload.get(key, default)
    if raw_value is None:
        return default
    return str(raw_value)


def _validate_scan(scan: ScanSettings) -> None:
    if scan.t_min_ms < 0.0:
        raise ValueError("T min must be non-negative because the scan variable is T >= 0.")
    if scan.t_max_ms <= scan.t_min_ms:
        raise ValueError("T max must be larger than T min.")
    if scan.n_points < 10:
        raise ValueError("Use at least 10 scan points for a meaningful fringe trace.")


def _validate_phase_scan(settings: PhaseScanSettings) -> None:
    if settings.fixed_t_ms < 0.0:
        raise ValueError("Fixed T must be non-negative.")
    if settings.phase_max_rad <= settings.phase_min_rad:
        raise ValueError("Phase max must be larger than phase min.")
    if settings.n_points < 10:
        raise ValueError("Use at least 10 phase samples for a meaningful Lissajous curve.")


def _validate_fringe(fringe: FringeParameters) -> None:
    if fringe.model_type not in {"cosine", "formula"}:
        raise ValueError(f"{fringe.label}: unsupported model type {fringe.model_type!r}.")
    if fringe.model_type == "cosine":
        if fringe.period_t2_ms2 <= 0.0:
            raise ValueError(f"{fringe.label}: period in T^2 must be positive.")
        if fringe.peak_to_peak < 0.0:
            raise ValueError(f"{fringe.label}: peak-to-peak must be non-negative.")
    if fringe.model_type == "formula" and not fringe.formula.strip():
        raise ValueError(f"{fringe.label}: formula mode requires a non-empty expression.")


def _compile_formula(formula: str, label: str) -> object:
    try:
        tree = ast.parse(formula, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"{label}: invalid formula syntax ({exc.msg}).") from exc

    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_FORMULA_NODES):
            raise ValueError(
                f"{label}: unsupported syntax in formula ({type(node).__name__})."
            )
        if isinstance(node, ast.Name) and node.id not in _ALLOWED_FORMULA_NAMES:
            raise ValueError(f"{label}: unknown symbol {node.id!r} in formula.")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _FORMULA_FUNCTIONS:
                raise ValueError(
                    f"{label}: only these functions are allowed: {', '.join(sorted(_FORMULA_FUNCTIONS))}."
                )

    return compile(tree, filename=f"<{label} formula>", mode="eval")


def _coerce_formula_output(
    value: object,
    *,
    t2_ms2: np.ndarray,
    phase_scan_rad: np.ndarray,
    label: str,
) -> np.ndarray:
    reference, _ = np.broadcast_arrays(t2_ms2, phase_scan_rad)
    probability = np.asarray(value, dtype=float)

    if probability.shape == ():
        probability = np.full(reference.shape, float(probability), dtype=float)
    else:
        try:
            probability = np.broadcast_to(probability, reference.shape)
        except ValueError as exc:
            raise ValueError(
                f"{label}: formula must return a scalar or an array compatible with the scan shape."
            ) from exc

    probability = np.asarray(probability, dtype=float)
    if not np.all(np.isfinite(probability)):
        raise ValueError(f"{label}: formula evaluation produced non-finite values.")
    return probability


def _simulate_formula_fringe(
    t2_ms2: np.ndarray,
    phase_scan_rad: np.ndarray,
    fringe: FringeParameters,
) -> np.ndarray:
    compiled = _compile_formula(fringe.formula, fringe.label)
    local_names = {
        **_FORMULA_FUNCTIONS,
        **_FORMULA_CONSTANTS,
        "offset": fringe.offset,
        "peak_to_peak": fringe.peak_to_peak,
        "period_t2_ms2": fringe.period_t2_ms2,
        "phase_rad": fringe.phase_rad,
        "phase_scan_rad": phase_scan_rad,
        "t2_ms2": t2_ms2,
        "t_ms": np.sqrt(np.clip(t2_ms2, 0.0, None)),
    }
    try:
        raw_probability = eval(compiled, {"__builtins__": {}}, local_names)
    except Exception as exc:
        raise ValueError(f"{fringe.label}: formula evaluation failed ({exc}).") from exc
    return _coerce_formula_output(
        raw_probability,
        t2_ms2=t2_ms2,
        phase_scan_rad=phase_scan_rad,
        label=fringe.label,
    )


def simulate_single_fringe(
    t2_ms2: np.ndarray,
    fringe: FringeParameters,
    *,
    clip_to_probability: bool,
    phase_scan_rad: float | np.ndarray = 0.0,
) -> np.ndarray:
    t2_array = np.asarray(t2_ms2, dtype=float)
    phase_scan_array = np.asarray(phase_scan_rad, dtype=float)
    t2_array, phase_scan_array = np.broadcast_arrays(t2_array, phase_scan_array)

    if fringe.model_type == "formula":
        probability = _simulate_formula_fringe(t2_array, phase_scan_array, fringe)
    else:
        phase = TWO_PI * t2_array / fringe.period_t2_ms2 + fringe.phase_rad + phase_scan_array
        probability = fringe.offset + 0.5 * fringe.peak_to_peak * np.cos(phase)

    if clip_to_probability:
        probability = np.clip(probability, 0.0, 1.0)
    return np.asarray(probability, dtype=float)


def simulate_dual_ai(
    scan: ScanSettings,
    upper: FringeParameters,
    lower: FringeParameters,
) -> SimulationResult:
    _validate_scan(scan)
    _validate_fringe(upper)
    _validate_fringe(lower)

    t_ms = np.linspace(scan.t_min_ms, scan.t_max_ms, scan.n_points)
    t2_ms2 = np.square(t_ms)
    upper_probability = simulate_single_fringe(
        t2_ms2,
        upper,
        clip_to_probability=scan.clip_to_probability,
    )
    lower_probability = simulate_single_fringe(
        t2_ms2,
        lower,
        clip_to_probability=scan.clip_to_probability,
    )

    return SimulationResult(
        scan=scan,
        upper=upper,
        lower=lower,
        t_ms=t_ms,
        t2_ms2=t2_ms2,
        upper_probability=upper_probability,
        lower_probability=lower_probability,
    )


def simulate_phase_scan_lissajous(
    settings: PhaseScanSettings,
    upper: FringeParameters,
    lower: FringeParameters,
    *,
    clip_to_probability: bool,
) -> PhaseScanResult:
    _validate_phase_scan(settings)
    _validate_fringe(upper)
    _validate_fringe(lower)

    phase_rad = np.linspace(settings.phase_min_rad, settings.phase_max_rad, settings.n_points)
    fixed_t2_ms2 = settings.fixed_t_ms * settings.fixed_t_ms
    fixed_t2_trace = np.full_like(phase_rad, fixed_t2_ms2, dtype=float)

    upper_probability = simulate_single_fringe(
        fixed_t2_trace,
        upper,
        clip_to_probability=clip_to_probability,
        phase_scan_rad=phase_rad,
    )
    lower_probability = simulate_single_fringe(
        fixed_t2_trace,
        lower,
        clip_to_probability=clip_to_probability,
        phase_scan_rad=phase_rad,
    )

    return PhaseScanResult(
        settings=settings,
        fixed_t2_ms2=fixed_t2_ms2,
        phase_rad=phase_rad,
        upper_probability=upper_probability,
        lower_probability=lower_probability,
    )


def wrap_phase_rad(phase_rad: float) -> float:
    return math.atan2(math.sin(phase_rad), math.cos(phase_rad))


def _format_probability_range(values: np.ndarray) -> str:
    return f"[{float(np.min(values)):.3f}, {float(np.max(values)):.3f}]"


def _shorten_formula(formula: str, max_chars: int = 58) -> str:
    compact = " ".join(formula.split())
    if len(compact) <= max_chars:
        return compact
    return f"{compact[: max_chars - 3]}..."


def _build_fringe_summary_line(
    fringe: FringeParameters,
    probabilities: np.ndarray,
    *,
    t2_span: float,
) -> str:
    probability_range = _format_probability_range(probabilities)
    if fringe.model_type == "cosine":
        cycles = t2_span / fringe.period_t2_ms2
        return (
            f"{fringe.label}: cosine model, {cycles:.2f} cycles across the scan, "
            f"P in {probability_range}"
        )
    return (
        f"{fringe.label}: formula model, P in {probability_range}, "
        f"expr = {_shorten_formula(fringe.formula)}"
    )


def build_summary_lines(result: SimulationResult) -> list[str]:
    t2_span = float(result.t2_ms2[-1] - result.t2_ms2[0])
    phase_diff = wrap_phase_rad(result.lower.phase_rad - result.upper.phase_rad)
    phase_diff_deg = math.degrees(phase_diff)

    lines = [
        (
            f"T scan: {result.scan.t_min_ms:.3f} to {result.scan.t_max_ms:.3f} ms "
            f"({result.scan.n_points} points)"
        ),
        (
            f"T^2 span: {result.t2_ms2[0]:.3f} to {result.t2_ms2[-1]:.3f} ms^2 "
            f"(window {t2_span:.3f} ms^2)"
        ),
        _build_fringe_summary_line(result.upper, result.upper_probability, t2_span=t2_span),
        _build_fringe_summary_line(result.lower, result.lower_probability, t2_span=t2_span),
        f"Configured phase parameter difference: {phase_diff:.3f} rad ({phase_diff_deg:.2f} deg)",
    ]

    if not result.scan.clip_to_probability:
        raw_min = min(float(np.min(result.upper_probability)), float(np.min(result.lower_probability)))
        raw_max = max(float(np.max(result.upper_probability)), float(np.max(result.lower_probability)))
        if raw_min < 0.0 or raw_max > 1.0:
            lines.append("Note: unclipped probabilities extend outside [0, 1].")
    else:
        lines.append("Probability clipping is enabled.")

    return lines


def build_phase_scan_summary_lines(result: PhaseScanResult) -> list[str]:
    lines = [
        (
            f"Phase-scan Lissajous: fixed T = {result.settings.fixed_t_ms:.3f} ms "
            f"(T^2 = {result.fixed_t2_ms2:.3f} ms^2)"
        ),
        (
            f"Phase range: {result.phase_rad[0]:.3f} to {result.phase_rad[-1]:.3f} rad "
            f"({result.settings.n_points} points)"
        ),
        f"MIGA21 during phase scan: P in {_format_probability_range(result.upper_probability)}",
        f"MIGA22 during phase scan: P in {_format_probability_range(result.lower_probability)}",
    ]
    return lines


def export_rows(result: SimulationResult) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for t_ms, t2_ms2, upper_p, lower_p in zip(
        result.t_ms,
        result.t2_ms2,
        result.upper_probability,
        result.lower_probability,
        strict=True,
    ):
        rows.append(
            {
                "T_ms": float(t_ms),
                "T2_ms2": float(t2_ms2),
                "upper_probability": float(upper_p),
                "lower_probability": float(lower_p),
            }
        )
    return rows


def export_phase_scan_rows(result: PhaseScanResult) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for phase_rad, upper_p, lower_p in zip(
        result.phase_rad,
        result.upper_probability,
        result.lower_probability,
        strict=True,
    ):
        rows.append(
            {
                "fixed_T_ms": float(result.settings.fixed_t_ms),
                "fixed_T2_ms2": float(result.fixed_t2_ms2),
                "phase_rad": float(phase_rad),
                "upper_probability": float(upper_p),
                "lower_probability": float(lower_p),
            }
        )
    return rows


def save_csv(result: SimulationResult, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["T_ms", "T2_ms2", "upper_probability", "lower_probability"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(export_rows(result))
    return path


def save_phase_scan_csv(result: PhaseScanResult, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "fixed_T_ms",
        "fixed_T2_ms2",
        "phase_rad",
        "upper_probability",
        "lower_probability",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(export_phase_scan_rows(result))
    return path


def save_configuration_json(
    result: SimulationResult,
    output_path: str | Path,
    *,
    phase_scan_result: PhaseScanResult | None = None,
    lissajous_mode: str = "t_scan",
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "scan": asdict(result.scan),
        "upper": asdict(result.upper),
        "lower": asdict(result.lower),
        "summary": build_summary_lines(result),
        "lissajous_mode": lissajous_mode,
    }
    if phase_scan_result is not None:
        payload["phase_scan"] = {
            **asdict(phase_scan_result.settings),
            "fixed_t2_ms2": phase_scan_result.fixed_t2_ms2,
        }
        payload["phase_scan_summary"] = build_phase_scan_summary_lines(phase_scan_result)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_configuration_json(input_path: str | Path) -> SavedConfiguration:
    path = Path(input_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid configuration JSON ({exc.msg}).") from exc

    if not isinstance(payload, dict):
        raise ValueError("Configuration JSON must contain an object at the top level.")

    default_scan, default_upper, default_lower = default_configuration()
    default_phase_scan = default_phase_scan_settings()

    scan_payload = _read_mapping(payload.get("scan"), "scan")
    upper_payload = _read_mapping(payload.get("upper"), "upper")
    lower_payload = _read_mapping(payload.get("lower"), "lower")

    phase_payload: dict[str, object] | None = None
    if payload.get("phase_scan") is not None:
        phase_payload = _read_mapping(payload.get("phase_scan"), "phase_scan")

    lissajous_mode = payload.get("lissajous_mode")
    if lissajous_mode is None:
        lissajous_mode = "phase_scan" if phase_payload is not None else "t_scan"
    else:
        lissajous_mode = str(lissajous_mode)
    if lissajous_mode not in {"t_scan", "phase_scan"}:
        raise ValueError("lissajous_mode must be 't_scan' or 'phase_scan'.")

    upper_model_type = _read_text_value(upper_payload, "model_type", default_upper.model_type)
    lower_model_type = _read_text_value(lower_payload, "model_type", default_lower.model_type)
    if upper_model_type not in {"cosine", "formula"}:
        raise ValueError("upper.model_type must be 'cosine' or 'formula'.")
    if lower_model_type not in {"cosine", "formula"}:
        raise ValueError("lower.model_type must be 'cosine' or 'formula'.")

    scan = ScanSettings(
        t_min_ms=_read_float_value(scan_payload, "t_min_ms", default_scan.t_min_ms, field_name="scan"),
        t_max_ms=_read_float_value(scan_payload, "t_max_ms", default_scan.t_max_ms, field_name="scan"),
        n_points=_read_int_value(scan_payload, "n_points", default_scan.n_points, field_name="scan"),
        clip_to_probability=_read_bool_value(
            scan_payload,
            "clip_to_probability",
            default_scan.clip_to_probability,
            field_name="scan",
        ),
    )
    upper = FringeParameters(
        label=_read_text_value(upper_payload, "label", default_upper.label),
        period_t2_ms2=_read_float_value(
            upper_payload,
            "period_t2_ms2",
            default_upper.period_t2_ms2,
            field_name="upper",
        ),
        phase_rad=_read_float_value(upper_payload, "phase_rad", default_upper.phase_rad, field_name="upper"),
        offset=_read_float_value(upper_payload, "offset", default_upper.offset, field_name="upper"),
        peak_to_peak=_read_float_value(
            upper_payload,
            "peak_to_peak",
            default_upper.peak_to_peak,
            field_name="upper",
        ),
        color=_read_text_value(upper_payload, "color", default_upper.color),
        model_type=upper_model_type,
        formula=_read_text_value(upper_payload, "formula", default_upper.formula),
    )
    lower = FringeParameters(
        label=_read_text_value(lower_payload, "label", default_lower.label),
        period_t2_ms2=_read_float_value(
            lower_payload,
            "period_t2_ms2",
            default_lower.period_t2_ms2,
            field_name="lower",
        ),
        phase_rad=_read_float_value(lower_payload, "phase_rad", default_lower.phase_rad, field_name="lower"),
        offset=_read_float_value(lower_payload, "offset", default_lower.offset, field_name="lower"),
        peak_to_peak=_read_float_value(
            lower_payload,
            "peak_to_peak",
            default_lower.peak_to_peak,
            field_name="lower",
        ),
        color=_read_text_value(lower_payload, "color", default_lower.color),
        model_type=lower_model_type,
        formula=_read_text_value(lower_payload, "formula", default_lower.formula),
    )

    phase_scan = None
    if lissajous_mode == "phase_scan" or phase_payload is not None:
        phase_source = phase_payload or {}
        phase_scan = PhaseScanSettings(
            fixed_t_ms=_read_float_value(
                phase_source,
                "fixed_t_ms",
                default_phase_scan.fixed_t_ms,
                field_name="phase_scan",
            ),
            phase_min_rad=_read_float_value(
                phase_source,
                "phase_min_rad",
                default_phase_scan.phase_min_rad,
                field_name="phase_scan",
            ),
            phase_max_rad=_read_float_value(
                phase_source,
                "phase_max_rad",
                default_phase_scan.phase_max_rad,
                field_name="phase_scan",
            ),
            n_points=_read_int_value(
                phase_source,
                "n_points",
                default_phase_scan.n_points,
                field_name="phase_scan",
            ),
        )

    return SavedConfiguration(
        scan=scan,
        upper=upper,
        lower=lower,
        lissajous_mode=lissajous_mode,
        phase_scan=phase_scan,
    )


def _print_default_summary() -> None:
    scan, upper, lower = default_configuration()
    result = simulate_dual_ai(scan, upper, lower)
    for line in build_summary_lines(result):
        print(line)


if __name__ == "__main__":
    _print_default_summary()
