# Bragg Interferometer Simulation Formula Reference

## 1. Scope Of The Model

This document describes the exact effective model implemented by the GUI-based Bragg atom-interferometer simulator used in this project. The model is designed for:

- fringe prediction,
- noise budgeting,
- sensitivity studies,
- parameter scans over pulse quality and technical noise.

It is not a full momentum-lattice propagation model. Instead, it keeps only an effective two-port interferometer subspace and treats imperfect Bragg diffraction through effective transfer probabilities, loss terms, and diffraction phases.

## 2. Simulation Workflow

The calculation proceeds in the following order:

1. Define the interferometer geometry and the pulse sequence parameters.
2. Build the laser-frequency-noise and mirror-acceleration-noise spectra.
3. Convert these technical noise spectra into interferometer phase-noise spectra.
4. Integrate the phase-noise spectra through the interferometer transfer function to obtain RMS phase noise.
5. Build one effective complex matrix for each Bragg pulse.
6. Propagate the initial state through the `pi/2 - pi - pi/2` sequence.
7. Compute upper-port and lower-port populations for each Monte Carlo shot.
8. Repeat the calculation over a scanned optical phase and average the shots.
9. Fit the resulting fringe with a cosine model.

Each step is written explicitly below.

## 3. Interferometer Parameters

The interferometer-level parameters are:

- `n`: Bragg order.
- `lambda`: laser wavelength.
- `T`: pulse separation between the first and second pulse, and between the second and third pulse.
- `a_eff`: effective acceleration projected along the interferometer axis.
- `phi_offset`: additional static phase offset.
- `phi0`: scanned optical phase.

These are entered in the GUI as:

- `Bragg order`
- `Wavelength`
- `Pulse separation T`
- `Effective acceleration`
- `Additional phase offset`

## 4. Effective Wavevector

The single-photon wavevector magnitude is

\[
k = \frac{2 \pi}{\lambda}.
\]

The effective Bragg interferometer wavevector is

\[
k_{\mathrm{eff}} = 2 n k = 2 n \frac{2 \pi}{\lambda}.
\]

Parameter meanings:

- `k`: single-photon wavevector magnitude.
- `k_eff`: effective two-photon Bragg wavevector used in the interferometer phase.
- `n`: Bragg order.
- `lambda`: wavelength.

## 5. Deterministic Interferometer Phase

The effective deterministic phase used in the model is

\[
\phi_{\mathrm{base}} = k_{\mathrm{eff}} a_{\mathrm{eff}} T^2 + \phi_{\mathrm{offset}}.
\]

The scanned optical phase enters as

\[
\phi_{\mathrm{scan}} = n \phi_0.
\]

Therefore the deterministic phase before shot-to-shot technical noise is

\[
\phi_{\mathrm{det}} = \phi_{\mathrm{base}} + \phi_{\mathrm{scan}}.
\]

Parameter meanings:

- `phi_base`: inertial plus static phase.
- `a_eff`: effective acceleration.
- `T`: pulse separation.
- `phi_offset`: additional user-defined phase offset.
- `phi0`: scanned optical phase.
- `n`: Bragg order.

## 6. Noise Spectra Input Convention

The simulator accepts noise spectra in power spectral density form.

For laser-frequency noise, the PSD unit is

\[
\mathrm{Hz}^2 / \mathrm{Hz}.
\]

For mirror acceleration noise, the PSD unit is

\[
(\mathrm{m/s}^2)^2 / \mathrm{Hz}.
\]

All dB inputs use the convention

\[
\mathrm{PSD}_{\mathrm{dB}} = 10 \log_{10}\left(\frac{S}{S_{\mathrm{ref}}}\right),
\]

with:

- `S_ref = 1 Hz^2/Hz` for laser-frequency noise,
- `S_ref = 1 (m/s^2)^2/Hz` for mirror acceleration noise.

The inverse conversion is

\[
S = 10^{\mathrm{PSD}_{\mathrm{dB}}/10}.
\]

Parameter meanings:

- `S`: linear PSD.
- `PSD_dB`: PSD written in dB.
- `S_ref`: reference PSD unit used in the dB convention.

