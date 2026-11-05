"""Regression tests for launch jitter; run with python test_launch.py."""
import math
from dataclasses import replace
from unittest.mock import patch
import miga_temperature_core as core


def near(a,b,tol):
    assert abs(a-b) < tol, (a,b,tol)


def run():
    geo=core.Geometry()
    s22,s21=core.default_sources()
    c=core.LaunchSettings(wavefront_enabled=True)
    x22=core.LaunchSource(.7996,103.8)
    x21=core.LaunchSource(.8,115.)
    for x,v,sv,sz in ((x22,4.265959961,.4644928,.2019886),(x21,4.26775,.5146609,.2238985)):
        k=core.launch_kinematics(c,x,10)
        near(k['velocity_m_s'],v,1e-7)
        near(k['velocity_allan_m_s']*1000,sv,1e-6)
        near(k['pulse_position_allan_m'][1]*1000,sz,1e-6)
    with patch.object(core,'_launch_calibrate',wraps=core._launch_calibrate) as calibration:
        result=core.analyze_launch_pair(geo,s22,s21,c,x22,x21,True)
        assert calibration.call_count == 4, 'Only nominal calibration at each of two integration orders per source'
    q22=result['sources']['MIGA22'];q21=result['sources']['MIGA21']; diff=result['differential']
    near(diff['middle_position_mm'],.3015459,1e-6)
    near(q22['allan']['wavefront_mrad'],15.96177,1e-4)
    near(q21['allan']['wavefront_mrad'],17.69316,1e-4)
    near(diff['wavefront_mrad'],23.82910,1e-4)
    for q in (q22,q21):
        k=q['sensitivity']; a=q['allan']; sv=q['kinematics']['velocity_allan_m_s']
        near(k['K_B_per_m_s'],k['K_B_halfstep_per_m_s'],0.001)
        assert abs(k['K_B_per_m_s']-k['K_B_comparison_order_per_m_s']) < max(.05*abs(k['K_B_comparison_order_per_m_s']),.001)
        near(a['total_mrad'],1000*abs(k['baseline_rad_per_m_s']+k['wavefront_rad_per_m_s'])*sv,1e-10)
        near((q['nominal']['p1']+q['nominal']['p3'])/2,.2,1e-8)
        near(q['nominal']['p2'],.4,1e-8)
    near(diff['total_mrad'],math.hypot(q22['allan']['total_mrad'],q21['allan']['total_mrad']),1e-10)
    plane=core.launch_wavefront_sensitivity(c,replace(x22,wavefront_radius_m=0),q22['kinematics'])
    assert plane==0
    assert core.launch_wavefront_sensitivity(replace(c,wavefront_enabled=False),x22,q22['kinematics'])==0
    # At a fixed laboratory middle time, kinematics correctly avoid moving the pulse with apex.
    fixed=core.launch_kinematics(replace(c,middle_pulse_ms=430),x22,10)
    near(fixed['pulse_position_allan_m'][1],.430*fixed['velocity_allan_m_s'],1e-15)
    # For zero jitter, all propagated linear terms vanish, including the wavefront.
    zero=core.analyze_launch_source(geo,s22,replace(c,quadrature_order=12,comparison_order=16),replace(x22,detection_allan_us=0),False)
    assert zero['kinematics']['velocity_allan_m_s']==0
    assert all(v==0 for v in zero['allan'].values())
    # Spatially uniform coupling cannot produce an appreciable position response.
    wide=core.analyze_launch_source(replace(geo,beam_waist_mm=10000),s22,replace(c,quadrature_order=12,comparison_order=16),replace(x22,vertical_offset_mm=3),False)
    assert abs(wide['sensitivity']['K_B_per_m_s']) < .001
    # Nonconverged quadrature must be reported, not silently accepted.
    coarse=core.analyze_launch_source(geo,s22,replace(c,quadrature_order=8,comparison_order=12),x22,False)
    assert any('Quadrature' in w for w in coarse['warnings'])
    # Changing fringe slope reverses only the signed baseline contribution.
    reverse=core.analyze_launch_source(geo,s22,replace(c,quadrature_order=12,comparison_order=16,fringe_slope_sign=-1),x22,False)
    near(reverse['sensitivity']['baseline_rad_per_m_s'], -zero['sensitivity']['baseline_rad_per_m_s'], 1e-12)
    near(reverse['sensitivity']['wavefront_rad_per_m_s'], zero['sensitivity']['wavefront_rad_per_m_s'], 1e-12)
    expected=reverse['sensitivity']['baseline_rad_per_m_s']+reverse['sensitivity']['wavefront_rad_per_m_s']
    near(reverse['sensitivity']['total_rad_per_m_s'],expected,1e-12)
    print('PASS: kinematics, wavefront, quadrature/step convergence, fixed calibration, zero and uniform limits, signed combination')
    print('Default conditional baseline differential:',diff['baseline_mrad'],'mrad')
    print('Default conditional wavefront differential:',diff['wavefront_mrad'],'mrad')


if __name__=='__main__': run()
