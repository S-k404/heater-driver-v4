"""Plot ngspice virtual-test results (run: ngspice -b heater_driver_v3_virtual_test.cir; python3 plot_sim.py)"""
import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
d = np.loadtxt('heater_driver_v4_sim.dat')
t = d[:, 0] * 1e3
names = ['pwm', 'iheat', 'vgs', 'fault', 'trip_n', 'latch_p', 'sh_f', 'vref', 'heat_n', 'p12', 'tdeg', 'temp', 'tref']
c = {n: d[:, 2 * i + 1] for i, n in enumerate(names)}
fig, ax = plt.subplots(6, 1, figsize=(11, 13), sharex=True)
ax[0].plot(t, c['pwm'], color='#555'); ax[0].set_ylabel('PWM in (V)'); ax[0].set_ylim(-0.3, 4.8)
ax[1].plot(t, c['iheat'], color='#c0392b'); ax[1].axhline(11.9, ls='--', color='k', lw=0.8)
ax[1].text(0.2, 13, 'trip 11.9 A', fontsize=8); ax[1].set_ylabel('I heater (A)')
ax[2].plot(t, c['vgs'], color='#2c7fb8'); ax[2].set_ylabel('Q1 Vgs (V)')
ax[3].plot(t, c['fault'], color='#d35400', label='FAULT'); ax[3].plot(t, c['trip_n'], color='#27ae60', label='TRIP_N (N)')
ax[3].plot(t, c['latch_p'], color='#8e44ad', label='LATCH_P (P)'); ax[3].legend(fontsize=8, loc='upper left'); ax[3].set_ylabel('latch (V)')
ax[4].plot(t, c['p12'], color='#333'); ax[4].set_ylabel('+12V rail (V)')
ax[5].plot(t, c['tdeg'], color='#c0392b', label='NTC temperature (C)'); ax[5].axhline(84, ls='--', color='k', lw=0.8)
ax[5].text(0.2, 86, 'OTP trip ~84 C', fontsize=8); ax[5].set_ylabel('NTC temp (C)'); ax[5].set_xlabel('time (ms)')
for a in ax:
    a.grid(alpha=0.3)
    for x in (2, 8.3, 10, 12, 13, 14, 14.2, 15.8, 16, 17): a.axvline(x, color='grey', lw=0.6, ls=':')
for x, l in [(0.1, 'power-up'), (2.05, 'PWM 1 kHz 50%'), (8.35, 'SHORT'), (10.05, 'short off'), (12.05, 'RESET'), (13.6, 'RESET held'), (14.25, '+SHORT'), (16.1, 'released'), (17.1, 'OVER-TEMP ramp')]:
    ax[0].text(x, 3.7, l, fontsize=8)
fig.suptitle('Heater driver v4 - virtual test (ngspice): power-up, PWM, short trip, latch, reset, RESET held into short, over-temperature', fontsize=11)
fig.tight_layout(); fig.savefig('sim_overview.png', dpi=110)
m = (t > 8.29) & (t < 8.33)
us = t[m] * 1000 - 8300
fig, ax = plt.subplots(3, 1, figsize=(9, 7), sharex=True)
ax[0].plot(us, c['iheat'][m], color='#c0392b'); ax[0].axhline(11.9, ls='--', color='k', lw=0.8); ax[0].set_ylabel('I (A)')
ax[1].plot(us, c['sh_f'][m] * 1000, label='SH_F (filtered shunt)'); ax[1].plot(us, c['vref'][m] * 1000, label='VREF'); ax[1].set_ylabel('mV'); ax[1].legend(fontsize=8)
ax[2].plot(us, c['vgs'][m], label='Q1 Vgs'); ax[2].plot(us, c['fault'][m], label='FAULT'); ax[2].set_ylabel('V'); ax[2].legend(fontsize=8)
ax[2].set_xlabel('time after short applied (us)')
for a in ax: a.grid(alpha=0.3)
fig.suptitle('Short-circuit zoom: gate off ~8 us after short, peak 37 A, fault latched', fontsize=11)
fig.tight_layout(); fig.savefig('sim_short_zoom.png', dpi=110)
print('ok')
