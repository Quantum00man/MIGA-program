"""Teaching example: Bragg two-momentum-state radial ensemble integral.

This is NOT a validated fit to MIGA21/MIGA22. It demonstrates the
normalization, B(T), A(T), and finite-difference dB/dT formula.
Requires: numpy
"""
import numpy as np
from numpy.polynomial.laguerre import laggauss

KB = 1.380649e-23
M_RB87 = 1.44316e-25
FLIGHT_S = 0.4305
WAIST_M = 12e-3
INITIAL_SIGMA_M = 0.0
ON_AXIS_AREAS = (1.5, 3.2, 1.5)  # rad; illustrative only, not fit
N_QUAD = 80

u_nodes, u_weights = laggauss(N_QUAD)


def ba_at_temperature(temp_uK, areas=ON_AXIS_AREAS):
    temperature_K = temp_uK * 1e-6
    sigma2 = INITIAL_SIGMA_M ** 2 + KB * temperature_K * FLIGHT_S ** 2 / M_RB87
    intensity_factor = np.exp(-4 * sigma2 * u_nodes / WAIST_M ** 2)
    a, b, c = [np.sin(0.5 * area * intensity_factor) ** 2 for area in areas]
    b_atom = b + (a + c - 2 * a * c) * (1 - 2 * b)
    a_atom = 2 * b * np.sqrt(a * (1 - a) * c * (1 - c))
    return float(np.dot(u_weights, b_atom)), float(np.dot(u_weights, a_atom))


def temperature_slope(temp_uK, step_uK=0.01, areas=ON_AXIS_AREAS):
    bp, _ = ba_at_temperature(temp_uK + step_uK, areas)
    bm, _ = ba_at_temperature(temp_uK - step_uK, areas)
    return (bp - bm) / (2 * step_uK)


def conditional_from_older_slopes():
    # The two K values below were obtained from an earlier simplified
    # assumed model and are NOT experimentally established.
    items = [
        ('MIGA22', 2.599, 0.151, 0.175, -0.0672),
        ('MIGA21', 1.869, 0.109, 0.210, -0.0889),
    ]
    phase_sigmas = []
    print('Illustrative radial model -- not calibrated to experiment')
    for name, T, sigma_T, measured_A, old_K in items:
        B, A = ba_at_temperature(T)
        K = temperature_slope(T)
        response_mrad = abs(K) * sigma_T / measured_A * 1000
        old_mrad = abs(old_K) * sigma_T / measured_A * 1000
        phase_sigmas.append(old_mrad)
        print(f'{name}: B_model={B:.6f}, A_model={A:.6f}, '
              f'K_model={K:.6f} 1/uK, illustrative={response_mrad:.3f} mrad')
        print(f'     previous conditional K={old_K:.4f} 1/uK '
              f'-> {old_mrad:.3f} mrad')
    print('Previous conditional independent differential = '
          f'{np.hypot(*phase_sigmas):.3f} mrad')


if __name__ == '__main__':
    conditional_from_older_slopes()
