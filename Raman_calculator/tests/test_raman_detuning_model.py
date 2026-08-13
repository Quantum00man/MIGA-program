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
    compute_light_shift_correction,
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

    def test_light_shift_correction_for_f1_to_f2(self) -> None:
        constants = DetuningConstants(recoil_frequency_khz=15.093)
        doppler_khz = 334.0
        light_shift_khz = 0.907
        measured_delta_plus_khz = doppler_khz + 15.093 + light_shift_khz
        measured_delta_minus_khz = -doppler_khz + 15.093 + light_shift_khz

        result = compute_light_shift_correction(
            measured_delta_plus_khz,
            measured_delta_minus_khz,
            TRANSITION_F1_TO_F2,
            constants,
        )

        self.assertAlmostEqual(result.light_shift_khz, light_shift_khz, places=12)
        self.assertAlmostEqual(result.doppler_term_khz, doppler_khz, places=12)
        self.assertAlmostEqual(
            result.corrected_delta_plus_khz, doppler_khz + 15.093, places=12
        )
        self.assertAlmostEqual(
            result.corrected_delta_minus_khz, -doppler_khz + 15.093, places=12
        )
        self.assertAlmostEqual(
            result.measured_coprop_center_khz, light_shift_khz, places=12
        )
        self.assertAlmostEqual(result.corrected_coprop_center_khz, 0.0, places=12)

    def test_light_shift_correction_uses_negative_recoil_for_reverse_transition(self) -> None:
        constants = DetuningConstants(recoil_frequency_khz=15.093)
        doppler_khz = 120.0
        light_shift_khz = -2.4
        signed_recoil_khz = -15.093

        result = compute_light_shift_correction(
            doppler_khz + signed_recoil_khz + light_shift_khz,
            -doppler_khz + signed_recoil_khz + light_shift_khz,
            TRANSITION_F2_TO_F1,
            constants,
        )

        self.assertAlmostEqual(result.signed_recoil_center_khz, -15.093, places=12)
        self.assertAlmostEqual(result.light_shift_khz, light_shift_khz, places=12)
        self.assertAlmostEqual(
            0.5
            * (result.corrected_delta_plus_khz + result.corrected_delta_minus_khz),
            -15.093,
            places=12,
        )
        self.assertAlmostEqual(
            result.measured_coprop_center_khz, light_shift_khz, places=12
        )
        self.assertAlmostEqual(result.corrected_coprop_center_khz, 0.0, places=12)


if __name__ == "__main__":
    unittest.main()
