from math import isclose, sqrt
import unittest

from mot_model import (
    BODY_DIAGONAL_PROJECTION,
    LaunchParameters,
    axial_force_n,
    ideal_launch_velocity_m_s,
    steady_state_velocity,
)


class MotModelTests(unittest.TestCase):
    def test_ideal_velocity_matches_closed_form(self) -> None:
        params = LaunchParameters(delta_f_mhz=2.0, wavelength_nm=780.0, include_gravity=False)
        expected = sqrt(3.0) * 780.0e-9 * 2.0e6
        self.assertTrue(isclose(ideal_launch_velocity_m_s(params), expected, rel_tol=1e-12))

    def test_projection_is_body_diagonal_value(self) -> None:
        params = LaunchParameters(delta_f_mhz=1.0, projection=BODY_DIAGONAL_PROJECTION)
        expected = 1.0 / sqrt(3.0)
        self.assertTrue(isclose(params.projection, expected, rel_tol=1e-12))

    def test_force_cancels_at_ideal_velocity_without_gravity(self) -> None:
        params = LaunchParameters(
            delta_f_mhz=3.0,
            wavelength_nm=780.0,
            mean_detuning_mhz=-12.0,
            linewidth_mhz=6.065,
            saturation_parameter=0.25,
            include_gravity=False,
        )
        velocity = ideal_launch_velocity_m_s(params)
        self.assertAlmostEqual(axial_force_n(params, velocity), 0.0, delta=1e-24)

    def test_steady_state_stays_close_to_ideal_without_gravity(self) -> None:
        params = LaunchParameters(
            delta_f_mhz=2.5,
            wavelength_nm=780.0,
            mean_detuning_mhz=-15.0,
            linewidth_mhz=6.065,
            saturation_parameter=0.20,
            include_gravity=False,
        )
        steady = steady_state_velocity(params)
        ideal = ideal_launch_velocity_m_s(params)
        self.assertTrue(steady.converged)
        self.assertTrue(isclose(steady.velocity_m_s, ideal, rel_tol=1e-4))


if __name__ == "__main__":
    unittest.main()
