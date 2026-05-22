from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


PI = math.pi
DEFAULT_VZ_M_S = 3.34778
DEFAULT_ALPHA_DEG = 4.9678
DEFAULT_LASER_WAVELENGTH_M = 780e-9
DEFAULT_RECOIL_FREQUENCY_KHZ = 15.093

TRANSITION_F1_TO_F2 = "F1→F2"
TRANSITION_F2_TO_F1 = "F2→F1"
FLYING_UP = "flying up"
FALLING_DOWN = "falling down"


@dataclass(slots=True)
class DetuningConstants:
    vz_m_s: float = DEFAULT_VZ_M_S
    alpha_deg: float = DEFAULT_ALPHA_DEG
    laser_wavelength_m: float = DEFAULT_LASER_WAVELENGTH_M
    recoil_frequency_khz: float = DEFAULT_RECOIL_FREQUENCY_KHZ

    @property
    def alpha_rad(self) -> float:
        return math.radians(self.alpha_deg)

    @property
    def k(self) -> float:
        return 2.0 * PI / self.laser_wavelength_m

    @property
    def keff(self) -> float:
        return 2.0 * self.k

    @property
    def recoil_frequency_rad_s(self) -> float:
        return 2.0 * PI * self.recoil_frequency_khz * 1e3

    def validate(self) -> None:
        if self.vz_m_s <= 0.0:
            raise ValueError("vz must be positive.")
        if self.laser_wavelength_m <= 0.0:
            raise ValueError("Laser wavelength must be positive.")
        if self.recoil_frequency_khz < 0.0:
            raise ValueError("Recoil frequency must be non-negative.")
        if abs(math.cos(self.alpha_rad)) < 1e-12:
            raise ValueError("alpha is too close to 90 degrees for stable transverse-velocity calculations.")


@dataclass(slots=True)
class VelocityInversionResult:
    vx_mm_s: float
    used_case: str


@dataclass(slots=True)
class CalibrationResult:
    alpha_deg: float
    vx_mm_s: float
    flying_up_case: str
    falling_down_case: str


def transition_sign(trans_case: str) -> int:
    if trans_case == TRANSITION_F1_TO_F2:
        return 1
    if trans_case == TRANSITION_F2_TO_F1:
        return -1
    raise ValueError("Transition type must be F1→F2 or F2→F1.")


def detuning_case_label(up_or_down: str, detuning_khz: float) -> str:
    sign_label = "Δ>0" if detuning_khz >= 0.0 else "Δ<0"
    if up_or_down not in {FLYING_UP, FALLING_DOWN}:
        raise ValueError("Mode must be 'flying up' or 'falling down'.")
    return f"{up_or_down}, {sign_label}"


def compute_detuning_khz(
    vx_mm_s: float,
    trans_case: str,
    constants: DetuningConstants | None = None,
) -> dict[str, float]:
    constants = constants or DetuningConstants()
    constants.validate()

    vx_m_s = vx_mm_s / 1000.0
    wr_sign = transition_sign(trans_case)
    term1 = constants.keff * constants.vz_m_s * math.sin(constants.alpha_rad)
    term2 = constants.keff * vx_m_s * math.cos(constants.alpha_rad)
    recoil_term = wr_sign * constants.recoil_frequency_rad_s

    def to_khz(omega_rad_s: float) -> float:
        return omega_rad_s / (2.0 * PI * 1e3)

    return {
        f"{FLYING_UP}, Δ>0": to_khz(term1 + term2 + recoil_term),
        f"{FLYING_UP}, Δ<0": to_khz(-term1 - term2 + recoil_term),
        f"{FALLING_DOWN}, Δ>0": to_khz(term1 - term2 + recoil_term),
        f"{FALLING_DOWN}, Δ<0": to_khz(-term1 + term2 + recoil_term),
    }


def compute_vx_from_detuning_auto(
    detuning_khz: float,
    up_or_down: str,
    trans_case: str,
    constants: DetuningConstants | None = None,
) -> VelocityInversionResult:
    constants = constants or DetuningConstants()
    constants.validate()

    detuning_rad_s = detuning_khz * 2.0 * PI * 1e3
    term1 = constants.keff * constants.vz_m_s * math.sin(constants.alpha_rad)
    coefficient = constants.keff * math.cos(constants.alpha_rad)
    wr_sign = transition_sign(trans_case)
    recoil_term = wr_sign * constants.recoil_frequency_rad_s

    if up_or_down == FLYING_UP:
        if detuning_khz >= 0.0:
            vx_m_s = (detuning_rad_s - term1 - recoil_term) / coefficient
            used_case = f"{FLYING_UP}, Δ>0"
        else:
            vx_m_s = -(detuning_rad_s - recoil_term + term1) / coefficient
            used_case = f"{FLYING_UP}, Δ<0"
    elif up_or_down == FALLING_DOWN:
        if detuning_khz >= 0.0:
            vx_m_s = -(detuning_rad_s - term1 - recoil_term) / coefficient
            used_case = f"{FALLING_DOWN}, Δ>0"
        else:
            vx_m_s = (detuning_rad_s - recoil_term + term1) / coefficient
            used_case = f"{FALLING_DOWN}, Δ<0"
    else:
        raise ValueError("Mode must be 'flying up' or 'falling down'.")

    return VelocityInversionResult(vx_mm_s=vx_m_s * 1e3, used_case=used_case)


def calibrate_alpha_and_vx_from_scans(
    flying_up_detuning_khz: float,
    falling_down_detuning_khz: float,
    trans_case: str,
    constants: DetuningConstants | None = None,
) -> CalibrationResult:
    constants = constants or DetuningConstants()
    constants.validate()

    wr_sign = transition_sign(trans_case)
    recoil_term = wr_sign * constants.recoil_frequency_rad_s

    flying_up_sign = 1.0 if flying_up_detuning_khz >= 0.0 else -1.0
    falling_down_sign = 1.0 if falling_down_detuning_khz >= 0.0 else -1.0

    flying_up_rad_s = flying_up_detuning_khz * 2.0 * PI * 1e3
    falling_down_rad_s = falling_down_detuning_khz * 2.0 * PI * 1e3

    up_sum = (flying_up_rad_s - recoil_term) / flying_up_sign
    down_difference = (falling_down_rad_s - recoil_term) / falling_down_sign

    term1 = 0.5 * (up_sum + down_difference)
    term2 = 0.5 * (up_sum - down_difference)

    sine_alpha = term1 / (constants.keff * constants.vz_m_s)
    if not np.isfinite(sine_alpha) or abs(sine_alpha) > 1.0 + 1e-9:
        raise ValueError(
            "The provided scan results are inconsistent with the model; they imply an invalid sin(alpha)."
        )
    sine_alpha = float(np.clip(sine_alpha, -1.0, 1.0))

    alpha_rad = math.asin(sine_alpha)
    cosine_alpha = math.cos(alpha_rad)
    if abs(cosine_alpha) < 1e-12:
        raise ValueError("The calibrated alpha is too close to 90 degrees for stable vx recovery.")

    vx_m_s = term2 / (constants.keff * cosine_alpha)
    return CalibrationResult(
        alpha_deg=math.degrees(alpha_rad),
        vx_mm_s=vx_m_s * 1e3,
        flying_up_case=detuning_case_label(FLYING_UP, flying_up_detuning_khz),
        falling_down_case=detuning_case_label(FALLING_DOWN, falling_down_detuning_khz),
    )
