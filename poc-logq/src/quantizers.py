"""Quantization utilities for linear and logarithmic converters."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

import math


@dataclass
class QuantizerResult:
    """Container holding quantized values and metadata."""

    values: List[float]
    codebook: List[float]
    step_ratio: float


def linear_quantize(values: Iterable[float], n_bits: int, min_val: float, max_val: float) -> QuantizerResult:
    levels = 2 ** n_bits
    span = max_val - min_val
    step = span / (levels - 1) if levels > 1 else 0
    codebook = [min_val + i * step for i in range(levels)] if levels > 1 else [min_val]
    quantized: List[float] = []
    for value in values:
        clamped = min(max(value, min_val), max_val)
        index = int(round((clamped - min_val) / span * (levels - 1))) if span and levels > 1 else 0
        index = max(0, min(index, len(codebook) - 1))
        quantized.append(codebook[index])
    return QuantizerResult(values=quantized, codebook=codebook, step_ratio=1.0)


def log_step_ratio(bins_per_decade: float) -> float:
    return float(10 ** (1.0 / bins_per_decade))


def log_quantize(
    values: Iterable[float],
    anchor: float,
    bins_per_decade: float,
    dead_zone: float = 0.0,
) -> QuantizerResult:
    r = log_step_ratio(bins_per_decade)
    quantized: List[float] = []
    for value in values:
        magnitude = abs(value)
        if magnitude < dead_zone:
            quantized.append(0.0)
            continue
        if anchor == 0:
            quantized.append(0.0)
            continue
        scaled = magnitude / anchor
        exponent = 0 if scaled <= 0 else round(math.log(scaled, r))
        code_value = anchor * (r ** exponent)
        quantized.append(math.copysign(code_value, value))

    num_bins = 40
    codebook = [anchor * (r ** exp) for exp in range(-num_bins, num_bins + 1)]
    return QuantizerResult(values=quantized, codebook=codebook, step_ratio=r)


def effective_bits_from_bins(bins_per_decade: float) -> float:
    return math.log(bins_per_decade, 2)


def delta_bits_vs_linear(baseline_bits: float, bins_per_decade: float) -> float:
    eff_bits = effective_bits_from_bins(bins_per_decade)
    return max(0.0, baseline_bits - eff_bits)


def quantization_error(values: Iterable[float], quantized_values: Iterable[float]) -> float:
    original = [float(v) for v in values]
    quantized = [float(v) for v in quantized_values]
    if not original:
        return 0.0
    error = [(o - q) ** 2 for o, q in zip(original, quantized)]
    return sum(error) / len(error)


__all__ = [
    "QuantizerResult",
    "linear_quantize",
    "log_quantize",
    "log_step_ratio",
    "effective_bits_from_bins",
    "delta_bits_vs_linear",
    "quantization_error",
]