## 7. Background Noise Model

The simulator decomposes the technical noise background into:

- a white term,
- a flicker term,
- a random-walk term,
- a sum of Lorentzian peaks.

The full PSD is modeled as

\[
S(f) = S_0 + \frac{C_1}{f} + \frac{C_2}{f^2} + \sum_i S_{\mathrm{peak},i}(f).
\]

Parameter meanings:

- `f`: Fourier frequency.
- `S0`: white PSD level.
- `C1`: flicker PSD coefficient referenced at `1 Hz`.
- `C2`: random-walk PSD coefficient referenced at `1 Hz`.
- `S_peak,i(f)`: PSD contribution of peak `i`.

### 7.1 White Term

The white-noise contribution is

\[
S_{\mathrm{white}}(f) = S_0.
\]

Parameter meanings:

- `S0`: constant PSD floor.

### 7.2 Flicker Term

The flicker-noise contribution is

\[
S_{\mathrm{flicker}}(f) = \frac{C_1}{f}.
\]

Parameter meanings:

- `C1`: PSD coefficient equal to the flicker PSD at `f = 1 Hz`.
- `f`: Fourier frequency.

### 7.3 Random-Walk Term

The random-walk contribution is

\[
S_{\mathrm{rw}}(f) = \frac{C_2}{f^2}.
\]

Parameter meanings:

- `C2`: PSD coefficient equal to the random-walk PSD at `f = 1 Hz`.
- `f`: Fourier frequency.

## 8. Lorentzian Peak Model

Each narrow-band peak is modeled by a Lorentzian PSD:

\[
S_{\mathrm{peak}}(f) =
\frac{S_{\mathrm{peak,center}}}
{1 + \left(\frac{f - f_0}{\Gamma}\right)^2}.
\]

Parameter meanings:

- `S_peak,center`: peak-center PSD in linear units.
- `f0`: center frequency of the peak.
- `Gamma`: width parameter of the Lorentzian.
- `f`: Fourier frequency.

In the GUI, `S_peak,center` is entered as `psd_db`, and the simulator converts it back to linear PSD through

\[
S_{\mathrm{peak,center}} = 10^{\mathrm{psd\_db}/10}.
\]

## 9. Total ASD Used Internally

The simulator computes the total linear PSD first:

\[
S_{\mathrm{total}}(f)
=
S_0
+ \frac{C_1}{f}
+ \frac{C_2}{f^2}
+ \sum_i S_{\mathrm{peak},i}(f).
\]

The amplitude spectral density used internally is then

\[
\mathrm{ASD}_{\mathrm{total}}(f) = \sqrt{S_{\mathrm{total}}(f)}.
\]

Parameter meanings:

- `S_total(f)`: total linear PSD.
- `ASD_total(f)`: total amplitude spectral density.

## 10. Laser-Frequency Noise To Phase Noise

Let `S_nu(f)` be the laser-frequency-noise PSD. The simulator constructs the interferometer phase-noise PSD as

\[
S_{\phi,\mathrm{laser}}(f) = \frac{n^2 S_{\nu}(f)}{f^2}.
\]

Parameter meanings:

- `S_phi,laser(f)`: interferometer phase-noise PSD arising from laser frequency noise.
- `S_nu(f)`: laser-frequency-noise PSD.
- `n`: Bragg order.
- `f`: Fourier frequency.

This is the effective model used in the code. It compresses the laser-noise transfer into a single phase-noise PSD before the final transfer-function weighting.

## 11. Mirror Acceleration Noise To Phase Noise

Let `S_a(f)` be the mirror acceleration PSD. The mirror displacement PSD is implicitly modeled via

\[
S_z(f) = \frac{S_a(f)}{(2 \pi f)^4}.
\]

The corresponding interferometer phase-noise PSD is

\[
S_{\phi,\mathrm{vib}}(f) = k_{\mathrm{eff}}^2 S_z(f)
=
\frac{k_{\mathrm{eff}}^2 S_a(f)}{(2 \pi f)^4}.
\]

