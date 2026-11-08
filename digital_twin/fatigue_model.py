"""
core/fatigue_model.py  (v1.3, tuned)

Borbely two-process sleep model + Oman vestibular mismatch ODE + fatigue ODE.
Changes in v1.3 (see CHANGES comments):
  1. Vestibular: mismatch integral is now LEAKY (uses tau_ms, which was unused),
     so motion-sickness risk falls as the brain adapts.
  2. Vestibular: realistic adaptation time scale (days, not hours).
  3. Vestibular: p_ms_step uses hazard_scale so events are rare, not constant.
  4. Fatigue: recovery happens only while sleeping.
"""

import math
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class BorbelyParameters:
    S_max: float = 1.0
    S_min: float = 0.0
    tau_wake: float = 18.7
    tau_sleep: float = 4.2
    T_c: float = 24.0
    M_c: float = 0.50
    A_c: float = 0.17
    phi_c: float = 0.0
    sleep_start_hour: float = 22.0
    sleep_end_hour: float = 6.0
    sleep_noise_std: float = 0.5
    orbital_period_hours: float = 1.5
    phase_noise_amplitude: float = 0.03


@dataclass
class VestibularParameters:
    k_adapt_0: float = 0.03     # CHANGE: was 0.18 (5 h adaptation). 0.03 -> ~1-2 days
    w_s: float = 0.60
    tau_ms: float = 12.0        # CHANGE: now actually used (leaky integrator), was 6.0 unused
    sigma_ms: float = 0.40
    xi_ms: float = 3.0          # CHANGE: was 0.25 (saturated instantly)
    hr_gain: float = 8.0
    hazard_scale: float = 0.10  # NEW: converts rate into rare per-step event probability


@dataclass
class FatigueParameters:
    alpha_sleep_debt: float = 0.35
    beta_mismatch: float = 0.25
    gamma_recovery_base: float = 0.20
    gamma_circadian_boost: float = 0.10
    noise_shape: float = 0.5
    noise_scale: float = 0.03
    min_fatigue: float = 0.0
    max_fatigue: float = 10.0


class BorbelyModel:
    def __init__(self, params: Optional[BorbelyParameters] = None):
        self.p = params or BorbelyParameters()
        self._rng = np.random.default_rng(42)
        self.S = self.p.S_min + 0.30 * (self.p.S_max - self.p.S_min)
        self.S_norm = self.S / self.p.S_max
        self.sleeping = False
        self._phase_noise_accum: float = 0.0

    def seed(self, s: int):
        self._rng = np.random.default_rng(s)

    def reset(self, S_0: float = 0.30):
        self.S = S_0
        self.S_norm = S_0 / self.p.S_max
        self.sleeping = False
        self._phase_noise_accum = 0.0

    def _circadian(self, t_h: float) -> float:
        phi = (t_h + self.p.phi_c) / self.p.T_c
        base = self.p.M_c + self.p.A_c * math.cos(2 * math.pi * phi)
        noise_sigma = self.p.phase_noise_amplitude * self.p.A_c
        self._phase_noise_accum += float(self._rng.normal(0, noise_sigma))
        self._phase_noise_accum *= 0.97
        return base + self._phase_noise_accum

    def _in_sleep_window(self, t_h: float) -> bool:
        hour_of_day = t_h % 24.0
        ss, se = self.p.sleep_start_hour, self.p.sleep_end_hour
        if ss > se:
            return hour_of_day >= ss or hour_of_day <= se
        return ss <= hour_of_day <= se

    def step(self, dt_hours: float, t_h: float) -> Dict[str, Any]:
        C = self._circadian(t_h)
        in_window = self._in_sleep_window(t_h)
        if not self.sleeping and in_window and self.S >= (self.p.M_c + 0.5 * self.p.A_c):
            self.sleeping = True
        elif self.sleeping and not in_window:
            self.sleeping = False

        if self.sleeping:
            dS = -(self.S / self.p.tau_sleep) * dt_hours
        else:
            dS = ((self.p.S_max - self.S) / self.p.tau_wake) * dt_hours

        self.S = float(np.clip(self.S + dS, self.p.S_min, self.p.S_max))
        self.S_norm = self.S / self.p.S_max

        upper_gate = C
        lower_gate = C - self.p.A_c
        if self.sleeping and upper_gate > lower_gate:
            sq = float(np.clip((upper_gate - self.S) / max(upper_gate - lower_gate, 1e-6), 0.0, 1.0))
        elif not self.sleeping:
            sq = float(np.clip(1.0 - self.S_norm, 0.1, 1.0))
        else:
            sq = 0.3

        return {"S": self.S, "C": C, "sleeping": self.sleeping,
                "sleep_quality": sq, "phase_noise": self._phase_noise_accum}


