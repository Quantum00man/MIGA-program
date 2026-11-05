"""Lightweight tests for the physics core; run: python test_model.py"""
import math
from miga_temperature_core import (
    Geometry, Source, default_sources, analyze_pair, calibrate, evaluate, samples,
)


def run():
    geo=Geometry(radial_order=80)
    s22,s21=default_sources()
    results=analyze_pair(geo,s22,s21,build_scan=False)
    for name,r in results['sources'].items():
        source=r['source']
        cal=r['calibration']
        assert abs((cal['efficiency_p1']+cal['efficiency_p3'])/2-source['splitter_efficiency'])<1e-8
        assert abs(cal['efficiency_p2']-source['mirror_efficiency'])<1e-8
        assert 0<=r['nominal']['B']<=1 and 0<=r['nominal']['A']<=0.5
        assert r['allan']['apparent_phase_mrad']>=0
    assert 56<results['sources']['MIGA22']['allan']['apparent_phase_mrad']<60
    assert 44<results['sources']['MIGA21']['allan']['apparent_phase_mrad']<49
    assert 72<results['differential']['temperature_baseline_phase_allan_mrad']<76
    # Numerical convergence in radial quadrature.
    hi=analyze_pair(Geometry(radial_order=120),s22,s21,build_scan=False)
    for name in ('MIGA22','MIGA21'):
        old=results['sources'][name]['derivatives']['K_B_per_uK']
        new=hi['sources'][name]['derivatives']['K_B_per_uK']
        assert abs(old-new)<1e-5,(name,old,new)
    # Sampling of laser power for a centered Gaussian cloud.
    from numpy import dot
    cloud=samples(geo,s22,s22.temperature_uK)
    effective=dot(cloud['weights'],cloud['factors'][1])
    sigma2=cloud['sigma_r_apex_mm']**2
    analytic=1/(1+4*sigma2/geo.beam_waist_mm**2)
    assert abs(effective-analytic)<2e-6,(effective,analytic)
    # Source temperature excursions MUST NOT re-calibrate the peak pulse areas.
    cal=calibrate(geo,s22)
    plus=evaluate(geo,s22,cal['theta_s'],cal['theta_m'],s22.temperature_uK+0.1)
    assert abs(plus['splitter_first']-s22.splitter_efficiency)>1e-5
    # Full 4D is provided only as an advanced, convergence-sensitive option.
    g4=Geometry(integration_mode='4D trajectory (slower)',quadrature_order=6)
    x=analyze_pair(g4,s22,s21,build_scan=False)
    assert x['differential']['temperature_baseline_phase_allan_mrad']>=0
    print('PASS: radial convergence, pulse-area calibration, intensity average, 4D smoke test')
    print('Default conditional model results:')
    for name,r in results['sources'].items():
        print(name, f'B={r["nominal"]["B"]:.5f}',f'A={r["nominal"]["A"]:.5f}',
              f'K_B={r["derivatives"]["K_B_per_uK"]:+.6f}/uK',
              f'baseline phase={r["allan"]["apparent_phase_mrad"]:.3f}mrad')
    print(f'Differential={results["differential"]["temperature_baseline_phase_allan_mrad"]:.3f}mrad')


if __name__=='__main__':
    run()