Parameter meanings:

- `S_a(f)`: mirror acceleration PSD.
- `S_z(f)`: mirror displacement PSD.
- `S_phi,vib(f)`: interferometer phase-noise PSD from mirror vibration.
- `k_eff`: effective wavevector.
- `f`: Fourier frequency.

## 12. Interferometer Transfer Function

For the effective three-pulse sequence, the simulator uses the frequency-domain weighting

\[
H(f) = \left|1 - 2 e^{-i 2 \pi f T} + e^{-i 4 \pi f T}\right|.
\]

The weighted phase-noise integrand is therefore

\[
I(f) = |H(f)|^2 S_{\phi}(f).
\]

This is evaluated separately for laser noise and vibration noise.

Parameter meanings:

- `H(f)`: magnitude of the interferometer transfer function.
- `I(f)`: weighted phase-noise integrand.
- `T`: pulse separation.
- `S_phi(f)`: phase-noise PSD of one technical noise source.

## 13. Integrated Phase Noise

The simulator integrates the weighted phase-noise PSD over a logarithmic frequency grid:

\[
\sigma_{\phi}^2 = \int_{f_{\min}}^{f_{\max}} |H(f)|^2 S_{\phi}(f)\, df.
\]

The RMS phase noise is

\[
\sigma_{\phi} = \sqrt{\sigma_{\phi}^2}.
\]

This is done independently for:

- laser-frequency noise,
- mirror-vibration noise.

Parameter meanings:

- `sigma_phi`: RMS phase noise contributed by one noise source.
- `f_min`, `f_max`: integration bounds.
- `|H(f)|^2 S_phi(f)`: transfer-function-weighted phase-noise PSD.

## 14. Pulse-Level Effective Parameters

Each Bragg pulse is parameterized by:

- `P`: transfer probability.
- `L`: loss probability.
- `phi_d`: diffraction phase.
- `sigma_P`: shot-to-shot standard deviation of the transfer probability.
- `sigma_phi_d`: shot-to-shot standard deviation of the diffraction phase.

These are defined separately for:

- the first beam splitter,
- the mirror pulse,
- the second beam splitter.

## 15. Shot-To-Shot Pulse Fluctuations

For each Monte Carlo shot, the transfer probability is sampled as

\[
P' \sim \mathcal{N}(P, \sigma_P),
\]

and clipped to the interval `[0, 1]`.

The diffraction phase is sampled as

\[
\phi_d' \sim \mathcal{N}(\phi_d, \sigma_{\phi_d}).
\]

Parameter meanings:

- `P'`: shot-specific transfer probability.
- `phi_d'`: shot-specific diffraction phase.
- `P`: mean transfer probability.
- `phi_d`: mean diffraction phase.
- `sigma_P`: standard deviation of the transfer probability.
- `sigma_phi_d`: standard deviation of the diffraction phase.

## 16. Effective Pulse Matrix

Each pulse is represented by the effective complex matrix

