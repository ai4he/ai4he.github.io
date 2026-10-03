"""CLI entry-point for the log quantization PoC simulator."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
from pathlib import Path
from typing import List

from .finance import FinanceConfig
from .io_utils import load_config
from .plots import plot_energy_breakdown, plot_npv_cdf, plot_payback_hist, plot_roi_vs_delta, plot_tornado
from .scenarios import ScenarioOutcome, deterministic_scenarios, monte_carlo, run_scenario
from .system_model import ScenarioParams, SystemConfig
from .task_model import AccuracyConfig, AccuracyModel


def build_system_config(cfg: dict) -> SystemConfig:
    return SystemConfig(
        p_adc_share=cfg["p_adc_share"],
        enob_baseline_bits=cfg["enob_baseline_bits"],
        adc_e0_pj=cfg["adc_e0_pj"],
        dac_e0_pj=cfg["dac_e0_pj"],
        include_dac=cfg.get("include_dac", True),
        sample_rate_ksps=cfg["sample_rate_ksps"],
        n_channels=cfg["n_channels"],
        duty_cycle=cfg["duty_cycle"],
        baseline_inferences_per_sec=cfg["baseline_inferences_per_sec"],
        utilization=cfg["utilization"],
        electricity_price_per_kwh=cfg["electricity_price_per_kwh"],
        price_per_1k_inferences_usd=cfg.get("price_per_1k_inferences_usd", 0.0),
        accuracy_penalty_to_revenue=cfg.get("accuracy_penalty_to_revenue", 0.0),
    )


def build_finance_config(cfg: dict) -> FinanceConfig:
    return FinanceConfig(
        hw_cost_baseline_usd=cfg["hw_cost_baseline_usd"],
        hw_cost_logq_usd=cfg["hw_cost_logq_usd"],
        r_and_d_nonrecurring_usd=cfg.get("r_and_d_nonrecurring_usd", 0.0),
        discount_rate_annual=cfg.get("discount_rate_annual", 0.1),
        lifetime_years=cfg.get("lifetime_years", 3),
        residual_value_fraction=cfg.get("residual_value_fraction", 0.0),
    )


def build_accuracy_model(cfg: dict) -> AccuracyModel:
    acc_cfg = AccuracyConfig(
        acc_drop_at_1bit=cfg["acc_drop_at_1bit"],
        acc_drop_k=cfg["acc_drop_k"],
        acc_drop_cap=cfg.get("acc_drop_cap", 100.0),
        accuracy_curve_path=Path("data/accuracy_curves.csv"),
    )
    return AccuracyModel(acc_cfg)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PoC simulation for log quantization ROI")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--run_name", type=str, default="baseline")
    parser.add_argument("--sweep", action="store_true")
    parser.add_argument("--mc", action="store_true")
    parser.add_argument("--plot", action="store_true")
    return parser.parse_args()


def ensure_output_dir(run_name: str) -> Path:
    timestamp = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = Path("outputs") / "runs" / f"{timestamp}_{run_name}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_summary(outcomes: List[ScenarioOutcome], path: Path) -> None:
    records = []
    for outcome in outcomes:
        record = outcome.summary.as_dict()
        record.update(
            {
                "name": outcome.name,
                "roi": outcome.finance.roi,
                "npv": outcome.finance.npv,
                "irr": outcome.finance.irr,
                "payback_months": outcome.finance.payback_months,
                "tco_reduction_pct": outcome.finance.tco_reduction_pct,
            }
        )
        records.append(record)
    if not records:
        return
    fieldnames = list(records[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def main() -> None:
    args = parse_args()
    cfg = load_config(args.config)

    system_cfg = build_system_config(cfg)
    finance_cfg = build_finance_config(cfg)
    accuracy_model = build_accuracy_model(cfg)

    output_dir = ensure_output_dir(args.run_name)

    delta_bits = cfg.get("delta_bits_log_mean", 0.0)
    bins_per_decade = cfg.get("bins_per_decade", 12)

    base_params = ScenarioParams(delta_bits=delta_bits, bins_per_decade=bins_per_decade)
    base_outcome = run_scenario("baseline", system_cfg, finance_cfg, accuracy_model, base_params)

    print(base_outcome.scoreboard())

    outcomes = [base_outcome]

    if args.sweep:
        sweep_outcomes = deterministic_scenarios(system_cfg, finance_cfg, accuracy_model, delta_bits)
        for outcome in sweep_outcomes:
            print(outcome.scoreboard())
        outcomes.extend(sweep_outcomes)

    save_summary(outcomes, output_dir / "summary.csv")

    cashflow_path = output_dir / "cashflows_baseline.csv"
    with cashflow_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["year", "cashflow"])
        for idx, value in enumerate(base_outcome.finance.cashflows):
            writer.writerow([idx, value])

    mc_records: List[dict] = []
    if args.mc:
        mc_trials = int(cfg.get("mc_trials", 1000))
        mc_records = monte_carlo(
            system_cfg,
            finance_cfg,
            accuracy_model,
            bins_per_decade,
            cfg.get("delta_bits_log_mean", delta_bits),
            cfg.get("delta_bits_log_std", 0.2),
            mc_trials,
            seed=cfg.get("random_seed"),
        )
        if mc_records:
            fieldnames = list(mc_records[0].keys())
            with (output_dir / "monte_carlo.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(mc_records)

    if args.plot:
        roi_totals = {}
        roi_counts = {}
        for out in outcomes:
            key = round(out.summary.delta_bits, 6)
            roi_totals[key] = roi_totals.get(key, 0.0) + out.finance.roi
            roi_counts[key] = roi_counts.get(key, 0) + 1
        delta_sorted = sorted(roi_totals.keys())
        roi_avg = [roi_totals[k] / roi_counts[k] for k in delta_sorted]
        plot_roi_vs_delta(delta_sorted, roi_avg, output_dir / "roi_vs_deltabits.png")
        plot_energy_breakdown(
            base_outcome.summary.power_system_baseline_w,
            base_outcome.summary.power_system_logq_w,
            output_dir / "energy_breakdown.png",
        )
        if args.mc and mc_records:
            npv_values = [row["npv"] for row in mc_records]
            payback_values = [row["payback_months"] for row in mc_records]
            plot_npv_cdf(npv_values, output_dir / "npv_cdf.png")
            plot_payback_hist(payback_values, output_dir / "payback_hist.png")
            tornado_cols = [
                "sampled_delta_bits",
                "sampled_p_adc_share",
                "sampled_accuracy_penalty",
                "sampled_electricity_price",
            ]
            samples = [[row[col] for row in mc_records] for col in tornado_cols]
            plot_tornado(npv_values, tornado_cols, samples, output_dir / "tornado_sensitivity.png")


if __name__ == "__main__":
    main()
