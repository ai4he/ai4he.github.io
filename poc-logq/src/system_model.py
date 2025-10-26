"""System level aggregation for power, throughput, and cost impacts."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Optional

import math

from .adc_models import ConverterConfig, converter_power, converter_savings_ratio
from .task_model import AccuracyModel

SECONDS_PER_YEAR = 365 * 24 * 3600


@dataclass
class SystemConfig:
    p_adc_share: float
    enob_baseline_bits: float
    adc_e0_pj: float
    dac_e0_pj: float
    include_dac: bool
    sample_rate_ksps: float
    n_channels: int
    duty_cycle: float
    baseline_inferences_per_sec: float
    utilization: float
    electricity_price_per_kwh: float
    price_per_1k_inferences_usd: float
    accuracy_penalty_to_revenue: float


@dataclass
class ScenarioParams:
    delta_bits: float
    bins_per_decade: float
    layer_profiles_path: Optional[Path] = None


@dataclass
class PowerBreakdown:
    power_conv_baseline_w: float
    power_conv_logq_w: float
    power_system_baseline_w: float
    power_system_logq_w: float
    converter_savings_pct: float
    system_power_reduction_pct: float


@dataclass
class ThroughputResult:
    baseline_inferences_per_sec: float
    logq_inferences_per_sec: float
    throughput_gain_x: float


@dataclass
class RevenueResult:
    baseline_revenue: float
    logq_revenue: float
    delta_revenue: float


@dataclass
class CostResult:
    baseline_energy_cost: float
    logq_energy_cost: float
    energy_savings: float


@dataclass
class ScenarioSummary:
    delta_bits: float
    bins_per_decade: float
    converter_savings_pct: float
    system_power_reduction_pct: float
    accuracy_drop_pct: float
    throughput_gain_x: float
    baseline_energy_cost: float
    logq_energy_cost: float
    energy_savings: float
    baseline_revenue: float
    logq_revenue: float
    delta_revenue: float
    power_system_baseline_w: float
    power_system_logq_w: float

    def as_dict(self) -> Dict[str, float]:
        return asdict(self)


def _effective_delta_bits(delta_bits: float, bins_per_decade: float, enob_baseline_bits: float) -> float:
    """Blend configured delta_bits with limits implied by bins_per_decade."""

    max_delta = max(0.0, enob_baseline_bits - math.log(bins_per_decade, 2))
    return float(min(delta_bits, max_delta if max_delta > 0 else delta_bits))


def compute_power(config: SystemConfig, params: ScenarioParams) -> PowerBreakdown:
    delta_bits = _effective_delta_bits(params.delta_bits, params.bins_per_decade, config.enob_baseline_bits)

    conv_cfg = ConverterConfig(
        enob_baseline_bits=config.enob_baseline_bits,
        delta_bits=delta_bits,
        adc_e0_pj=config.adc_e0_pj,
        dac_e0_pj=config.dac_e0_pj,
        include_dac=config.include_dac,
        sample_rate_ksps=config.sample_rate_ksps,
        n_channels=config.n_channels,
        duty_cycle=config.duty_cycle,
    )
    power_conv_baseline, power_conv_logq = converter_power(conv_cfg)

    power_system_baseline = power_conv_baseline / config.p_adc_share
    power_system_logq = power_conv_logq / config.p_adc_share

    converter_savings_pct = converter_savings_ratio(delta_bits) * 100
    system_power_reduction_pct = (1 - power_system_logq / power_system_baseline) * 100

    return PowerBreakdown(
        power_conv_baseline_w=power_conv_baseline,
        power_conv_logq_w=power_conv_logq,
        power_system_baseline_w=power_system_baseline,
        power_system_logq_w=power_system_logq,
        converter_savings_pct=converter_savings_pct,
        system_power_reduction_pct=system_power_reduction_pct,
    )


def compute_energy_cost(power_watts: float, utilization: float, price_per_kwh: float) -> float:
    energy_kwh = power_watts * utilization * SECONDS_PER_YEAR / 3600
    return energy_kwh * price_per_kwh


def compute_throughput(config: SystemConfig, power_breakdown: PowerBreakdown) -> ThroughputResult:
    throughput_logq = config.baseline_inferences_per_sec * (
        power_breakdown.power_system_baseline_w / power_breakdown.power_system_logq_w
    )
    return ThroughputResult(
        baseline_inferences_per_sec=config.baseline_inferences_per_sec,
        logq_inferences_per_sec=throughput_logq,
        throughput_gain_x=throughput_logq / config.baseline_inferences_per_sec,
    )


def compute_revenue(config: SystemConfig, throughput: ThroughputResult, accuracy_drop_pct: float) -> RevenueResult:
    baseline_rev = _revenue_for(config, throughput.baseline_inferences_per_sec, 0.0)
    logq_rev = _revenue_for(config, throughput.logq_inferences_per_sec, accuracy_drop_pct)
    return RevenueResult(
        baseline_revenue=baseline_rev,
        logq_revenue=logq_rev,
        delta_revenue=logq_rev - baseline_rev,
    )


def _revenue_for(config: SystemConfig, inferences_per_sec: float, accuracy_drop_pct: float) -> float:
    inferences_per_year = inferences_per_sec * SECONDS_PER_YEAR * config.utilization
    gross = config.price_per_1k_inferences_usd * (inferences_per_year / 1000)
    penalty = 1 - config.accuracy_penalty_to_revenue * (accuracy_drop_pct / 100)
    penalty = max(0.0, penalty)
    return gross * penalty


def compute_costs(config: SystemConfig, power_breakdown: PowerBreakdown) -> CostResult:
    baseline_cost = compute_energy_cost(
        power_breakdown.power_system_baseline_w, config.utilization, config.electricity_price_per_kwh
    )
    logq_cost = compute_energy_cost(
        power_breakdown.power_system_logq_w, config.utilization, config.electricity_price_per_kwh
    )
    return CostResult(
        baseline_energy_cost=baseline_cost,
        logq_energy_cost=logq_cost,
        energy_savings=baseline_cost - logq_cost,
    )


def summarize_scenario(
    config: SystemConfig,
    params: ScenarioParams,
    accuracy_model: AccuracyModel,
) -> ScenarioSummary:
    power_breakdown = compute_power(config, params)
    delta_bits = _effective_delta_bits(params.delta_bits, params.bins_per_decade, config.enob_baseline_bits)
    accuracy_drop = accuracy_model.accuracy_drop_pct(delta_bits)
    throughput = compute_throughput(config, power_breakdown)
    revenue = compute_revenue(config, throughput, accuracy_drop)
    costs = compute_costs(config, power_breakdown)

    return ScenarioSummary(
        delta_bits=delta_bits,
        bins_per_decade=params.bins_per_decade,
        converter_savings_pct=power_breakdown.converter_savings_pct,
        system_power_reduction_pct=power_breakdown.system_power_reduction_pct,
        accuracy_drop_pct=accuracy_drop,
        throughput_gain_x=throughput.throughput_gain_x,
        baseline_energy_cost=costs.baseline_energy_cost,
        logq_energy_cost=costs.logq_energy_cost,
        energy_savings=costs.energy_savings,
        baseline_revenue=revenue.baseline_revenue,
        logq_revenue=revenue.logq_revenue,
        delta_revenue=revenue.delta_revenue,
        power_system_baseline_w=power_breakdown.power_system_baseline_w,
        power_system_logq_w=power_breakdown.power_system_logq_w,
    )


__all__ = [
    "SystemConfig",
    "ScenarioParams",
    "ScenarioSummary",
    "compute_power",
    "compute_costs",
    "compute_revenue",
    "compute_throughput",
    "summarize_scenario",
]
