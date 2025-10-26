"""Scenario helpers for deterministic sweeps and Monte Carlo sampling."""
from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import product
from typing import Dict, Iterable, List, Optional

import math
import random

from .finance import FinanceConfig, FinanceResult, evaluate_finance
from .system_model import ScenarioParams, ScenarioSummary, SystemConfig, summarize_scenario
from .task_model import AccuracyModel


@dataclass
class ScenarioOutcome:
    name: str
    summary: ScenarioSummary
    finance: FinanceResult

    def scoreboard(self) -> str:
        irr_pct = self.finance.irr * 100 if self.finance.irr is not None else float("nan")
        return (
            f"ΔN={self.summary.delta_bits:.2f} | Conv Savings={self.summary.converter_savings_pct:.0f}% "
            f"| System Power↓={self.summary.system_power_reduction_pct:.0f}% | AccΔ={self.summary.accuracy_drop_pct:.2f}% "
            f"| TCO↓={self.finance.tco_reduction_pct:.0f}% | ROI={self.finance.roi:.2f}x "
            f"| NPV=${self.finance.npv/1e6:.2f}M | IRR={irr_pct:.1f}% "
            f"| Payback={self.finance.payback_months:.1f} mo"
        )


def run_scenario(
    name: str,
    system_cfg: SystemConfig,
    finance_cfg: FinanceConfig,
    accuracy_model: AccuracyModel,
    params: ScenarioParams,
) -> ScenarioOutcome:
    summary = summarize_scenario(system_cfg, params, accuracy_model)
    finance = evaluate_finance(
        finance_cfg,
        summary.baseline_energy_cost,
        summary.logq_energy_cost,
        summary.baseline_revenue,
        summary.logq_revenue,
    )
    return ScenarioOutcome(name=name, summary=summary, finance=finance)


def deterministic_scenarios(
    system_cfg: SystemConfig,
    finance_cfg: FinanceConfig,
    accuracy_model: AccuracyModel,
    base_delta_bits: float,
    bins_options: Iterable[int] = (8, 12, 16),
) -> List[ScenarioOutcome]:
    outcomes: List[ScenarioOutcome] = []
    delta_bits_grid = [0.5, 1.0, 1.5, 2.0]
    p_adc_range = [0.75, 0.85, 0.95]
    electricity_values = [system_cfg.electricity_price_per_kwh * factor for factor in (0.75, 1.0, 1.5)]
    utilization_values = [0.4, system_cfg.utilization, 0.8]

    for bins, delta_bits, p_adc, price, util in product(
        bins_options, delta_bits_grid, p_adc_range, electricity_values, utilization_values
    ):
        scenario_cfg = replace(
            system_cfg,
            p_adc_share=float(p_adc),
            electricity_price_per_kwh=float(price),
            utilization=float(util),
        )
        params = ScenarioParams(delta_bits=float(delta_bits), bins_per_decade=float(bins))
        name = f"bins{bins}_dN{delta_bits:.2f}_p{p_adc:.2f}_price{price:.2f}_util{util:.2f}"
        outcomes.append(run_scenario(name, scenario_cfg, finance_cfg, accuracy_model, params))
    return outcomes


def monte_carlo(
    system_cfg: SystemConfig,
    finance_cfg: FinanceConfig,
    accuracy_model: AccuracyModel,
    bins_per_decade: float,
    delta_mean: float,
    delta_std: float,
    trials: int,
    seed: Optional[int] = None,
) -> List[Dict[str, float]]:
    rng = random.Random(seed)
    sigma = 0.3
    mu = math.log(system_cfg.electricity_price_per_kwh) - 0.5 * sigma**2
    records: List[Dict[str, float]] = []

    for _ in range(trials):
        sampled_delta = max(0.0, min(system_cfg.enob_baseline_bits - 1, rng.gauss(delta_mean, delta_std)))
        sampled_padc = rng.triangular(0.8, 0.85, 0.9)
        sampled_penalty = rng.uniform(0.3, 0.8)
        sampled_price = rng.lognormvariate(mu, sigma)

        scenario_cfg = replace(
            system_cfg,
            p_adc_share=float(sampled_padc),
            electricity_price_per_kwh=float(sampled_price),
            accuracy_penalty_to_revenue=float(sampled_penalty),
        )
        params = ScenarioParams(delta_bits=float(sampled_delta), bins_per_decade=float(bins_per_decade))
        outcome = run_scenario("mc", scenario_cfg, finance_cfg, accuracy_model, params)
        record = outcome.summary.as_dict()
        record.update(
            {
                "roi": outcome.finance.roi,
                "npv": outcome.finance.npv,
                "irr": outcome.finance.irr if outcome.finance.irr is not None else float("nan"),
                "payback_months": outcome.finance.payback_months,
                "tco_reduction_pct": outcome.finance.tco_reduction_pct,
                "sampled_delta_bits": sampled_delta,
                "sampled_p_adc_share": sampled_padc,
                "sampled_accuracy_penalty": sampled_penalty,
                "sampled_electricity_price": sampled_price,
            }
        )
        records.append(record)
    return records


__all__ = [
    "ScenarioOutcome",
    "run_scenario",
    "deterministic_scenarios",
    "monte_carlo",
]
