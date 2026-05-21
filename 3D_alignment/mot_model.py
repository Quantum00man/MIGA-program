from __future__ import annotations

from dataclasses import dataclass
from math import acos, pi, sqrt

C = 299_792_458.0
HBAR = 1.054_571_817e-34
AMU = 1.660_539_066_60e-27
G = 9.806_65

BODY_DIAGONAL_PROJECTION = 1.0 / sqrt(3.0)
BODY_DIAGONAL_ANGLE_DEG = acos(BODY_DIAGONAL_PROJECTION) * 180.0 / pi

ATOM_MASSES_AMU = {
    "87Rb": 86.909_180_531_0,
    "85Rb": 84.911_789_737_9,
    "133Cs": 132.905_451_961_0,
    "23Na": 22.989_769_282_0,
    "39K": 38.963_706_486_4,
    "custom": 86.909_180_531_0,
}


@dataclass(frozen=True)
class LaunchParameters:
    delta_f_mhz: float
    wavelength_nm: float = 780.0
    mean_detuning_mhz: float = -12.0
    linewidth_mhz: float = 6.065
    saturation_parameter: float = 0.30
    interaction_time_ms: float = 3.0
    mass_amu: float = ATOM_MASSES_AMU["87Rb"]
    include_gravity: bool = True
    projection: float = BODY_DIAGONAL_PROJECTION


@dataclass(frozen=True)
class ForceBalanceResult:
    velocity_m_s: float
    residual_force_n: float
    converged: bool


@dataclass(frozen=True)
class LaunchSimulationResult:
    times_s: list[float]
    velocities_m_s: list[float]
    heights_m: list[float]
    final_velocity_m_s: float
    final_height_m: float


def validate_parameters(params: LaunchParameters) -> None:
    if params.delta_f_mhz < 0.0:
        raise ValueError(
            "Δf 必须是非负数；这里约定输入的是每组光相对平均频率的单边偏移。\n"
            "Δf must be non-negative; this program expects the single-sided offset of each beam group from the shared mean frequency."
        )
    if params.wavelength_nm <= 0.0:
        raise ValueError("波长必须大于 0 nm。\nWavelength must be greater than 0 nm.")
    if params.linewidth_mhz <= 0.0:
        raise ValueError("自然线宽 Γ/2π 必须大于 0 MHz。\nNatural linewidth Γ/2π must be greater than 0 MHz.")
    if params.saturation_parameter < 0.0:
        raise ValueError("单束饱和参数 s0 不能为负数。\nSingle-beam saturation parameter s0 cannot be negative.")
    if params.interaction_time_ms <= 0.0:
        raise ValueError("发射时间必须大于 0 ms。\nLaunch time must be greater than 0 ms.")
    if params.mass_amu <= 0.0:
        raise ValueError("原子质量必须大于 0 amu。\nAtomic mass must be greater than 0 amu.")
    if not 0.0 < params.projection <= 1.0:
        raise ValueError("几何投影因子必须落在 (0, 1] 内。\nGeometric projection factor must lie in (0, 1].")


def ideal_launch_velocity_m_s(params: LaunchParameters) -> float:
    validate_parameters(params)
    wavelength_m = params.wavelength_nm * 1e-9
    delta_f_hz = params.delta_f_mhz * 1e6
    return wavelength_m * delta_f_hz / params.projection


def total_frequency_difference_mhz(params: LaunchParameters) -> float:
    return 2.0 * params.delta_f_mhz


def mass_kg(params: LaunchParameters) -> float:
    return params.mass_amu * AMU


def axial_wavevector_magnitude(params: LaunchParameters) -> float:
    wavelength_m = params.wavelength_nm * 1e-9
    return (2.0 * pi / wavelength_m) * params.projection


def _single_beam_scattering_rate_s(
    detuning_rad_s: float,
    linewidth_rad_s: float,
    saturation_parameter: float,
    total_saturation: float,
) -> float:
    denominator = 1.0 + total_saturation + (2.0 * detuning_rad_s / linewidth_rad_s) ** 2
    return 0.5 * linewidth_rad_s * saturation_parameter / denominator


def axial_force_n(params: LaunchParameters, velocity_m_s: float) -> float:
    validate_parameters(params)

    linewidth_rad_s = 2.0 * pi * params.linewidth_mhz * 1e6
    mean_detuning_rad_s = 2.0 * pi * params.mean_detuning_mhz * 1e6
    delta_f_rad_s = 2.0 * pi * params.delta_f_mhz * 1e6
    k_projection = axial_wavevector_magnitude(params)
    total_saturation = 6.0 * params.saturation_parameter

    detuning_down = mean_detuning_rad_s + delta_f_rad_s - k_projection * velocity_m_s
    detuning_up = mean_detuning_rad_s - delta_f_rad_s + k_projection * velocity_m_s

    rate_down = _single_beam_scattering_rate_s(
        detuning_rad_s=detuning_down,
        linewidth_rad_s=linewidth_rad_s,
        saturation_parameter=params.saturation_parameter,
        total_saturation=total_saturation,
    )
    rate_up = _single_beam_scattering_rate_s(
        detuning_rad_s=detuning_up,
        linewidth_rad_s=linewidth_rad_s,
        saturation_parameter=params.saturation_parameter,
        total_saturation=total_saturation,
    )

    radiative_force = 3.0 * HBAR * k_projection * (rate_down - rate_up)
    gravity_force = mass_kg(params) * G if params.include_gravity else 0.0
    return radiative_force - gravity_force