class VestibularMismatchModel:
    def __init__(self, params: Optional[VestibularParameters] = None):
        self.p = params or VestibularParameters()
        self.e_hat = 0.0
        self.cumulative_mismatch = 0.0

    def reset(self, sensory_input: float = 0.0):
        self.e_hat = sensory_input
        self.cumulative_mismatch = 0.0

    def step(self, dt_hours: float, sensory_input: float, S_norm: float) -> Dict[str, Any]:
        k_adapt = self.p.k_adapt_0 * max(0.0, 1.0 - self.p.w_s * S_norm)

        mismatch = sensory_input - self.e_hat
        abs_mismatch = abs(mismatch)

        d_ehat = k_adapt * mismatch * dt_hours
        self.e_hat = float(np.clip(self.e_hat + d_ehat, -2.0, 2.0))

        # CHANGE: leaky integral. Old code: cum += |m|*dt (never decreased, so risk
        # stayed at its maximum forever). New: cum decays with time constant tau_ms.
        self.cumulative_mismatch += (abs_mismatch - self.cumulative_mismatch / self.p.tau_ms) * dt_hours
        self.cumulative_mismatch = max(0.0, self.cumulative_mismatch)

        cum = self.cumulative_mismatch
        p_rate = self.p.sigma_ms * cum / (self.p.xi_ms + cum)
        # CHANGE: hazard_scale makes episodes rare (was p_rate*dt capped at 0.25)
        p_ms_step = float(np.clip(p_rate * dt_hours * self.p.hazard_scale, 0.0, 0.25))

        hr_delta = self.p.hr_gain * abs_mismatch

        return {"mismatch": mismatch, "e_hat": self.e_hat, "k_adapt": k_adapt,
                "cumulative_mismatch": self.cumulative_mismatch,
                "p_ms_step": p_ms_step, "hr_delta": hr_delta,
                "abs_mismatch": abs_mismatch}


