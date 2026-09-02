# First hardware validation

This checklist is pending: no TGF3162 was connected during development.

1. Connect PC and generator to the switch. Configure compatible IP addresses/subnets using the operating system and instrument front panel. Note the generator's IP and firmware version.
2. Start the application, choose LAN, set IP and port 9221, then Test Connection. Expect the exact TGF3162 identity. Connect and confirm channel settings/output states initially show unknown.
3. With the load prepared for a test signal, use each channel's Off control. Check the front-panel indicators. Neither channel should follow the other.
4. Apply CH1: 10 kHz, 1 Vpp, 0 degrees, modulation Off. Confirm sine, 50 ohm load setting and zero offset on the front panel. Enable CH1 and measure into a 50 ohm termination. The app itself does not measure waveforms.
5. Set CH2 to a different frequency/amplitude and toggle only CH2. Verify CH1 is unchanged. Repeat with CH1. Test initial instrument tracking/coupling enabled, then verify the app establishes independent operation.
6. For an unmodulated sine, compare 1 Vpp, 0.353553 Vrms and approximately 3.9794 dBm into 50 ohms. Allow for the instrument's rounding and accuracy. Check 50/100/160 MHz amplitude restrictions at appropriate test levels.
7. Test AM at a modest amplitude: 100 kHz carrier, 1 kHz internal sine, 10%, 50%, then 100% depth. Record how programmed Vpp relates to carrier and envelope maxima. Do not interpret converted Vrms/dBm as modulated-waveform RMS/power.
8. Test FM: 1 MHz carrier, 1 kHz internal sine, 10 kHz deviation. Check the front-panel parameters and measure frequency excursion/spectrum with suitable equipment. Verify behavior near frequency and amplitude boundaries separately.
9. At equal carrier frequencies, change each phase and compare against a reference. The app never sends ALIGN. Different frequencies cannot maintain a fixed phase difference.
10. While outputs are off, test a cable disconnect and reconnection. Expect an explicit failure, unknown state and no automatic re-enable. Test instrument restart and inspect power-on handling.
11. Edit a channel manually on the instrument. Observe that the app does not claim to read this change; reapply the intended settings. Confirm multi-client use is excluded for the experiment.
12. Before ending the test, turn off outputs explicitly if needed. Disconnecting the app should leave instrument output enable unchanged.

Record firmware identity, command errors, measured values, load termination and relevant screenshots in the experiment record. Mark hardware validation complete only after actual measurements.
