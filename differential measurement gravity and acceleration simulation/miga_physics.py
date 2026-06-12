from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import numpy as np

G_SI = 6.67430e-11


@dataclass(frozen=True)
class SourceMass:
    mass_kg: float
    x_m: float
    y_m: float


@dataclass(frozen=True)
class FieldPoint:
    name: str
    x_m: float
    y_m: float


@dataclass(frozen=True)
class AccelerationVector:
    ax_m_s2: float
    ay_m_s2: float

    @property
    def magnitude_m_s2(self) -> float:
        return math.hypot(self.ax_m_s2, self.ay_m_s2)


@dataclass(frozen=True)
class SensorResponse:
    acceleration: AccelerationVector
    a_bragg_m_s2: float
    a_x_estimate_m_s2: float


@dataclass(frozen=True)
class MassPlacementDesign:
    positions_x_m: np.ndarray
    required_mass_positive_kg: np.ndarray
    required_mass_signed_kg: np.ndarray
    delta_ax_per_kg_m_s2: np.ndarray
    target_gradient_s2: float


@dataclass(frozen=True)
class FixedPositionMassScan:
    masses_kg: np.ndarray
    ax21_m_s2: np.ndarray
    ax22_m_s2: np.ndarray
    delta_ax_m_s2: np.ndarray
    gradient_ax_s2: np.ndarray
    gradient_x_estimate_s2: np.ndarray


def first_order_bragg_keff(wavelength_m: float) -> float:
    if wavelength_m <= 0.0:
        raise ValueError("The Bragg wavelength must be positive.")
    return 4.0 * math.pi / wavelength_m


def horizontal_gradiometer_points(baseline_m: float) -> tuple[FieldPoint, FieldPoint]:
    if baseline_m <= 0.0:
        raise ValueError("The interferometer baseline must be positive.")
    return (
        FieldPoint(name="MIGA21", x_m=0.0, y_m=0.0),
        FieldPoint(name="MIGA22", x_m=baseline_m, y_m=0.0),
    )


def source_mass_acceleration(source: SourceMass, point: FieldPoint) -> AccelerationVector:
    dx_m = source.x_m - point.x_m
    dy_m = source.y_m - point.y_m
    radius_m = math.hypot(dx_m, dy_m)
    if radius_m == 0.0:
        raise ValueError(f"{point.name} is colocated with the source mass.")

    prefactor = G_SI * source.mass_kg / radius_m**3
    return AccelerationVector(
        ax_m_s2=prefactor * dx_m,
        ay_m_s2=prefactor * dy_m,
    )


def bragg_axis(alpha_rad: float) -> tuple[float, float]:
    return math.cos(alpha_rad), math.sin(alpha_rad)


def project_acceleration_on_bragg(acceleration: AccelerationVector, alpha_rad: float) -> float:
    cos_alpha, sin_alpha = bragg_axis(alpha_rad)
    return acceleration.ax_m_s2 * cos_alpha + acceleration.ay_m_s2 * sin_alpha


def laboratory_gravity_acceleration(gravity_m_s2: float) -> AccelerationVector:
    return AccelerationVector(ax_m_s2=0.0, ay_m_s2=-abs(gravity_m_s2))


def background_gravity_projection_on_bragg(alpha_rad: float, gravity_m_s2: float) -> float:
    return project_acceleration_on_bragg(laboratory_gravity_acceleration(gravity_m_s2), alpha_rad)


def remove_background_gravity_from_beam_acceleration(
    total_beam_acceleration_m_s2: float,
    alpha_rad: float,
    gravity_m_s2: float,
) -> float:
    return total_beam_acceleration_m_s2 - background_gravity_projection_on_bragg(alpha_rad, gravity_m_s2)


def beam_acceleration_to_x_axis_after_gravity_subtraction(
    total_beam_acceleration_m_s2: float,
    alpha_rad: float,
    gravity_m_s2: float,
) -> float:
    return beam_acceleration_to_x_axis_estimate(
        remove_background_gravity_from_beam_acceleration(total_beam_acceleration_m_s2, alpha_rad, gravity_m_s2),
        alpha_rad,
    )


def beam_acceleration_to_x_axis_estimate(a_bragg_m_s2: float, alpha_rad: float) -> float:
    cos_alpha = math.cos(alpha_rad)
    if abs(cos_alpha) < 1.0e-15:
        raise ValueError("alpha is too close to 90 degrees to infer x-axis acceleration.")
    return a_bragg_m_s2 / cos_alpha


def x_axis_acceleration_to_beam(ax_m_s2: float, alpha_rad: float) -> float:
    return ax_m_s2 * math.cos(alpha_rad)


def vector_to_x_axis_estimate(acceleration: AccelerationVector, alpha_rad: float) -> float:
    return beam_acceleration_to_x_axis_estimate(
        project_acceleration_on_bragg(acceleration, alpha_rad),
        alpha_rad,
    )


def response_from_source_mass(source: SourceMass, point: FieldPoint, alpha_rad: float) -> SensorResponse:
    acceleration = source_mass_acceleration(source, point)
    a_bragg_m_s2 = project_acceleration_on_bragg(acceleration, alpha_rad)
    a_x_estimate_m_s2 = beam_acceleration_to_x_axis_estimate(a_bragg_m_s2, alpha_rad)
    return SensorResponse(
        acceleration=acceleration,
        a_bragg_m_s2=a_bragg_m_s2,
        a_x_estimate_m_s2=a_x_estimate_m_s2,
    )


