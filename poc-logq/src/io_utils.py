"""Utilities for loading configuration and optional CSV inputs."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Tuple

import csv
import json
import ast

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - fallback parser
    yaml = None


@dataclass
class LayerProfile:
    layer: str
    fs_ksps: float
    n_channels: int
    dynamic_range_min: float
    dynamic_range_max: float
    weight: float


def load_config(path: Path) -> Dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text)
    return _parse_simple_yaml(text)


def dump_yaml(data: Dict[str, Any], path: Path) -> None:
    if yaml is not None:
        with Path(path).open("w", encoding="utf-8") as handle:
            yaml.safe_dump(data, handle)
    else:
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def _parse_simple_yaml(text: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value.lower() in {"true", "false"}:
            result[key] = value.lower() == "true"
        else:
            try:
                result[key] = ast.literal_eval(value)
            except Exception:
                result[key] = value
    return result


def load_layer_profiles(path: Path) -> Tuple[list[LayerProfile], float]:
    profiles: list[LayerProfile] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required_cols = {"layer", "fs_ksps", "n_channels", "dynamic_range_min", "dynamic_range_max", "weight"}
        if not required_cols.issubset(reader.fieldnames or set()):
            missing = required_cols - set(reader.fieldnames or [])
            raise ValueError(f"layer_profiles missing columns: {missing}")
        for row in reader:
            profiles.append(
                LayerProfile(
                    layer=row["layer"],
                    fs_ksps=float(row["fs_ksps"]),
                    n_channels=int(row["n_channels"]),
                    dynamic_range_min=float(row["dynamic_range_min"]),
                    dynamic_range_max=float(row["dynamic_range_max"]),
                    weight=float(row["weight"]),
                )
            )
    total_weight = sum(profile.weight for profile in profiles)
    if total_weight <= 0:
        raise ValueError("layer_profiles weights must sum to positive value")
    return profiles, total_weight


__all__ = ["load_config", "dump_yaml", "load_layer_profiles", "LayerProfile"]
