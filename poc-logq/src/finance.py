"""Financial modeling utilities for ROI style metrics."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional


@dataclass
class FinanceConfig:
    hw_cost_baseline_usd: float
    hw_cost_logq_usd: float
    r_and_d_nonrecurring_usd: float
    discount_rate_annual: float
    lifetime_years: int
    residual_value_fraction: float


@dataclass
class FinanceResult:
    roi: float
    npv: float
    irr: Optional[float]
    payback_months: float
    baseline_tco: float
    logq_tco: float
    tco_reduction_pct: float
    cashflows: List[float]


def total_cost_of_ownership(
    hw_cost: float, energy_cost_per_year: float, lifetime_years: int, residual_fraction: float
) -> float:
    residual = hw_cost * residual_fraction
    return hw_cost + energy_cost_per_year * lifetime_years - residual


def build_cashflows(
    finance_cfg: FinanceConfig,
    energy_savings_per_year: float,
    delta_revenue_per_year: float,
) -> List[float]:
    delta_capex = finance_cfg.hw_cost_logq_usd - finance_cfg.hw_cost_baseline_usd
    residual_delta = (
        finance_cfg.hw_cost_logq_usd * finance_cfg.residual_value_fraction
        - finance_cfg.hw_cost_baseline_usd * finance_cfg.residual_value_fraction
    )

    cashflows = [-(delta_capex + finance_cfg.r_and_d_nonrecurring_usd)]
    for year in range(1, finance_cfg.lifetime_years + 1):
        cash = energy_savings_per_year + delta_revenue_per_year
        if year == finance_cfg.lifetime_years:
            cash += residual_delta
        cashflows.append(cash)
    return cashflows


def npv(rate: float, cashflows: Iterable[float]) -> float:
    return sum(cf / ((1 + rate) ** idx) for idx, cf in enumerate(cashflows))


def irr(cashflows: Iterable[float], guess: float = 0.1) -> Optional[float]:
    cashflows = list(cashflows)
    if not cashflows or all(cf >= 0 for cf in cashflows[1:]):
        return None

    def f(rate: float) -> float:
        return npv(rate, cashflows)

    r0 = guess
    r1 = guess + 0.1
    f0 = f(r0)
    f1 = f(r1)
    for _ in range(100):
        if abs(f1 - f0) < 1e-9:
            break
        r2 = r1 - f1 * (r1 - r0) / (f1 - f0)
        if abs(r2 - r1) < 1e-7:
            return r2
        r0, r1 = r1, r2
        f0, f1 = f1, f(r1)
    return r1 if abs(f1) < 1e-6 else None


def payback_period_months(cashflows: Iterable[float]) -> float:
    cashflows = list(cashflows)
    if all(cf == 0 for cf in cashflows):
        return float("inf")
    cumulative = 0.0
    for idx, cf in enumerate(cashflows):
        cumulative += cf
        if cumulative >= 0:
            if idx == 0:
                return 0.0
            prev_cumulative = cumulative - cf
            fraction = (0 - prev_cumulative) / cf if cf != 0 else 0
            return (idx - 1 + fraction) * 12
    return float("inf")


def evaluate_finance(
    finance_cfg: FinanceConfig,
    baseline_energy_cost: float,
    logq_energy_cost: float,
    baseline_revenue: float,
    logq_revenue: float,
) -> FinanceResult:
    energy_savings_per_year = baseline_energy_cost - logq_energy_cost
    delta_revenue_per_year = logq_revenue - baseline_revenue

    cashflows = build_cashflows(finance_cfg, energy_savings_per_year, delta_revenue_per_year)

    roi_gains = energy_savings_per_year * finance_cfg.lifetime_years + delta_revenue_per_year * finance_cfg.lifetime_years
    roi_gains += (
        finance_cfg.hw_cost_logq_usd * finance_cfg.residual_value_fraction
        - finance_cfg.hw_cost_baseline_usd * finance_cfg.residual_value_fraction
    )
    roi_costs = (finance_cfg.hw_cost_logq_usd - finance_cfg.hw_cost_baseline_usd) + finance_cfg.r_and_d_nonrecurring_usd
    if roi_costs == 0:
        roi = 0.0 if roi_gains == 0 else float("inf")
    else:
        roi = roi_gains / roi_costs

    net_present_value = npv(finance_cfg.discount_rate_annual, cashflows)
    internal_rate = irr(cashflows)
    payback = payback_period_months(cashflows)

    baseline_tco = total_cost_of_ownership(
        finance_cfg.hw_cost_baseline_usd,
        baseline_energy_cost,
        finance_cfg.lifetime_years,
        finance_cfg.residual_value_fraction,
    )
    logq_tco = total_cost_of_ownership(
        finance_cfg.hw_cost_logq_usd,
        logq_energy_cost,
        finance_cfg.lifetime_years,
        finance_cfg.residual_value_fraction,
    )
    tco_reduction_pct = (baseline_tco - logq_tco) / baseline_tco * 100

    return FinanceResult(
        roi=roi,
        npv=net_present_value,
        irr=internal_rate,
        payback_months=payback,
        baseline_tco=baseline_tco,
        logq_tco=logq_tco,
        tco_reduction_pct=tco_reduction_pct,
        cashflows=cashflows,
    )


__all__ = [
    "FinanceConfig",
    "FinanceResult",
    "evaluate_finance",
    "total_cost_of_ownership",
    "npv",
    "irr",
    "payback_period_months",
]