class FatigueModel:
    def __init__(self, params: Optional[FatigueParameters] = None):
        self.p = params or FatigueParameters()
        self._rng = np.random.default_rng(1)

    def seed(self, s: int):
        self._rng = np.random.default_rng(s)

    def _circadian_recovery_gate(self, C_val: float, M_c: float = 0.50) -> float:
        trough_depth = max(0.0, M_c - C_val)
        boost = self.p.gamma_circadian_boost * (trough_depth / 0.17)
        return self.p.gamma_recovery_base + boost

    def compute_fatigue_update(
        self,
        current_fatigue: float,
        sleep_quality: float,
        S_norm: float,
        abs_mismatch: float,
        C_val: float,
        dt_hours: float,
        fatigue_forcing: float = 0.0,
        sleeping: bool = True,     # NEW: recovery only while asleep
    ) -> Tuple[float, Dict[str, float]]:
        sleep_debt = float(np.clip(S_norm - 0.5, 0.0, 1.0))
        accum_sleep = self.p.alpha_sleep_debt * (sleep_debt ** 1.2) * dt_hours
        accum_mismatch = self.p.beta_mismatch * (abs_mismatch ** 1.5) * dt_hours

        gamma = self._circadian_recovery_gate(C_val)
        # CHANGE: old code recovered 24 h/day; now only during sleep
        recovery = gamma * sleep_quality * dt_hours if sleeping else 0.0

        noise = float(self._rng.gamma(self.p.noise_shape, self.p.noise_scale)) * dt_hours
        forcing_contrib = fatigue_forcing * dt_hours

        delta = accum_sleep + accum_mismatch - recovery + noise + forcing_contrib
        new_fatigue = float(np.clip(current_fatigue + delta, self.p.min_fatigue, self.p.max_fatigue))

        return new_fatigue, {
            "sleep_debt": sleep_debt, "accum_sleep": accum_sleep,
            "accum_mismatch": accum_mismatch, "recovery": recovery,
            "gamma_effective": gamma, "noise": noise,
            "forcing_contrib": forcing_contrib, "delta": delta,
        }

    def estimate_recovery_hours(self, current_fatigue: float, optimal_sleep_quality: float = 0.9,
                                C_val: float = 0.33, dt_hours: float = 1.0) -> float:
        F, hours = current_fatigue, 0.0
        while F > 1.0 and hours < 168:
            F, _ = self.compute_fatigue_update(
                current_fatigue=F, sleep_quality=optimal_sleep_quality, S_norm=0.1,
                abs_mismatch=0.0, C_val=C_val, dt_hours=dt_hours, sleeping=True)
            hours += dt_hours
        return hours

    def reset(self):
        self._rng = np.random.default_rng(1)


class PhysicsEngine:
    def __init__(self, borbely_params=None, vestibular_params=None, fatigue_params=None):
        self.borbely = BorbelyModel(borbely_params)
        self.vestibular = VestibularMismatchModel(vestibular_params)
        self.fatigue = FatigueModel(fatigue_params)
        self._fatigue_state: float = 0.0

    def seed(self, s: int):
        self.borbely.seed(s)
        self.fatigue.seed(s + 1)

    def reset(self, initial_fatigue: float = 0.0, S_0: float = 0.30):
        self.borbely.reset(S_0=S_0)
        self.vestibular.reset(sensory_input=0.0)
        self.fatigue.reset()
        self._fatigue_state = initial_fatigue

    def step(self, dt_hours: float, t_h: float, sensory_input: float = 1.0,
             fatigue_forcing: float = 0.0) -> Dict[str, Any]:
        borbely_out = self.borbely.step(dt_hours=dt_hours, t_h=t_h)
        vest_out = self.vestibular.step(dt_hours=dt_hours, sensory_input=sensory_input,
                                        S_norm=self.borbely.S_norm)
        new_fatigue, fat_components = self.fatigue.compute_fatigue_update(
            current_fatigue=self._fatigue_state,
            sleep_quality=borbely_out["sleep_quality"],
            S_norm=self.borbely.S_norm,
            abs_mismatch=vest_out["abs_mismatch"],
            C_val=borbely_out["C"],
            dt_hours=dt_hours,
            fatigue_forcing=fatigue_forcing,
            sleeping=borbely_out["sleeping"],
        )
        self._fatigue_state = new_fatigue
        return {
            "fatigue": new_fatigue, "sleep_quality": borbely_out["sleep_quality"],
            "S": borbely_out["S"], "C": borbely_out["C"],
            "sleeping": borbely_out["sleeping"], "phase_noise": borbely_out["phase_noise"],
            "mismatch": vest_out["mismatch"], "e_hat": vest_out["e_hat"],
            "k_adapt": vest_out["k_adapt"],
            "cumulative_mismatch": vest_out["cumulative_mismatch"],
            "p_ms_step": vest_out["p_ms_step"], "hr_delta": vest_out["hr_delta"],
            "abs_mismatch": vest_out["abs_mismatch"], "fatigue_components": fat_components,
        }