\[
U(P', \phi_d', L)
=
\sqrt{1-L}
\begin{bmatrix}
\sqrt{1-P'} & -i e^{-i \phi_d'} \sqrt{P'} \\
-i e^{i \phi_d'} \sqrt{P'} & \sqrt{1-P'}
\end{bmatrix}.
\]

Parameter meanings:

- `U`: effective pulse matrix.
- `P'`: shot-specific transfer probability.
- `L`: loss probability.
- `phi_d'`: shot-specific diffraction phase.

Interpretation:

- diagonal elements describe the amplitude that remains in the same effective port,
- off-diagonal elements describe transfer between the two effective ports,
- the prefactor `sqrt(1-L)` removes population that leaks into untracked parasitic momentum states.

## 17. Initial State

The interferometer starts in the lower basis state of the effective two-port model:

\[
\psi_0 =
\begin{bmatrix}
1 \\
0
\end{bmatrix}.
\]

Parameter meanings:

- `psi_0`: initial state vector before the first pulse.

## 18. Total Shot Phase

For each Monte Carlo shot, the total interferometer phase applied to the final pulse is

\[
\phi_{\mathrm{shot}}
=
\phi_{\mathrm{det}}
+ \delta \phi_{\mathrm{laser}}
+ \delta \phi_{\mathrm{vib}},
\]

with

\[
\delta \phi_{\mathrm{laser}} \sim \mathcal{N}(0, \sigma_{\phi,\mathrm{laser}})
\]

and

\[
\delta \phi_{\mathrm{vib}} \sim \mathcal{N}(0, \sigma_{\phi,\mathrm{vib}}).
\]

Parameter meanings:

- `phi_shot`: total shot-specific interferometer phase.
- `phi_det`: deterministic phase from inertial and user-defined terms.
- `delta phi_laser`: laser-noise phase draw.
- `delta phi_vib`: vibration-noise phase draw.
- `sigma_phi,laser`: RMS laser-noise phase.
- `sigma_phi,vib`: RMS vibration-noise phase.

## 19. Three-Pulse State Propagation

The three effective pulse matrices are:

\[
U_1 = U(P_1', \phi_{d,1}', L_1),
\]

\[
U_2 = U(P_2', \phi_{d,2}', L_2),
\]

\[
U_3 = U(P_3', \phi_{d,3}' + \phi_{\mathrm{shot}}, L_3).
\]

The final state is

\[
\psi_f = U_3 U_2 U_1 \psi_0.
\]

Parameter meanings:

- `U1`, `U2`, `U3`: first beam splitter, mirror, and second beam splitter matrices.
- `phi_shot`: shot-specific interferometer phase added to the last pulse.
- `psi_f`: final state vector after the full sequence.

## 20. Output-Port Populations

If

\[
\psi_f =
\begin{bmatrix}
\psi_A \\
\psi_B
\end{bmatrix},
\]

then the absolute tracked-port populations are

\[
P_A = |\psi_A|^2,
\]

\[
P_B = |\psi_B|^2.
\]

The effective loss channel is

\[
P_{\mathrm{loss}} = 1 - (P_A + P_B).
\]

Parameter meanings:

- `P_A`: lower effective output-port population.
- `P_B`: upper effective output-port population.
- `P_loss`: population leaked out of the tracked two-port model.

## 21. Normalised Port Populations

The plotted upper-port normalised population is

\[
P_{B,\mathrm{norm}} = \frac{P_B}{P_A + P_B}.
\]

The normalised lower-port population is

\[
P_{A,\mathrm{norm}} = \frac{P_A}{P_A + P_B}.
\]

Since the denominator is the same, the two satisfy

\[
P_{A,\mathrm{norm}} = 1 - P_{B,\mathrm{norm}}.
\]

This identity is exact inside the model, even when `P_loss` is nonzero.

Parameter meanings:

- `P_B,norm`: normalised upper-port population.
- `P_A,norm`: normalised lower-port population.

## 22. Monte Carlo Averaging Over Shots

At each scanned phase point, the simulator runs `N_shot` independent shots and computes:

\[
\overline{P}_{B,\mathrm{norm}} = \frac{1}{N_{\mathrm{shot}}} \sum_{j=1}^{N_{\mathrm{shot}}} P_{B,\mathrm{norm}}^{(j)},
\]

\[
\overline{P}_{A,\mathrm{norm}} = \frac{1}{N_{\mathrm{shot}}} \sum_{j=1}^{N_{\mathrm{shot}}} P_{A,\mathrm{norm}}^{(j)}.
\]

The absolute means are similarly defined:

\[
\overline{P}_A = \frac{1}{N_{\mathrm{shot}}} \sum_{j=1}^{N_{\mathrm{shot}}} P_A^{(j)},
\]

\[
\overline{P}_B = \frac{1}{N_{\mathrm{shot}}} \sum_{j=1}^{N_{\mathrm{shot}}} P_B^{(j)}.
\]

Parameter meanings:

- `N_shot`: number of Monte Carlo shots per phase point.
- overbar: Monte Carlo mean over shots.

## 23. Shot Scatter

The plotted `shot scatter` is the sample standard deviation of the normalised port population at a fixed scanned phase:

\[
\sigma_{\mathrm{scatter}} =
\sqrt{
\frac{1}{N_{\mathrm{shot}} - 1}
\sum_{j=1}^{N_{\mathrm{shot}}}
\left(P_{\mathrm{norm}}^{(j)} - \overline{P}_{\mathrm{norm}}\right)^2
}.
\]

Because

\[
P_{A,\mathrm{norm}} = 1 - P_{B,\mathrm{norm}},
\]

the normalised upper-port and lower-port scatters are equal in this model.

Parameter meanings:

- `sigma_scatter`: sample standard deviation at one scanned phase point.
- `P_norm^(j)`: normalised port population in shot `j`.
- `P_norm_bar`: mean normalised port population.

## 24. Cosine Fringe Fit

After averaging over shots, the simulator fits the displayed normalised fringe with

\[
P_{\mathrm{fit}}(\phi_0)
=
C_0 + C \cos(n \phi_0 + \phi_{\mathrm{fit}}).
\]

Parameter meanings:

- `C0`: fitted offset.
- `C`: fitted fringe amplitude.
- `n`: Bragg order.
- `phi0`: scanned optical phase.
- `phi_fit`: fitted phase offset.

The reported contrast is defined as the peak-to-peak excursion of the displayed fringe over the scanned phase range:

\[
\mathcal{C}_{\mathrm{pp}} = P_{\max} - P_{\min}.
\]

Parameter meanings:

- `C_pp`: reported peak-to-peak contrast.
- `P_max`: maximum value of the displayed normalised fringe over the scan.
- `P_min`: minimum value of the displayed normalised fringe over the scan.

For an ideal cosine sampled densely over a full period, this satisfies

\[
\mathcal{C}_{\mathrm{pp}} = 2 C,
\]

where `C` is the cosine-fit amplitude defined above.

## 25. Lower-Port Versus Upper-Port Display

The upper-port display uses the curve

\[
P_{\mathrm{display}} = P_{B,\mathrm{norm}}.
\]

The lower-port display uses the curve

\[
P_{\mathrm{display}} = P_{A,\mathrm{norm}} = 1 - P_{B,\mathrm{norm}}.
\]

Therefore:

- the two normalised port curves are complementary,
- they have the same scatter magnitude,
- their fitted cosine amplitudes have equal magnitude,
- their fitted phase offsets differ by `pi` modulo `2 pi`.

## 26. Effective Rabi-Model Mapping

When pulse parameters are constructed from an effective two-state Rabi model, the transfer probability is estimated as

\[
P =
\frac{\Omega_{\mathrm{eff}}^2}
{\Omega_{\mathrm{eff}}^2 + \Delta^2}
\sin^2\left(
\frac{\tau}{2}
\sqrt{\Omega_{\mathrm{eff}}^2 + \Delta^2}
\right).
\]

Parameter meanings:

- `Omega_eff`: effective Rabi frequency.
- `Delta`: detuning.
- `tau`: pulse duration.
- `P`: effective transfer probability used in the pulse matrix.

This mapping is provided as a convenience function. The main GUI workflow accepts `P` directly.

## 27. Numerical Integration Grid

The noise integration uses a logarithmic frequency grid:

\[
f_k \in [f_{\min}, f_{\max}],
\]

with `N_f` points spaced logarithmically between the bounds.

Parameter meanings:

- `f_min`: lower frequency cutoff.
- `f_max`: upper frequency cutoff.
- `N_f`: number of frequency-grid points.

## 28. Approximations And Limits

The formulas above correspond to an effective model with the following approximations:

1. Only two effective interferometer ports are propagated explicitly.
2. Additional Bragg momentum ports are absorbed into effective loss.
3. Phase noise is reduced to Gaussian shot-to-shot phase draws after transfer-function integration.
4. Pulse imperfections are represented by effective transfer probability and effective diffraction phase.
5. The reported `shot scatter` is Monte Carlo scatter of the model outputs, not a full atom-detection noise model.

These approximations make the simulator fast and interpretable, but they should not be confused with a full multistate Bragg propagation treatment.
