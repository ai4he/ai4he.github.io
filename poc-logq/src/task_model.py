"""Accuracy proxy models mapping bit reductions to task performance."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class AccuracyConfig:
    acc_drop_at_1bit: float
    acc_drop_k: float
    acc_drop_cap: float
    accuracy_curve_path: Optional[Path] = None


class AccuracyModel:
    """Parameterized mapping from ``Δbits`` to accuracy degradation."""

    def __init__(self, config: AccuracyConfig):
        self.config = config
        self._curve: Optional[List[Tuple[float, float]]] = None
        if config.accuracy_curve_path and Path(config.accuracy_curve_path).exists():
            rows: List[Tuple[float, float]] = []
            with Path(config.accuracy_curve_path).open("r", encoding="utf-8") as handle:
                next(handle, None)
                for line in handle:
                    parts = line.strip().split(",")
                    if len(parts) < 2:
                        continue
                    rows.append((float(parts[0]), float(parts[1])))
            rows.sort(key=lambda x: x[0])
            self._curve = rows

    def accuracy_drop_pct(self, delta_bits: float) -> float:
        if delta_bits <= 0:
            return 0.0
        if self._curve is not None:
            return float(self._interp_curve(delta_bits))

        proxy = self.config.acc_drop_at_1bit * (delta_bits / 1.0) ** self.config.acc_drop_k
        return float(min(proxy, self.config.acc_drop_cap))

    def _interp_curve(self, delta_bits: float) -> float:
        assert self._curve is not None
        rows = self._curve
        if delta_bits <= rows[0][0]:
            return max(0.0, min(rows[0][1], self.config.acc_drop_cap))
        if delta_bits >= rows[-1][0]:
            return max(0.0, min(rows[-1][1], self.config.acc_drop_cap))
        for (x0, y0), (x1, y1) in zip(rows, rows[1:]):
            if x0 <= delta_bits <= x1:
                t = (delta_bits - x0) / (x1 - x0)
                value = y0 + t * (y1 - y0)
                return max(0.0, min(value, self.config.acc_drop_cap))
        return max(0.0, min(rows[-1][1], self.config.acc_drop_cap))


__all__ = ["AccuracyConfig", "AccuracyModel"]
