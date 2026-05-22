from __future__ import annotations

import unittest

from raman_detuning_model import (
    DetuningConstants,
    FALLING_DOWN,
    FLYING_UP,
    TRANSITION_F1_TO_F2,
    TRANSITION_F2_TO_F1,
    calibrate_alpha_and_vx_from_scans,
    compute_detuning_khz,
    compute_vx_from_detuning_auto,
)


class RamanDetuningModelTest(unittest.TestCase):
    def test_detuning_velocity_round_trip_for_all_cases(self) -> None:
        constants = DetuningConstants()
        vx_mm_s = 8.25

        for transition in (TRANSITION_F1_TO_F2, TRANSITION_F2_TO_F1):
            detunings = compute_detuning_khz(vx_mm_s, transition, constants)
            for motion in (FLYING_UP, FALLING_DOWN):
                positive_label = f"{motion}, Δ>0"
                negative_label = f"{motion}, Δ<0"

                positive = compute_vx_from_detuning_auto(
                    detunings[positive_label], motion, transition, constants
                )
                negative = compute_vx_from_detuning_auto(
                    detunings[negative_label], motion, transition, constants
                )

                self.assertAlmostEqual(positive.vx_mm_s, vx_mm_s, places=9)
                self.assertAlmostEqual(negative.vx_mm_s, vx_mm_s, places=9)

    def test_calibration_recovers_alpha_and_vx(self) -> None:
        constants = DetuningConstants(alpha_deg=4.85)
        vx_mm_s = 11.4
        detunings = compute_detuning_khz(vx_mm_s, TRANSITION_F1_TO_F2, constants)

        calibration = calibrate_alpha_and_vx_from_scans(
            detunings[f"{FLYING_UP}, Δ>0"],
            detunings[f"{FALLING_DOWN}, Δ>0"],
            TRANSITION_F1_TO_F2,
            DetuningConstants(
                vz_m_s=constants.vz_m_s,
                alpha_deg=0.0,
                laser_wavelength_m=constants.laser_wavelength_m,
                recoil_frequency_khz=constants.recoil_frequency_khz,
            ),
        )

        self.assertAlmostEqual(calibration.alpha_deg, constants.alpha_deg, places=9)
        self.assertAlmostEqual(calibration.vx_mm_s, vx_mm_s, places=9)


if __name__ == "__main__":
    unittest.main()
