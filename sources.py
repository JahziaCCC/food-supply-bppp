import datetime as dt
import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List

import requests


# ===== توقيت السعودية =====
KSA_TZ = dt.timezone(dt.timedelta(hours=3))


@dataclass
class PricePoint:
    symbol: str
    name_ar: str
    price: Optional[float]
    currency: str
    source: str
    asof_utc: Optional[str]
    note: Optional[str] = None


def _safe_float(x: str) -> Optional[float]:
    try:
        v = float(x)
        if math.isfinite(v):
            return v
        return None
    except Exception:
        return None


def _http_get(url: str, timeout: int = 30) -> str:
    r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return r.text


def fetch_yahoo_chart_close(symbol: str) -> Tuple[Optional[float], Optional[str]]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=10d&interval=1d"

    try:
        r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        data = r.json()

        result = data.get("chart", {}).get("result", [])
        if not result:
            return None, "غير متاح"

        series = result[0]
        ts = series.get("timestamp", [])
        closes = series.get("indicators", {}).get("quote", [{}])[0].get("close", [])

        last_close = None
        last_ts = None

        for t, c in zip(ts, closes):
            if c is not None:
                last_close = float(c)
                last_ts = int(t)

        if last_close is None:
            return None, "غير متاح"

        asof = dt.datetime.utcfromtimestamp(last_ts).isoformat() + "Z"
        return last_close, asof

    except Exception:
        return None, "غير متاح"


def fetch_gdelt_counts(query: str, hours: int = 168) -> Tuple[Optional[int], str]:
    end = dt.datetime.utcnow()
    start = end - dt.timedelta(hours=hours)
    fmt = "%Y%m%d%H%M%S"

    url = (
        "https://api.gdeltproject.org/api/v2/doc/doc"
        f"?query={requests.utils.quote(query)}"
        f"&mode=timelinevolraw&format=json"
        f"&startdatetime={start.strftime(fmt)}"
        f"&enddatetime={end.strftime(fmt)}"
    )

    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        j = r.json()

        timeline = j.get("timeline", [])
        total = sum(int(x.get("value", 0)) for x in timeline)

        return total, "متاح"

    except Exception:
        return None, "غير متاح"


def compute_logistics_pressure_from_ais(aoi_summary: Optional[dict]) -> Tuple[int, str]:
    if not aoi_summary:
        return 12, "لا توجد تغذية AIS حالياً (خط أساس)"

    try:
        total_msgs = int(aoi_summary.get("total_messages", 0))
        unique = int(aoi_summary.get("unique_vessels", 0))
        anomalies = int(aoi_summary.get("speed_anomalies", 0))
        stopped = int(aoi_summary.get("stopped", 0))

        score = 0
        score += min(30, unique // 10 * 5)
        score += min(40, anomalies // 5 * 10)
        score += min(30, stopped // 3 * 7)

        score = max(0, min(100, score))

        note = f"رسائل={total_msgs} | سفن={unique} | شذوذ سرعة={anomalies} | توقف={stopped}"
        return score, note

    except Exception:
        return 12, "تعذر تفسير بيانات AIS (خط أساس)"


def get_commodities_catalog() -> List[dict]:
    return [
        {"key": "wheat", "name_ar": "القمح", "yahoo": "ZW=F"},
        {"key": "rice", "name_ar": "الأرز", "yahoo": "ZR=F"},
        {"key": "corn", "name_ar": "الذرة", "yahoo": "ZC=F"},
        {"key": "barley", "name_ar": "الشعير", "yahoo": None},
        {"key": "veg_oil", "name_ar": "الزيت النباتي", "yahoo": None},
        {"key": "sugar", "name_ar": "السكر", "yahoo": "SB=F"},
        {"key": "milk_powder", "name_ar": "حليب بودرة", "yahoo": None},
        {"key": "feed", "name_ar": "الأعلاف", "yahoo": "ZC=F"},
    ]


# ===== النسخة النهائية (تعطي قيم 7 أيام) =====
def fetch_price_history_approx_7d(item: dict):

    latest_price = None
    past_price = None

    # المصدر الأساسي
    if item.get("yahoo"):
        p, _ = fetch_yahoo_chart_close(item["yahoo"])
        latest_price = p

    # fallback احتياطي
    if latest_price is None:

        fallback = {
            "wheat": (540, 520),
            "rice": (15, 14.8),
            "corn": (430, 410),
            "barley": (280, 275),
            "veg_oil": (920, 910),
            "sugar": (22, 22.4),
            "milk_powder": (3200, 3150),
            "feed": (430, 410),
        }

        vals = fallback.get(item["key"])

        if vals:
            latest_price, past_price = vals

    point = PricePoint(
        symbol=item["key"],
        name_ar=item["name_ar"],
        price=latest_price,
        currency="USD",
        source="Fallback" if latest_price else "غير متاح",
        asof_utc=None,
    )

    return point, latest_price, past_price, "approx"


def get_geopolitical_signal() -> Dict[str, object]:
    queries = {
        "قيود التصدير": "export ban wheat rice",
        "تعطل الموانئ والشحن": "port closure shipping disruption",
        "البحر الأسود": "black sea grain export",
    }

    heat = 0
    details = []

    for label, q in queries.items():
        cnt, _ = fetch_gdelt_counts(q)

        if cnt is None:
            details.append(f"{label}: غير متاح")
            continue

        details.append(f"{label}: {cnt}")

        if label == "قيود التصدير":
            heat += min(40, cnt // 50 * 10)
        elif label == "تعطل الموانئ والشحن":
            heat += min(40, cnt // 30 * 10)
        else:
            heat += min(20, cnt // 80 * 5)

    heat = max(0, min(100, heat))

    return {"heat": heat, "details": details}
