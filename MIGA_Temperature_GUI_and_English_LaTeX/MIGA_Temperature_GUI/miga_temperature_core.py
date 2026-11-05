"""Conditional two-momentum-state Bragg baseline-noise calculator.

Physical scope
--------------
- Resonant two-momentum-state, pulse-area approximation; each atom has three
  position-dependent transfer probabilities a, b, c.
- Only the two closed Mach--Zehnder paths interfere; other paths add baseline.
- 2D transverse Gaussian position and velocity distributions, integrated with
  deterministic Gauss--Hermite quadrature over x0, y0, vx, vy.
- Optional effective Gaussian spatial acceptance at the middle pulse.
- Calibrate on-axis splitter/mirror pulse areas ONCE at nominal temperature.
  Then hold these physical pulse areas fixed while varying temperature.
- The quoted Allan deviation of temperature is propagated linearly to baseline
  Allan deviation and to mid-fringe equivalent phase using MEASURED amplitude.
- Independent sources are combined in quadrature, not subtracted linearly.

Not a quasi-Bragg multiport, Doppler-sensitive, or true diffraction-phase model.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from functools import lru_cache
from typing import Dict, Tuple, List
import json
import math
import numpy as np
from numpy.polynomial.hermite import hermgauss
from numpy.polynomial.laguerre import laggauss
from scipy.optimize import brentq

KB = 1.380649e-23       # J/K
M_RB87 = 1.44316060e-25  # kg
G0 = 9.80665

BRANCHES = (
    "First crossing (minimum positive pulse area)",
    "Pulse area > pi/2 (first available root)",
    "Descending: pi < area < 2pi",
    "Second rise: 2pi < area < 3pi",
    "Area between 3pi and 4pi",
)


@dataclass
class Geometry:
    beam_waist_mm: float = 12.0
    flight_time_ms: float = 430.5
    pulse_separation_ms: float = 10.0
    initial_rms_mm: float = 0.25
    quadrature_order: int = 10
    include_vertical_ballistic_shift: bool = False
    derivative_step_uK: float = 0.01
    integration_mode: str = "Radial (fast, centered)"
    radial_order: int = 80


@dataclass
class Source:
    name: str
    temperature_uK: float
    temperature_allan_uK: float
    splitter_efficiency: float
    mirror_efficiency: float
    measured_B: float
    measured_A: float
    splitter_branch: str = BRANCHES[0]
    mirror_branch: str = BRANCHES[0]
    center_offset_x_mm: float = 0.0
    center_offset_y_mm: float = 0.0
    detection_rms_mm: float = 0.0  # 0 => no effective acceptance weighting


@lru_cache(maxsize=10)
def _radial_quad(order: int) -> Tuple[np.ndarray, np.ndarray]:
    u, w = laggauss(order)
    return u, w


@lru_cache(maxsize=12)
def _normal_quad(order: int) -> Tuple[np.ndarray, np.ndarray]:
    """Normal(0,1) quadrature nodes and normalized weights."""
    z, w = hermgauss(order)
    return z * math.sqrt(2), w / math.sqrt(math.pi)


def _validate(geo: Geometry, src: Source) -> None:
    if not 1 <= geo.beam_waist_mm <= 10000:
        raise ValueError('Beam radius must be positive (1--10000 mm).')
    if geo.flight_time_ms <= geo.pulse_separation_ms:
        raise ValueError('Flight time must exceed pulse separation.')
    if geo.initial_rms_mm < 0 or geo.initial_rms_mm > 1000:
        raise ValueError('Initial cloud RMS size must be nonnegative.')
    if not 4 <= geo.quadrature_order <= 20:
        raise ValueError('4D quadrature order must be between 4 and 20.')
    if not 16 <= geo.radial_order <= 140:
        raise ValueError('Radial quadrature order must be between 16 and 140.')
    if geo.integration_mode not in ("Radial (fast, centered)", "4D trajectory (slower)"):
        raise ValueError('Unknown integration mode.')
    if geo.integration_mode.startswith("Radial") and (
       src.center_offset_x_mm != 0 or src.center_offset_y_mm != 0
       or geo.include_vertical_ballistic_shift):
        raise ValueError('Radial mode assumes centered cloud and neglects pulse-time transverse position changes. Switch to 4D trajectory to use offsets or ballistic shift.')
    if not 0 < geo.derivative_step_uK < src.temperature_uK:
        raise ValueError('Derivative step must be positive and smaller than temperature.')
    if src.temperature_uK <= 0 or src.temperature_allan_uK < 0:
        raise ValueError('Mean temperature must be positive; Allan must be nonnegative.')
    for x in [src.splitter_efficiency, src.mirror_efficiency]:
        if not (0 < x < 1):
            raise ValueError('Transfer efficiencies must be strictly between 0 and 1.')
    if src.measured_A <= 0 or src.measured_A > 1:
        raise ValueError('Measured absolute fringe amplitude must be in (0,1].')
    if not (0 <= src.measured_B <= 1):
        raise ValueError('Measured baseline must be between 0 and 1.')
    if src.detection_rms_mm < 0:
        raise ValueError('Detection acceptance RMS must be >= 0 (0: no selection).')
    if src.splitter_branch not in BRANCHES or src.mirror_branch not in BRANCHES:
        raise ValueError('Unknown pulse-area calibration branch.')


def samples(geo: Geometry, src: Source, temperature_uK: float) -> Dict[str, np.ndarray]:
    """4D Gaussian (initial x,y,vx,vy) quadrature at the three Bragg times.

    Coordinates x,y are transverse to the horizontal Bragg axis. When enabled,
    x is chosen as the vertical transverse direction, with apex at t_c.
    """
    if temperature_uK <= 0:
        raise ValueError('Temperature must be positive.')
    if geo.integration_mode.startswith('Radial'):
        u, weights = _radial_quad(geo.radial_order)
        tc = geo.flight_time_ms * 1e-3
        v_rms = math.sqrt(KB * temperature_uK * 1e-6 / M_RB87)
        sig2 = (geo.initial_rms_mm*1e-3)**2 + (v_rms*tc)**2
        r2 = 2*sig2*u
        factor = np.exp(-2*r2/(geo.beam_waist_mm*1e-3)**2)
        weights = weights.copy()
        if src.detection_rms_mm > 0:
            sdet = src.detection_rms_mm*1e-3
            weights *= np.exp(-r2/(2*sdet*sdet))
        weights /= weights.sum()
        return {'factors':np.stack([factor,factor,factor]),
                'weights':weights, 'sigma_v_mm_s':v_rms*1e3,
                'sigma_r_apex_mm':math.sqrt(sig2)*1e3}

    order = geo.quadrature_order
    z, w = _normal_quad(order)
    # Collapse the initial-position integral when its width is exactly zero.
    if geo.initial_rms_mm == 0:
        z0, w0 = np.array([0.0]), np.array([1.0])
    else:
        z0, w0 = z, w
    X0, Y0, VX, VY = np.meshgrid(z0, z0, z, z, indexing='ij')
    W0x, W0y, Wvx, Wvy = np.meshgrid(w0, w0, w, w, indexing='ij')
    weights = (W0x * W0y * Wvx * Wvy).ravel().astype(float)
    x0 = (X0.ravel() * geo.initial_rms_mm * 1e-3)
    y0 = (Y0.ravel() * geo.initial_rms_mm * 1e-3)
    v_rms = math.sqrt(KB * temperature_uK * 1e-6 / M_RB87)
    vx = VX.ravel() * v_rms
    vy = VY.ravel() * v_rms

    tc = geo.flight_time_ms * 1e-3
    sep = geo.pulse_separation_ms * 1e-3
    t_pulses = (tc-sep, tc, tc+sep)
    w_m = geo.beam_waist_mm*1e-3
    cx = src.center_offset_x_mm*1e-3
    cy = src.center_offset_y_mm*1e-3
    offsets = []
    for t in t_pulses:
        ballistic = -0.5*G0*(t-tc)**2 if geo.include_vertical_ballistic_shift else 0.0
        x = x0+vx*t -cx+ballistic
        y = y0+vy*t -cy
        # Effective Bragg coupling proportional to product of field amplitudes;
        # for identical overlapping Gaussian counterpropagating beams this is
        # exp(-2r^2/w^2) (the normalized optical intensity of one beam).
        offsets.append(np.exp(-2*(x*x+y*y)/(w_m*w_m)))
    factors = np.stack(offsets, axis=0)

    # Optional effective spatial acceptance: represents relative detection
    # weighting near middle pulse, NOT the physical detector 0.804s later.
    if src.detection_rms_mm > 0:
        sdet = src.detection_rms_mm*1e-3
        x_det = x0+vx*tc-cx
        y_det = y0+vy*tc-cy
        weights *= np.exp(-0.5*(x_det*x_det+y_det*y_det)/(sdet*sdet))
    weights /= weights.sum()
    return {'factors': factors, 'weights': weights, 'sigma_v_mm_s': v_rms*1e3,
            'sigma_r_apex_mm': math.sqrt((geo.initial_rms_mm)**2+(v_rms*tc*1e3)**2)}


def average_transition(theta: float, intensity: np.ndarray, weight: np.ndarray) -> float:
    return float(np.dot(weight, np.sin(0.5*theta*intensity)**2))


def _all_roots(func, target: float, theta_max: float = 8*math.pi) -> List[float]:
    grid = np.linspace(1e-9, theta_max, 2001)
    vals = np.array([func(float(t)) - target for t in grid])
    roots = []
    for i in range(len(grid)-1):
        if vals[i] == 0:
            roots.append(float(grid[i]))
        if vals[i]*vals[i+1] < 0:
            roots.append(float(brentq(lambda t: func(t)-target, grid[i], grid[i+1], xtol=1e-11)))
    return roots


def _select_root(roots: List[float], branch: str, kind: str, target: float) -> float:
    tol = 1e-8
    if branch == BRANCHES[0]:
        candidates = roots
    elif branch == BRANCHES[1]:
        candidates = [v for v in roots if v > math.pi/2-tol]
    elif branch == BRANCHES[2]:
        candidates = [v for v in roots if math.pi-tol < v < 2*math.pi+tol]
    elif branch == BRANCHES[3]:
        candidates = [v for v in roots if 2*math.pi-tol < v < 3*math.pi+tol]
    else:
        candidates = [v for v in roots if 3*math.pi-tol < v < 4*math.pi+tol]
    if not candidates:
        alltext = ', '.join(f'{v/math.pi:.3f}pi' for v in roots[:12]) or '(none)'
        raise ValueError(
            f'{kind}: target efficiency {target:.1%} is not reachable on selected '
            f'branch "{branch}". Available solutions: {alltext}. '
            'Change branch, geometry, acceptance, or target efficiency.'
        )
    return float(min(candidates))


def calibrate(geo: Geometry, src: Source) -> Dict[str, object]:
    """Find per-source on-axis pulse areas at the *nominal* temperature."""
    _validate(geo, src)
    cloud = samples(geo, src, src.temperature_uK)
    f = cloud['factors']
    weights = cloud['weights']
    # Same nominal splitter peak area for first and final pulses.
    split_fn = lambda theta: 0.5*(
        average_transition(theta, f[0], weights)
        +average_transition(theta, f[2], weights)
    )
    mirror_fn = lambda theta: average_transition(theta, f[1], weights)
    split_roots = _all_roots(split_fn, src.splitter_efficiency)
    mirror_roots = _all_roots(mirror_fn, src.mirror_efficiency)
    theta_s = _select_root(split_roots, src.splitter_branch, 'splitter', src.splitter_efficiency)
    theta_m = _select_root(mirror_roots, src.mirror_branch, 'mirror', src.mirror_efficiency)
    return {
        'theta_s': theta_s,
        'theta_m': theta_m,
        'p1_nom': average_transition(theta_s, f[0], weights),
        'p2_nom': average_transition(theta_m, f[1], weights),
        'p3_nom': average_transition(theta_s, f[2], weights),
        'sample_count': weights.size,
        'cloud': cloud,
    }


def evaluate(geo: Geometry, src: Source, theta_s: float, theta_m: float,
             temperature_uK: float) -> Dict[str,float]:
    """Compute B(T), A(T), pulse efficiencies; no calibration at T."""
    cloud = samples(geo, src, temperature_uK)
    f = cloud['factors']
    weights = cloud['weights']
    a = np.sin(0.5*theta_s*f[0])**2
    b = np.sin(0.5*theta_m*f[1])**2
    c = np.sin(0.5*theta_s*f[2])**2
    B_atom = b + (a+c-2*a*c)*(1-2*b)
    A_atom = 2*b*np.sqrt(np.clip(a*(1-a)*c*(1-c),0,None))
    return {
        'B': float(np.dot(weights, B_atom)),
        'A': float(np.dot(weights, A_atom)),
        'splitter_first': float(np.dot(weights,a)),
        'mirror': float(np.dot(weights,b)),
        'splitter_last': float(np.dot(weights,c)),
        'sigma_v_mm_s': float(cloud['sigma_v_mm_s']),
        'sigma_r_apex_mm': float(cloud['sigma_r_apex_mm']),
    }


def analyze_source(geo: Geometry, src: Source, build_scan: bool=True) -> Dict[str, object]:
    cal = calibrate(geo, src)
    th_s,th_m=cal['theta_s'],cal['theta_m']
    T=src.temperature_uK
    h=geo.derivative_step_uK
    nom=evaluate(geo,src,th_s,th_m,T)
    plus=evaluate(geo,src,th_s,th_m,T+h)
    minus=evaluate(geo,src,th_s,th_m,T-h)
    kh_B=(plus['B']-minus['B'])/(2*h)
    kh_A=(plus['A']-minus['A'])/(2*h)
    half=evaluate(geo,src,th_s,th_m,T+h/2)
    halfm=evaluate(geo,src,th_s,th_m,T-h/2)
    kh_B_half=(half['B']-halfm['B'])/h
    sigma_B=abs(kh_B)*src.temperature_allan_uK
    sigma_mrad=1000*sigma_B/src.measured_A
    measured_B_mismatch=nom['B']-src.measured_B
    measured_A_mismatch=nom['A']-src.measured_A
    warnings=[]
    if abs(measured_B_mismatch)>0.025 or abs(measured_A_mismatch)>0.025:
        warnings.append('The two-state model does NOT reproduce measured B/A: K_T is scenario-dependent.')
    if not (th_s <= math.pi):
        warnings.append('Splitter center pulse is past first Rabi maximum (theta_s>pi).')
    elif th_s > math.pi/2:
        warnings.append('Splitter center pulse is over pi/2 (as requested for MIGA21).')
    if src.measured_A > src.mirror_efficiency/2+1e-8:
        warnings.append('A_measured > <p_mirror>/2 violates simple closed-path bound if same normalized ensemble.')
    if abs(kh_B-kh_B_half)>max(0.001*abs(kh_B_half),1e-5):
        warnings.append('Finite-difference derivatives differ noticeably between h and h/2.')
    if geo.integration_mode.startswith('4D') and geo.quadrature_order < 14:
        warnings.append('4D quadrature below order 14 can be inaccurate; check order convergence.')
    if src.temperature_allan_uK > 0.1*T:
        warnings.append('Temperature Allan >10% of mean; linear propagation may be inaccurate.')
    result={
        'source':asdict(src),
        'calibration':{'splitter_area_rad':th_s,'mirror_area_rad':th_m,
                       'splitter_area_pi':th_s/math.pi,'mirror_area_pi':th_m/math.pi,
                       'efficiency_p1':cal['p1_nom'],
                       'efficiency_p2':cal['p2_nom'],
                       'efficiency_p3':cal['p3_nom'],
                       'sample_count':cal['sample_count']},
        'nominal':nom,
        'derivatives':{'K_B_per_uK':kh_B,'K_A_per_uK':kh_A,
                       'K_B_halfstep_per_uK':kh_B_half},
        'allan':{'baseline_population':sigma_B,
                 'apparent_phase_mrad':sigma_mrad,
                 'signed_apparent_sensitivity_mrad_per_uK':-1000*kh_B/src.measured_A},
        'model_mismatch':{'B':measured_B_mismatch,'A':measured_A_mismatch},
        'warnings':warnings
    }
    if build_scan:
        window=max(0.06,3*src.temperature_allan_uK)
        temps=np.linspace(max(0.05,T-window),T+window,51)
        scan=[evaluate(geo,src,th_s,th_m,float(temp)) for temp in temps]
        result['scan']={
            'temperature_uK':temps.tolist(),
            'B': [d['B'] for d in scan],
            'A': [d['A'] for d in scan],
            'splitter_eff': [(d['splitter_first']+d['splitter_last'])/2 for d in scan],
            'mirror_eff':[d['mirror'] for d in scan]
        }
    return result


def analyze_pair(geo: Geometry, s22: Source, s21: Source, build_scan=True) -> Dict[str,object]:
    results={s22.name:analyze_source(geo,s22,build_scan),s21.name:analyze_source(geo,s21,build_scan)}
    if s22.name==s21.name:
        raise ValueError('Source names must be different.')
    # Independence is a physically explicit assumption, not inherent in code.
    diff=math.sqrt(sum(r['allan']['apparent_phase_mrad']**2 for r in results.values()))
    return {'model':'Resonant two-momentum-state, closed MZ paths, Gaussian transverse ensemble',
            'geometry':asdict(geo),
            'sources':results,
            'differential':{'temperature_baseline_phase_allan_mrad':diff,
                'temperature_noise_correlation':0.0,
                'assumption':'Independent atom-source temperature noise, same Allan averaging interval'},
            'limitations':[
                'Only population baseline variation, not true quasi-Bragg diffraction phase',
                'Measured efficiencies used for one-time calibration at mean temperature',
                'On-axis splitter and mirror areas calibrated independently for each source',
                'Radial mode uses the same transverse position at all three pulses',
                'Pulse area approximates Blackman only in resonant two-state limit',
                'No axial Doppler detuning, higher diffraction orders, or detailed readout acceptance',
                'Model B/A mismatch means derivatives are conditional, not validated physics budget',
                'Allan propagation is first-order, appropriate at the specified averaging time',
            ]}


def default_sources() -> Tuple[Source, Source]:
    return (
        Source('MIGA22',2.599,0.151,0.20,0.40,0.2905,0.175),
        Source('MIGA21',1.869,0.109,0.20,0.40,0.4165,0.210,
               splitter_branch=BRANCHES[1]),
    )



@dataclass
class LaunchSettings:
    """Launch scenario, SI geometry; 0 middle_pulse_ms uses each nominal apex."""
    gravity_m_s2: float = 9.81
    detection_height_m: float = 0.275
    middle_pulse_ms: float = 0.0
    velocity_step_mm_s: float = 0.02
    quadrature_order: int = 48
    comparison_order: int = 64
    wavefront_enabled: bool = False
    wavelength_nm: float = 780.0
    fringe_slope_sign: int = 1


@dataclass
class LaunchSource:
    detection_time_s: float
    detection_allan_us: float
    vertical_offset_mm: float = 0.0
    wavefront_radius_m: float = 200.0  # signed effective two-photon radius; 0 = plane wave


def launch_kinematics(cfg: LaunchSettings, inp: LaunchSource, separation_ms: float):
    g, td, zd = cfg.gravity_m_s2, inp.detection_time_s, cfg.detection_height_m
    if not all(math.isfinite(x) for x in (g, td, zd, inp.detection_allan_us, separation_ms, cfg.middle_pulse_ms)) or g <= 0 or td <= 0 or inp.detection_allan_us < 0 or separation_ms <= 0:
        raise ValueError('Gravity, detection time and pulse separation must be positive; arrival-time Allan must be nonnegative.')
    v = zd/td + g*td/2
    apex = v/g
    if v <= 0 or td <= apex:
        raise ValueError('The specified detection time must be on the descending trajectory.')
    dvdt = g/2-zd/td**2
    sigma_v = abs(dvdt)*inp.detection_allan_us*1e-6
    t2 = apex if cfg.middle_pulse_ms == 0 else cfg.middle_pulse_ms*1e-3
    ts = np.array([t2-separation_ms*1e-3, t2, t2+separation_ms*1e-3])
    if ts[0] <= 0:
        raise ValueError('All Bragg pulse times must be after launch.')
    return {'velocity_m_s':v, 'velocity_allan_m_s':sigma_v,
            'dv_dt_m_s2':dvdt, 'apex_time_s':apex, 'apex_height_m':v*v/(2*g),
            'apex_height_allan_m':apex*sigma_v,
            'pulse_times_s':ts.tolist(), 'pulse_position_allan_m':(ts*sigma_v).tolist()}


def _launch_cloud(geo, src, cfg, inp, kin, velocity_delta_m_s=0.0, offset_delta_mm=0.0, order=None):
    """4D joint Gaussian integrated via middle-position/thermal-velocity coordinates.

    The acceptance is fixed in laboratory coordinates at the nominal middle
    cloud center, independent of beam offset and held fixed under perturbation.
    """
    n = cfg.quadrature_order if order is None else order
    z, w = _normal_quad(n)
    # The residual thermal velocity is narrow near the middle pulse; use a
    # separate quadrature order while retaining the exact covariance.
    zv, wv = _normal_quad(min(10, max(4, (n+7)//8)))
    p, q, yp, yq = np.meshgrid(z,zv,z,zv,indexing='ij')
    wp,wq,wy,wyq = np.meshgrid(w,wv,w,wv,indexing='ij')
    weights=(wp*wq*wy*wyq).ravel()
    t2=kin['pulse_times_s'][1]
    sv=math.sqrt(KB*src.temperature_uK*1e-6/M_RB87)
    s0=geo.initial_rms_mm*1e-3
    sm=math.sqrt(s0*s0+(sv*t2)**2)
    cov=sv*sv*t2
    residual=math.sqrt(max(0.0,sv*sv-cov*cov/(sm*sm)))
    xc=(sm*p).ravel(); yc=(sm*yp).ravel()
    vx=(cov/sm*p+residual*q).ravel(); vy=(cov/sm*yp+residual*yq).ravel()
    if src.detection_rms_mm > 0:
        scale=src.detection_rms_mm*1e-3
        weights=weights*np.exp(-((xc+t2*velocity_delta_m_s)**2+yc*yc)/(2*scale*scale))
    norm=weights.sum()
    if not np.isfinite(norm) or norm <= 0: raise ValueError('Detection acceptance gives zero integration weight.')
    weights=weights/norm
    v=kin['velocity_m_s']; g=cfg.gravity_m_s2
    z2=v*t2-g*t2*t2/2
    beam_z=z2-inp.vertical_offset_mm*1e-3-offset_delta_mm*1e-3
    beam_y=src.center_offset_y_mm*1e-3
    factors=[]
    for t in kin['pulse_times_s']:
        zmean=(v+velocity_delta_m_s)*t-g*t*t/2
        xx=xc+vx*(t-t2)+zmean-beam_z
        yy=yc+vy*(t-t2)-beam_y
        factors.append(np.exp(-2*(xx*xx+yy*yy)/(geo.beam_waist_mm*1e-3)**2))
    return np.array(factors), weights


def _launch_evaluate(factors, weights, theta_s, theta_m):
    a=np.sin(theta_s*factors[0]/2)**2
    b=np.sin(theta_m*factors[1]/2)**2
    c=np.sin(theta_s*factors[2]/2)**2
    avg=lambda x: float(np.sum(weights*x))
    return {'B':avg(b+(a+c-2*a*c)*(1-2*b)),
            'A':avg(2*b*np.sqrt(np.clip(a*(1-a)*c*(1-c),0,None))),
            'p1':avg(a),'p2':avg(b),'p3':avg(c)}


def _launch_calibrate(f, w, src):
    # Locate all branches up to 8π, as in the existing pulse-area model.
    def roots(kind,target):
        def fun(t):
            if kind=='splitter':
                return float(np.sum(w*(np.sin(t*f[0]/2)**2+np.sin(t*f[2]/2)**2)*0.5))-target
            return float(np.sum(w*np.sin(t*f[1]/2)**2))-target
        grid=np.linspace(1e-9,8*math.pi,401)
        values=[fun(t) for t in grid]
        return [float(brentq(fun,a,b,xtol=1e-11)) for a,b,fa,fb in zip(grid[:-1],grid[1:],values[:-1],values[1:]) if fa*fb<0]
    split=_select_root(roots('splitter',src.splitter_efficiency),src.splitter_branch,'splitter',src.splitter_efficiency)
    mirror=_select_root(roots('mirror',src.mirror_efficiency),src.mirror_branch,'mirror',src.mirror_efficiency)
    return split,mirror


def launch_wavefront_sensitivity(cfg, inp, kin):
    """Center-trajectory effective quadratic wavefront response, rad/(m/s).

    This is a separate point-cloud approximation, not ensemble-weighted fringe
    phase; its coherent combination with baseline is conditional on that model.
    """
    if not cfg.wavefront_enabled or inp.wavefront_radius_m == 0: return 0.0
    ts=np.array(kin['pulse_times_s']); v=kin['velocity_m_s']; g=cfg.gravity_m_s2
    z=v*ts-g*ts**2/2
    zc=z[1]-inp.vertical_offset_mm*1e-3
    k=4*math.pi/(cfg.wavelength_nm*1e-9)
    return float(k/inp.wavefront_radius_m*np.dot([1,-2,1],(z-zc)*ts))


def analyze_launch_source(geo, src, cfg, inp, build_scan=True):
    from dataclasses import replace
    # Reuse existing model input checks; launch uses a dedicated 4D integrator.
    _validate(replace(geo,integration_mode='4D trajectory (slower)'),src)
    vals=(cfg.velocity_step_mm_s,cfg.wavelength_nm,inp.vertical_offset_mm,inp.wavefront_radius_m)
    if not all(math.isfinite(x) for x in vals) or cfg.velocity_step_mm_s <= 0 or cfg.wavelength_nm <= 0:
        raise ValueError('Velocity step and wavelength must be finite and positive; offsets and radii must be finite.')
    if cfg.fringe_slope_sign not in (-1,1) or not (8<=cfg.quadrature_order<=80 and 8<=cfg.comparison_order<=80) or cfg.comparison_order==cfg.quadrature_order:
        raise ValueError('Use distinct launch quadrature orders between 8 and 80, and fringe slope sign +1 or -1.')
    kin=launch_kinematics(cfg,inp,geo.pulse_separation_ms)
    h=cfg.velocity_step_mm_s*1e-3
    def compute(order):
        f,w=_launch_cloud(geo,src,cfg,inp,kin,order=order)
        ths,thm=_launch_calibrate(f,w,src)
        nominal=_launch_evaluate(f,w,ths,thm)
        def at(dv=0.0, dd=0.0):
            a,b=_launch_cloud(geo,src,cfg,inp,kin,velocity_delta_m_s=dv,offset_delta_mm=dd,order=order)
            return _launch_evaluate(a,b,ths,thm)
        def derivative(step, dd=0):return (at(step,dd)['B']-at(-step,dd)['B'])/(2*step)
        return ths,thm,nominal,derivative(h),derivative(h/2),at,derivative
    ths,thm,nom,kb,khalf,at,derivative=compute(cfg.quadrature_order)
    _,_,nom_hi,khi,_,_,_=compute(cfg.comparison_order)
    sv=kin['velocity_allan_m_s']; kbase=-cfg.fringe_slope_sign*kb/src.measured_A
    kwf=launch_wavefront_sensitivity(cfg,inp,kin); ktot=kbase+kwf
    warn=[]
    if abs(nom['B']-src.measured_B)>0.025 or abs(nom['A']-src.measured_A)>0.025:
        warn.append('Model B/A differs from measured values; result is a conditional scenario.')
    if src.measured_A > src.mirror_efficiency/2+1e-8:
        warn.append('Measured A exceeds mirror efficiency / 2: simple closed-path bound may be violated for the same ensemble.')
    if abs(kb-khalf)>max(abs(khalf)*0.01, 0.01):warn.append('Velocity finite-difference h versus h/2 did not converge to 1%.')
    if abs(kb-khi)>max(abs(khi)*0.05,0.001) or abs(nom['B']-nom_hi['B'])>0.001 or abs(nom['A']-nom_hi['A'])>0.001:
        warn.append('Quadrature orders disagree; increase both orders and check convergence.')
    if sv > 0:
        bp=at(sv)['B']; bm=at(-sv)['B']
        even_response=abs((bp+bm)/2-nom['B'])
        linear_response=abs(kb*sv)
        if even_response > max(0.1*linear_response,1e-9):
            warn.append('Baseline response is nonlinear across one velocity Allan; first-order propagation may miss noise.')
    out={'input':asdict(inp),'kinematics':kin,'calibration':{'splitter_area_pi':ths/math.pi,'mirror_area_pi':thm/math.pi},
         'nominal':nom,'model_mismatch':{'B':nom['B']-src.measured_B,'A':nom['A']-src.measured_A},
         'sensitivity':{'K_B_per_m_s':kb,'K_B_per_mm_s':kb/1000,'K_B_per_mm':kb/kin['pulse_times_s'][1]/1000,
                        'K_B_halfstep_per_m_s':khalf,'K_B_comparison_order_per_m_s':khi,
                        'baseline_rad_per_m_s':kbase,'wavefront_rad_per_m_s':kwf,'total_rad_per_m_s':ktot},
         'allan':{'baseline_population':abs(kb)*sv,'baseline_mrad':1000*abs(kbase)*sv,
                  'wavefront_mrad':1000*abs(kwf)*sv,'total_mrad':1000*abs(ktot)*sv},'warnings':warn}
    if build_scan:
        dvs=np.linspace(-max(3*sv,3*h),max(3*sv,3*h),31)
        off=np.array([-5.,-2.,0.,2.,5.])
        # Offsets are absolute relative to beam center. Pulse areas stay fixed at the user's nominal offset.
        ob=[derivative(h,float(d-inp.vertical_offset_mm)) for d in off]
        rs=[100.,200.,500.,1000.,0.]
        # 0 denotes the plane-wave limit; these are scenario curves, not measurements.
        wf=[launch_wavefront_sensitivity(replace(cfg,wavefront_enabled=True),replace(inp,wavefront_radius_m=r),kin) for r in rs]
        out['scan']={'velocity_delta_mm_s':(dvs*1000).tolist(),'velocity_B':[at(float(d))['B'] for d in dvs],
                     'offset_mm':off.tolist(),'offset_K_B_per_mm':[float(k/kin['pulse_times_s'][1]/1000) for k in ob],
                     'offset_baseline_mrad':[float(1000*abs(k/src.measured_A)*sv) for k in ob],
                     'radius_m':rs,'radius_wavefront_mrad':[float(1000*abs(k)*sv) for k in wf],
                     'radius_total_mrad':[float(1000*abs(kbase+k)*sv) for k in wf]}
    return out


def analyze_launch_pair(geo, s22, s21, cfg, input22, input21, build_scan=True):
    if s22.name==s21.name: raise ValueError('Source names must be different.')
    r22=analyze_launch_source(geo,s22,cfg,input22,build_scan)
    r21=analyze_launch_source(geo,s21,cfg,input21,build_scan)
    diff={key: math.hypot(r22['allan'][key],r21['allan'][key]) for key in ('baseline_mrad','wavefront_mrad','total_mrad')}
    diff['middle_position_mm']=1000*math.hypot(r22['kinematics']['pulse_position_allan_m'][1],r21['kinematics']['pulse_position_allan_m'][1])
    return {'model':'Conditional resonant two-state; 4D Gaussian trajectories; quadratic center-trajectory effective wavefront',
            'geometry':asdict(geo),'settings':asdict(cfg),'sources':{s22.name:r22,s21.name:r21},'differential':diff,
            'assumptions':['Detection timing is attributed solely to launch velocity; launch height and detector jitter are neglected.',
               'Sources are independent at the same Allan averaging time; within one source all three pulse displacements are correlated.',
               'Pulse areas and laboratory pulse times are fixed during velocity and offset scans.',
               'Quadratic wavefront is a separate center-trajectory approximation; its radius is an effective assumed two-photon parameter, not measured.',
               'The signed baseline sensitivity uses delta_phi = -delta_B/(fringe_slope_sign*A_measured).',
               'No multiport diffraction phase, axial Doppler, wavefront aberrations, or temperature/launch covariance.']}

if __name__=='__main__':
    geo=Geometry()
    s22,s21=default_sources()
    result=analyze_pair(geo,s22,s21)
    for name,r in result['sources'].items():
        print(name, 'theta_s/pi',round(r['calibration']['splitter_area_pi'],3),
              'B_model',round(r['nominal']['B'],4),
              'A_model',round(r['nominal']['A'],4),
              'K_B/uK',round(r['derivatives']['K_B_per_uK'],5),
              'sigma_app_mrad',round(r['allan']['apparent_phase_mrad'],3))
    print('Differential [mrad]:',round(result['differential']['temperature_baseline_phase_allan_mrad'],3))
