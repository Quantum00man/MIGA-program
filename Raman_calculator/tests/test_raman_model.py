from __future__ import annotations

import unittest

import numpy as np

from app import BUNDLED_PRESETS
from raman_model import (
    DEFAULT_TEMPERATURE_UK,
    RamanSimulationParameters,
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


if __name__ == "__main__":
    unittest.main()
