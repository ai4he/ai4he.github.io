"""Energy and power models for ADC/DAC paths."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ConverterConfig:
    enob_baseline_bits: float
    delta_bits: float
    adc_e0_pj: float
    dac_e0_pj: float
    include_dac: bool
    sample_rate_ksps: float
    n_channels: int
    duty_cycle: float


SECONDS_PER_HOUR = 3600
PJ_TO_J = 1e-12


def energy_per_conversion(enob: float, e0_pj: float) -> float:
    """Return energy per conversion in Joules."""

    return e0_pj * (2 ** enob) * PJ_TO_J


def converter_power(config: ConverterConfig) -> tuple[float, float]:
    """Return converter power (ADC + optional DAC) in Watts for baseline and log quantization."""

    convs_per_sec = config.n_channels * config.sample_rate_ksps * 1e3 * config.duty_cycle

    baseline_enob = config.enob_baseline_bits
    logq_enob = max(1.0, config.enob_baseline_bits - config.delta_bits)

    e_adc_baseline = energy_per_conversion(baseline_enob, config.adc_e0_pj)
    e_adc_logq = energy_per_conversion(logq_enob, config.adc_e0_pj)

    e_dac_baseline = e_dac_logq = 0.0
    if config.include_dac:
        e_dac_baseline = energy_per_conversion(baseline_enob, config.dac_e0_pj)
        e_dac_logq = energy_per_conversion(logq_enob, config.dac_e0_pj)

    power_baseline = convs_per_sec * (e_adc_baseline + e_dac_baseline)
    power_logq = convs_per_sec * (e_adc_logq + e_dac_logq)

    return power_baseline, power_logq


def converter_savings_ratio(delta_bits: float) -> float:
    """Return the theoretical converter energy savings ratio for a given ``delta_bits``."""

    return 1 - 2 ** (-delta_bits)


__all__ = [
    "ConverterConfig",
    "converter_power",
    "energy_per_conversion",
    "converter_savings_ratio",
]
