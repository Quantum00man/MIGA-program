"""Sweep gaussian splitter width at 50:50 target, evaluate multiport losses and readout."""
import numpy as np
from scipy.optimize import brentq
import matplotlib.pyplot as plt
from pathlib import Path
from quasi_bragg_sim import pulse_matrix, output_pops, first_harmonic_fit, IDX0, IDXM

outdir=Path(__file__).resolve().parent
T=1000.
phis=np.linspace(0,2*np.pi,101)
rows=[]
fringes={}
for sigma in [7.0,7.5,8.0,10.0,12.0]:
    def objective(r): return abs(pulse_matrix(sigma,r)[IDXM,IDX0])**2-.5
    rates=np.linspace(.1,3.0,21)
    vals=[objective(q) for q in rates]
    brackets=[(rates[i],rates[i+1]) for i in range(len(vals)-1) if vals[i]*vals[i+1]<0]
    if not brackets:
        rows.append([sigma,np.nan,np.nan,np.nan,np.nan,np.nan,np.nan]);continue
    r=brentq(objective,*brackets[0])
    U1=pulse_matrix(sigma,r)
    U2=pulse_matrix(2*sigma,r)
    P,_=output_pops(U1,U2,U1,T,phis)
    fit=first_harmonic_fit(phis,P)
    leak=1-abs(U1[IDXM,IDX0])**2-abs(U1[IDX0,IDX0])**2
    phase_bias=np.angle(np.exp(1j*(fit[2]+np.pi)))
    rows.append([sigma,r,leak,fit[0],fit[1],phase_bias,fit[3]])
    fringes[sigma]=P
arr=np.array(rows)
print(' sigma_us  omega/wr  leak  offset amplitude phase_bias_rad fit_residual')
for row in arr: print(' '.join(f'{v:11.5f}' for v in row))
fig,axs=plt.subplots(1,2,figsize=(11,4))
axs[0].plot(arr[:,0]*2.35482,arr[:,2]*100,'o-')
axs[0].axhline(10,ls='--',alpha=.6)
axs[0].set(xlabel='Splitter Gaussian FWHM (us)',ylabel='Other momentum populations (%)',title='Multiport loss after splitter')
for sigma in [7.,7.5,8.,12.]:
 if sigma in fringes: axs[1].plot(phis,fringes[sigma],label=f'FWHM {2.355*sigma:.1f} us')
axs[1].set(xlabel='Third Bragg pulse phase (rad)',ylabel='P(-hbar k)',title='Detected fringe vs pulse duration')
axs[1].legend();fig.tight_layout();fig.savefig(outdir/'quasi_bragg_pulse_scan.png',dpi=175)
np.savetxt(outdir/'quasi_bragg_pulse_scan.csv',arr,delimiter=',',header='sigma_us,omega_over_wr,leak_after_splitter,fringe_offset,fringe_amplitude,phase_bias_rad,fit_residual',comments='')