def axial_acceleration_m_s2(params: LaunchParameters, velocity_m_s: float) -> float:
    return axial_force_n(params, velocity_m_s) / mass_kg(params)


def steady_state_velocity(params: LaunchParameters) -> ForceBalanceResult:
    validate_parameters(params)

    ideal_velocity = ideal_launch_velocity_m_s(params)
    search_max = max(6.0, 2.5 * max(ideal_velocity, 0.1), ideal_velocity + 4.0)
    samples = 4_001
    velocities = [search_max * index / (samples - 1) for index in range(samples)]
    forces = [axial_force_n(params, velocity) for velocity in velocities]

    sign_change_intervals: list[tuple[float, float]] = []
    best_index = min(range(samples), key=lambda index: abs(forces[index]))

    for index in range(samples - 1):
        left_force = forces[index]
        right_force = forces[index + 1]
        if left_force == 0.0:
            return ForceBalanceResult(
                velocity_m_s=velocities[index],
                residual_force_n=0.0,
                converged=True,
            )
        if left_force * right_force < 0.0:
            sign_change_intervals.append((velocities[index], velocities[index + 1]))

    if not sign_change_intervals:
        return ForceBalanceResult(
            velocity_m_s=velocities[best_index],
            residual_force_n=forces[best_index],
            converged=False,
        )

    left, right = min(
        sign_change_intervals,
        key=lambda interval: abs(0.5 * (interval[0] + interval[1]) - ideal_velocity),
    )

    for _ in range(80):
        midpoint = 0.5 * (left + right)
        left_force = axial_force_n(params, left)
        mid_force = axial_force_n(params, midpoint)

        if abs(mid_force) < 1e-27:
            return ForceBalanceResult(
                velocity_m_s=midpoint,
                residual_force_n=mid_force,
                converged=True,
            )

        if left_force * mid_force <= 0.0:
            right = midpoint
        else:
            left = midpoint

    midpoint = 0.5 * (left + right)
    residual_force = axial_force_n(params, midpoint)
    return ForceBalanceResult(
        velocity_m_s=midpoint,
        residual_force_n=residual_force,
        converged=abs(residual_force) < 1e-24,
    )


def force_profile(params: LaunchParameters, points: int = 321) -> tuple[list[float], list[float]]:
    validate_parameters(params)
    ideal_velocity = ideal_launch_velocity_m_s(params)
    span = max(6.0, 2.5 * max(ideal_velocity, 0.1), ideal_velocity + 4.0)
    velocities = [span * index / (points - 1) for index in range(points)]
    forces = [axial_force_n(params, velocity) for velocity in velocities]
    return velocities, forces


def simulate_launch(params: LaunchParameters) -> LaunchSimulationResult:
    validate_parameters(params)

    total_time_s = params.interaction_time_ms * 1e-3
    steps = max(600, min(8_000, int(total_time_s / 5e-6)))
    dt = total_time_s / steps

    def acceleration(velocity_m_s: float) -> float:
        return axial_acceleration_m_s2(params, velocity_m_s)

    times = [0.0]
    velocities = [0.0]
    heights = [0.0]
    velocity = 0.0
    height = 0.0

    sample_stride = max(1, steps // 300)

    for step in range(1, steps + 1):
        k1_v = acceleration(velocity)
        k1_z = velocity

        v2 = velocity + 0.5 * dt * k1_v
        k2_v = acceleration(v2)
        k2_z = v2

        v3 = velocity + 0.5 * dt * k2_v
        k3_v = acceleration(v3)
        k3_z = v3

        v4 = velocity + dt * k3_v
        k4_v = acceleration(v4)
        k4_z = v4

        velocity += (dt / 6.0) * (k1_v + 2.0 * k2_v + 2.0 * k3_v + k4_v)
        height += (dt / 6.0) * (k1_z + 2.0 * k2_z + 2.0 * k3_z + k4_z)

        if step % sample_stride == 0 or step == steps:
            times.append(step * dt)
            velocities.append(velocity)
            heights.append(height)

    return LaunchSimulationResult(
        times_s=times,
        velocities_m_s=velocities,
        heights_m=heights,
        final_velocity_m_s=velocity,
        final_height_m=height,
    )


def ballistic_apex_height_m(initial_height_m: float, launch_velocity_m_s: float) -> float:
    if launch_velocity_m_s <= 0.0:
        return initial_height_m
    return initial_height_m + launch_velocity_m_s**2 / (2.0 * G)