def fringe_period_to_beam_acceleration(
    period_value: float,
    period_unit: str,
    k_eff_m_inv: float,
    sign: float = 1.0,
) -> float:
    if period_value <= 0.0:
        raise ValueError("The fringe period must be positive.")

    if period_unit == "ms^2":
        period_s2 = period_value * 1.0e-6
    elif period_unit == "s^2":
        period_s2 = period_value
    else:
        raise ValueError(f"Unsupported period unit: {period_unit}")

    return sign * (2.0 * math.pi) / (k_eff_m_inv * period_s2)


def angular_frequency_to_beam_acceleration(
    omega_value: float,
    omega_unit: str,
    k_eff_m_inv: float,
) -> float:
    if omega_unit == "rad/ms^2":
        omega_rad_s2 = omega_value * 1.0e6
    elif omega_unit == "rad/s^2":
        omega_rad_s2 = omega_value
    else:
        raise ValueError(f"Unsupported angular-frequency unit: {omega_unit}")

    return omega_rad_s2 / k_eff_m_inv


def beam_acceleration_to_angular_frequency(
    acceleration_m_s2: float,
    omega_unit: str,
    k_eff_m_inv: float,
) -> float:
    omega_rad_s2 = k_eff_m_inv * acceleration_m_s2
    if omega_unit == "rad/ms^2":
        return omega_rad_s2 * 1.0e-6
    if omega_unit == "rad/s^2":
        return omega_rad_s2
    raise ValueError(f"Unsupported angular-frequency unit: {omega_unit}")


def fringe_signal(
    t_squared_ms2: Iterable[float],
    beam_acceleration_m_s2: float,
    k_eff_m_inv: float,
    phase_offset_rad: float,
    contrast: float,
    offset: float = 0.0,
) -> np.ndarray:
    t_squared_ms2 = np.asarray(list(t_squared_ms2), dtype=float)
    t_squared_s2 = t_squared_ms2 * 1.0e-6
    phase_rad = k_eff_m_inv * beam_acceleration_m_s2 * t_squared_s2 + phase_offset_rad
    return offset + contrast * np.cos(phase_rad)


def differential_acceleration(a2_m_s2: float, a1_m_s2: float) -> float:
    return a2_m_s2 - a1_m_s2


def acceleration_gradient(delta_a_m_s2: float, baseline_m: float) -> float:
    if baseline_m <= 0.0:
        raise ValueError("The interferometer baseline must be positive.")
    return delta_a_m_s2 / baseline_m


def required_mass_profile_for_target_gradient(
    target_gradient_s2: float,
    positions_x_m: Iterable[float],
    baseline_m: float,
) -> MassPlacementDesign:
    positions_x_m = np.asarray(list(positions_x_m), dtype=float)
    target_delta_ax = target_gradient_s2 * baseline_m
    miga21, miga22 = horizontal_gradiometer_points(baseline_m)

    signed_mass = np.full_like(positions_x_m, np.nan, dtype=float)
    positive_mass = np.full_like(positions_x_m, np.nan, dtype=float)
    delta_ax_per_kg = np.full_like(positions_x_m, np.nan, dtype=float)

    for index, x_m in enumerate(positions_x_m):
        if abs(x_m - miga21.x_m) < 1.0e-9 or abs(x_m - miga22.x_m) < 1.0e-9:
            continue

        unit_source = SourceMass(mass_kg=1.0, x_m=float(x_m), y_m=0.0)
        response_21 = source_mass_acceleration(unit_source, miga21)
        response_22 = source_mass_acceleration(unit_source, miga22)
        delta_unit = differential_acceleration(response_22.ax_m_s2, response_21.ax_m_s2)
        delta_ax_per_kg[index] = delta_unit

        if abs(delta_unit) < 1.0e-30:
            continue

        signed_value = target_delta_ax / delta_unit
        signed_mass[index] = signed_value
        if signed_value >= 0.0:
            positive_mass[index] = signed_value

    return MassPlacementDesign(
        positions_x_m=positions_x_m,
        required_mass_positive_kg=positive_mass,
        required_mass_signed_kg=signed_mass,
        delta_ax_per_kg_m_s2=delta_ax_per_kg,
        target_gradient_s2=target_gradient_s2,
    )


def fixed_position_mass_scan(
    masses_kg: Iterable[float],
    source_x_m: float,
    source_y_m: float,
    baseline_m: float,
    alpha_rad: float,
) -> FixedPositionMassScan:
    masses_kg = np.asarray(list(masses_kg), dtype=float)
    miga21, miga22 = horizontal_gradiometer_points(baseline_m)

    unit_source = SourceMass(mass_kg=1.0, x_m=source_x_m, y_m=source_y_m)
    response_21 = response_from_source_mass(unit_source, miga21, alpha_rad)
    response_22 = response_from_source_mass(unit_source, miga22, alpha_rad)

    ax21 = masses_kg * response_21.acceleration.ax_m_s2
    ax22 = masses_kg * response_22.acceleration.ax_m_s2
    delta_ax = ax22 - ax21
    gradient_ax = delta_ax / baseline_m

    x_est_21 = masses_kg * response_21.a_x_estimate_m_s2
    x_est_22 = masses_kg * response_22.a_x_estimate_m_s2
    gradient_x_estimate = (x_est_22 - x_est_21) / baseline_m

    return FixedPositionMassScan(
        masses_kg=masses_kg,
        ax21_m_s2=ax21,
        ax22_m_s2=ax22,
        delta_ax_m_s2=delta_ax,
        gradient_ax_s2=gradient_ax,
        gradient_x_estimate_s2=gradient_x_estimate,
    )
