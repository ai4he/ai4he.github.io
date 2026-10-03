"""Matplotlib plots for investor-facing visuals."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Sequence

try:  # pragma: no cover - optional dependency
    import matplotlib.pyplot as plt
except ImportError:  # pragma: no cover
    plt = None  # type: ignore


def _prepare_path(path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def plot_roi_vs_delta(delta_bits: Sequence[float], roi: Sequence[float], path: Path) -> None:
    path = _prepare_path(path)
    if plt is None:
        return
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(delta_bits, roi, marker="o")
    ax.set_title("Investor View: ROI vs. Δbits")
    ax.set_xlabel("Δbits removed")
    ax.set_ylabel("ROI (×)")
    ax.grid(True)
    for x, y in zip(delta_bits, roi):
        ax.annotate(f"{y:.2f}x", (x, y), textcoords="offset points", xytext=(0, 6), ha="center")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_npv_cdf(npv_values: Sequence[float], path: Path) -> None:
    path = _prepare_path(path)
    if plt is None:
        return
    values = sorted(npv_values)
    if not values:
        return
    cdf = [i / (len(values) - 1) if len(values) > 1 else 1 for i in range(len(values))]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(values, cdf)
    ax.set_title("Investor View: NPV CDF")
    ax.set_xlabel("NPV (USD)")
    ax.set_ylabel("Cumulative probability")
    ax.grid(True)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_payback_hist(payback_values: Iterable[float], path: Path) -> None:
    path = _prepare_path(path)
    if plt is None:
        return
    filtered = [v for v in payback_values if v not in (float("inf"), float("-inf"))]
    if not filtered:
        return
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(filtered, bins=min(20, len(filtered)))
    ax.set_title("Investor View: Payback Histogram")
    ax.set_xlabel("Payback (months)")
    ax.set_ylabel("Count")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_energy_breakdown(baseline_power: float, logq_power: float, path: Path) -> None:
    path = _prepare_path(path)
    if plt is None:
        return
    fig, ax = plt.subplots(figsize=(6, 4))
    categories = ["Baseline", "LogQ"]
    values = [baseline_power, logq_power]
    ax.bar(categories, values, color=["#ef4444", "#22c55e"])
    ax.set_title("Investor View: System Power")
    ax.set_ylabel("Power (W)")
    for idx, value in enumerate(values):
        ax.text(idx, value, f"{value/1e3:.1f} kW", ha="center", va="bottom")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_tornado(metric_values: Sequence[float], columns: List[str], samples: List[List[float]], path: Path) -> None:
    path = _prepare_path(path)
    if plt is None:
        return
    if not metric_values:
        return
    correlations = []
    n = len(metric_values)
    mean_metric = sum(metric_values) / n
    var_metric = sum((v - mean_metric) ** 2 for v in metric_values)
    for col_name, col_values in zip(columns, zip(*samples)):
        col_list = list(col_values)
        mean_col = sum(col_list) / n
        var_col = sum((v - mean_col) ** 2 for v in col_list)
        if var_metric == 0 or var_col == 0:
            corr = 0.0
        else:
            cov = sum((m - mean_metric) * (c - mean_col) for m, c in zip(metric_values, col_list))
            corr = cov / (var_metric ** 0.5 * var_col ** 0.5)
        correlations.append((col_name, corr))
    correlations.sort(key=lambda x: abs(x[1]), reverse=True)

    labels = [col for col, _ in correlations]
    vals = [corr for _, corr in correlations]
    positions = range(len(labels))

    fig, ax = plt.subplots(figsize=(6, 4))
    colors = ["#22d3ee" if v >= 0 else "#f97316" for v in vals]
    ax.barh(list(positions), vals, color=colors)
    ax.set_yticks(list(positions))
    ax.set_yticklabels(labels)
    ax.set_xlabel("Correlation with NPV")
    ax.set_title("Investor View: Tornado Sensitivity")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


__all__ = [
    "plot_roi_vs_delta",
    "plot_npv_cdf",
    "plot_payback_hist",
    "plot_energy_breakdown",
    "plot_tornado",
]
