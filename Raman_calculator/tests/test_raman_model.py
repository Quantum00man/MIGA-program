from __future__ import annotations

import unittest

import numpy as np

from app import BUNDLED_PRESETS
from raman_model import (
    BRAGG_TRANSITION,
    DEFAULT_TEMPERATURE_UK,
    SATURATION_INTENSITY_W_M2,
    RamanSimulationParameters,
    effective_bragg_rabi_frequency,
    effective_raman_rabi_frequency,
    first_peak_with_quadratic_refinement,
    simulate_rabi_oscillation,
)


class RamanModelTest(unittest.TestCase):
    def test_default_temperatures_match_current_default(self) -> None:
        params = RamanSimulationParameters()

        self.assertAlmostEqual(
            params.transverse_temperature_uK, DEFAULT_TEMPERATURE_UK, places=9
        )
        self.assertAlmostEqual(
            params.longitudinal_temperature_uK,
            DEFAULT_TEMPERATURE_UK,
            places=9,
        )
        self.assertFalse(params.use_separate_longitudinal_temperature)
        self.assertAlmostEqual(
            params.longitudinal_velocity_sigma_m_s,
            params.transverse_velocity_sigma_m_s,
            places=12,
        )

    def test_separate_longitudinal_temperature_changes_only_longitudinal_sigma(self) -> None:
        linked = RamanSimulationParameters(
            transverse_temperature_uK=2.5,
            use_separate_longitudinal_temperature=False,
            longitudinal_temperature_uK=0.7,
        )
        separate = RamanSimulationParameters(
            transverse_temperature_uK=2.5,
            use_separate_longitudinal_temperature=True,
            longitudinal_temperature_uK=0.7,
        )

        self.assertAlmostEqual(
            linked.transverse_velocity_sigma_m_s,
            separate.transverse_velocity_sigma_m_s,
            places=12,
        )
        self.assertNotAlmostEqual(
            linked.longitudinal_velocity_sigma_m_s,
            separate.longitudinal_velocity_sigma_m_s,
            places=12,
        )

    def test_simulation_smoke(self) -> None:
        params = RamanSimulationParameters(
            tau_points=48,
            radial_points=56,
            velocity_points=56,
        )
        result = simulate_rabi_oscillation(params)

        self.assertEqual(result.tau_us.shape, (48,))
        self.assertEqual(result.transition_probability.shape, (48,))
        self.assertEqual(result.cloud_time_s.shape, (48,))
        self.assertEqual(result.cloud_time_display.shape, (48,))
        self.assertEqual(result.cloud_radius_mm.shape, (48,))
        self.assertTrue(np.all(result.transition_probability >= 0.0))
        self.assertTrue(np.all(result.transition_probability <= 1.0))
        self.assertTrue(np.all(np.diff(result.cloud_radius_mm) >= 0.0))
        self.assertGreaterEqual(result.on_axis_rabi_khz, 0.0)
        self.assertTrue(np.isfinite(result.ensemble_optimal_pulse_time_us))
        self.assertTrue(np.isfinite(result.ensemble_optimal_probability))
        self.assertGreater(result.cloud_radius_mm[-1], result.cloud_radius_mm[0])
        self.assertEqual(result.cloud_time_unit, "ms")

    def test_bundled_presets_match_requested_values(self) -> None:
        self.assertEqual(BUNDLED_PRESETS["Raman Down"]["p1_mw"], 14.0)
        self.assertEqual(BUNDLED_PRESETS["Raman Down"]["p2_mw"], 7.0)
        self.assertEqual(BUNDLED_PRESETS["Raman Down"]["w0_mm"], 11.5)
        self.assertEqual(BUNDLED_PRESETS["Raman Down"]["expansion_time_ms"], 56.0)
        self.assertEqual(BUNDLED_PRESETS["Raman Down"]["desacc_mhz"], -1300.0)
        self.assertEqual(BUNDLED_PRESETS["Raman Up"]["expansion_time_ms"], 78.0)
        self.assertEqual(BUNDLED_PRESETS["Raman Labeling"]["expansion_time_ms"], 780.0)
        self.assertEqual(BUNDLED_PRESETS["Bragg"]["transition_kind"], BRAGG_TRANSITION)
        self.assertEqual(BUNDLED_PRESETS["Bragg"]["p1_mw"], 60.0)
        self.assertEqual(BUNDLED_PRESETS["Bragg"]["p2_mw"], 60.0)
        self.assertEqual(BUNDLED_PRESETS["Bragg"]["w0_mm"], 12.0)
        self.assertEqual(BUNDLED_PRESETS["Bragg"]["expansion_time_ms"], 430.0)
        self.assertEqual(BUNDLED_PRESETS["Bragg"]["desacc_mhz"], -1200.0)
        self.assertEqual(BUNDLED_PRESETS["Bragg"]["tau_max_us"], 150.0)
        self.assertEqual(BUNDLED_PRESETS["Bragg"]["gain"], 1.0)

    def test_bragg_simulation_uses_supplied_coupling_model(self) -> None:
        params = RamanSimulationParameters(
            transition_kind=BRAGG_TRANSITION,
            p1_mw=60.0,
            p2_mw=60.0,
            w0_mm=12.0,
            desacc_mhz=-1200.0,
            gain=1.0,
            tau_points=32,
            radial_points=40,
            velocity_points=40,
        )
        radii = np.array([0.0, params.w0_m])
        intensity_1 = (
            2.0
            * params.p1_w
            / (np.pi * params.w0_m**2)
            * np.exp(-2.0 * radii**2 / params.w0_m**2)
        )
        intensity_2 = (
            2.0
            * params.p2_w
            / (np.pi * params.w0_m**2)
            * np.exp(-2.0 * radii**2 / params.w0_m**2)
        )
        expected = np.abs(
            params.gamma_rad_s**2
            / params.attenuation
            * params.gain
            * np.sqrt(intensity_1 * intensity_2)
            / (2.0 * SATURATION_INTENSITY_W_M2)
            * (
                5.0 / (24.0 * params.desacc_rad_s)
                + 3.0
                / (24.0 * (params.desacc_rad_s + params.delta2_rad_s))
            )
            / 2.0
        )

        np.testing.assert_allclose(
            effective_bragg_rabi_frequency(radii, params), expected
        )
        # The supplied Bragg expression currently matches the Raman expression;
        # separate routing keeps the two models independently extensible.
        np.testing.assert_allclose(
            effective_bragg_rabi_frequency(radii, params),
            effective_raman_rabi_frequency(radii, params),
        )
        result = simulate_rabi_oscillation(params)
        self.assertEqual(result.transition_probability.shape, (32,))
        self.assertTrue(np.all(np.isfinite(result.transition_probability)))

    def test_first_peak_is_refined_between_samples(self) -> None:
        x = np.linspace(0.0, 4.0, 9)
        y = 1.0 - (x - 1.3) ** 2

        peak_x, peak_y = first_peak_with_quadratic_refinement(x, y)

        self.assertAlmostEqual(peak_x, 1.3, places=12)
        self.assertAlmostEqual(peak_y, 1.0, places=12)

    def test_peak_finder_does_not_treat_scan_boundary_as_optimum(self) -> None:
        x = np.linspace(0.0, 1.0, 8)
        y = x**2

        peak_x, peak_y = first_peak_with_quadratic_refinement(x, y)

        self.assertTrue(np.isnan(peak_x))
        self.assertTrue(np.isnan(peak_y))


if __name__ == "__main__":
    unittest.main()
