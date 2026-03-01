from dataclasses import dataclass
from typing import Dict, Optional, List, Tuple


@dataclass
class RiskResult:
    level: int
    level_label: str
    risk_index: int
    trend_symbol: str
    trend_delta: int
    logistics_index: int
    geo_heat: int
    drivers: List[str]
    triggers_fired: List[str]


def clamp(n: float, lo: int = 0, hi: int = 100) -> int:
    return int(max(lo, min(hi, round(n))))


def compute_level_from_index(idx: int) -> Tuple[int, str]:
    if idx >= 70:
        return 3, "🔴 مرتفع"
    if idx >= 40:
        return 2, "🟠 متوسط"
    return 1, "🟢 منخفض"


def compute_risk_index(
    commodities_pct_7d: Dict[str, Optional[float]],
    logistics_index: int,
    geo_heat: int,
) -> Tuple[int, List[str], List[str]]:
    pct_values = [v for v in commodities_pct_7d.values() if v is not None]
    drivers = []
    triggers = []

    if pct_values:
        avg_pct = sum(pct_values) / len(pct_values)
        max_pct = max(pct_values)

        commodity_score = clamp((avg_pct / 10.0) * 40.0)
        spike_score = clamp((max_pct / 10.0) * 20.0)
        commodity_total = clamp(commodity_score + spike_score, 0, 60)

        drivers.append(f"ضغط السلع: {commodity_total}/60 (متوسط {avg_pct:.1f}% | أعلى {max_pct:.1f}%)")
        if max_pct >= 5.0:
            triggers.append("Commodity spike ≥ +5% (7d)")
    else:
        commodity_total = 10
        drivers.append("ضغط السلع: بيانات ناقصة — baseline 10/60")

    logistics_score = clamp((logistics_index / 100.0) * 20.0)
    drivers.append(f"ضغط النقل: {logistics_score}/20")
    if logistics_index >= 50:
        triggers.append("Logistics pressure high (AIS/Proxy)")

    geo_score = clamp((geo_heat / 100.0) * 20.0)
    drivers.append(f"الضجيج الجيوسياسي: {geo_score}/20")
    if geo_heat >= 60:
        triggers.append("Geopolitical heat elevated (GDELT proxy)")

    risk_index = clamp(commodity_total + logistics_score + geo_score, 0, 100)
    return risk_index, drivers, triggers


def compute_trend(prev_idx: Optional[int], current_idx: int) -> Tuple[str, int]:
    if prev_idx is None:
        return "↔", 0
    delta = current_idx - prev_idx
    if delta >= 5:
        return "↗", delta
    if delta <= -5:
        return "↘", delta
    return "↔", delta
