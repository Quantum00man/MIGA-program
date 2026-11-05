"""Minimal multi-momentum, single-frequency standing-wave Bragg Mach-Zehnder.

Install: pip install numpy scipy matplotlib
Run: python quasi_bragg_sim.py

Conventions:
 p_n=(2*n+1)*hbar*k + M*dv, n=-N,...,N;
 initial |+hbar*k> = |n=0>, detected |-hbar*k> = |n=-1>.
 kinetic phases are retained. The standing-wave coupling between adjacent n
 is hbar*omega(t)*exp(i*phi), with lattice spatial phase phi.
 Bragg lattice is stationary (frequency difference zero); additional dv models
 imperfect velocity preparation. The two free propagations include optional
 linear potential as a momentum-independent acceleration in an approximate
 interaction picture only if explicitly implemented later; none here.

Each Gaussian pulse is truncated at +/-4 sigma and the free evolution is from
 the END of one pulse to START of the next, as defined by the program.
"""
from pathlib import Path
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq
import matplotlib.pyplot as plt

K = 2*np.pi/780e-9
RECOIL_HZ = 3770.0
WR = 2*np.pi*RECOIL_HZ
N=5
n=np.arange(-N,N+1)
IDX0=np.where(n==0)[0][0]
IDXM=np.where(n==-1)[0][0]


def pulse_matrix(sigma_us, omega_r, nsteps_note=None):
    """Unitary for a Gaussian pulse with peak nearest-neighbor coupling omega_r * wr."""
    sigma=sigma_us*1e-6
    energies=(2*n+1)**2*WR
    low=np.diag(np.ones(len(n)-1),k=-1)
    high=low.T
    hop=low+high
    def rhs(t,Y):
        Y=Y.reshape((len(n),len(n)))
        H=np.diag(energies)+omega_r*WR*np.exp(-0.5*(t/sigma)**2)*hop
        return (-1j*H@Y).ravel()
    sol=solve_ivp(rhs, (-4*sigma,4*sigma),np.eye(len(n),dtype=complex).ravel(),
                  method='DOP853',rtol=2e-9,atol=1e-11)
    if not sol.success: raise RuntimeError(sol.message)
    return sol.y[:,-1].reshape((len(n),len(n)))


def phase_shift(U, phi):
    # The optical phase is applied to the standing-wave potential only.
    D=np.exp(1j*n*phi)
    return D[:,None]*U*np.conj(D)[None,:]


def free_matrix(T_us):
    return np.exp(-1j*(2*n+1)**2*WR*T_us*1e-6)


def output_pops(U1,U2,U3,T_us,phis):
    init=np.zeros(len(n),complex); init[IDX0]=1
    f=free_matrix(T_us)
    pre=f*(U2@(f*(U1@init)))
    ps=[]; wholes=[]
    for phi in phis:
        out=phase_shift(U3,phi)@pre
        ps.append(abs(out[IDXM])**2)
        wholes.append(abs(out)**2)
    return np.array(ps),np.array(wholes)


def first_harmonic_fit(phis,P):
    # Detect harmonics; return arg Z for P = offset + A cos(phi+phase).
    X=np.column_stack([np.ones_like(phis),np.cos(phis),np.sin(phis)])
    offset,C,S=np.linalg.lstsq(X,P,rcond=None)[0]
    amp=np.hypot(C,S)
    phase=np.arctan2(-S,C)
    residual=P-X@np.array([offset,C,S])
    rms=np.sqrt(np.mean(residual**2))
    return offset,amp,phase,rms


def main():
    outdir=Path(__file__).resolve().parent
    sigma=12.0 # microseconds; adjust to experimental pulse FWHM using FWHM=2.355 sigma
    T=1000.0  # microseconds, between pulse edges (approximate)
    # Choose a pi/2-like pulse by scanning peak depth for a population transfer ~ 0.5.
    def objective(r):
        U=pulse_matrix(sigma,r)
        return abs(U[IDXM,IDX0])**2-0.5
    rates=np.linspace(0.01,1.8,45)
    vals=[objective(r) for r in rates]
    brackets=[(rates[j],rates[j+1]) for j in range(len(vals)-1) if vals[j]*vals[j+1]<0]
    if not brackets:
        peak=rates[int(np.argmin(np.abs(vals)))]; print('No exact 50/50 root found; using near value')
    else: peak=brentq(objective,*brackets[0],xtol=1e-7)
    U1=pulse_matrix(sigma,peak)
    # A provisional mirror: double Gaussian sigma at same optical depth, to have double pulse area.
    U2=pulse_matrix(2*sigma,peak)
    U3=U1
    phis=np.linspace(0,2*np.pi,201)
    P,allp=output_pops(U1,U2,U3,T,phis)
    fit=first_harmonic_fit(phis,P)
    leak1=1-abs(U1[IDX0,IDX0])**2-abs(U1[IDXM,IDX0])**2
    print(f'sigma={sigma:.2f} us, FWHM={2.355*sigma:.2f} us, T={T:.1f} us, peak Omega/omega_r={peak:.4f}')
    print(f'after first splitter: P(+hk)={abs(U1[IDX0,IDX0])**2:.4f}, P(-hk)={abs(U1[IDXM,IDX0])**2:.4f}, leakage={leak1:.4f}')
    print(f'fringe offset={fit[0]:.4f}, amplitude={fit[1]:.4f}, fit phase={fit[2]:.4f} rad, non-sinusoidal RMS={fit[3]:.5f}')
    print('P at phi3=0, momentum ladder:',dict(zip([f'{2*j+1:+d} hk' for j in n],np.round(allp[0],4))))
    fig,axs=plt.subplots(1,2,figsize=(11,4))
    axs[0].bar(2*n+1,abs(U1[:,IDX0])**2,width=1.3)
    axs[0].set(xlabel='momentum / (hbar k)',ylabel='population',title='After first Gaussian Bragg splitter')
    axs[0].set_xticks(2*n+1)
    axs[1].plot(phis,P,label='Multiport output')
    axs[1].plot(phis,fit[0]+fit[1]*np.cos(phis+fit[2]),'--',label='First-harmonic fit')
    axs[1].set(xlabel='Last pulse phase (rad)',ylabel='P(-hbar k)',title='Mach-Zehnder readout')
    axs[1].legend(); fig.tight_layout()
    fig.savefig(outdir/'quasi_bragg_baseline.png',dpi=175)
    plt.close(fig)
    np.savez(outdir/'quasi_bragg_baseline.npz',n=n,phis=phis,P=P,allp=allp,U1=U1,U2=U2,U3=U3,sigma_us=sigma,T_us=T,omega_r=peak)

if __name__=='__main__': main()
