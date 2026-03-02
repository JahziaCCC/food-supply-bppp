import datetime as dt
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict

import requests


KSA_TZ = dt.timezone(dt.timedelta(hours=3))


@dataclass
class PricePoint:
    symbol: str
    name_ar: str
    price: Optional[float]
    source: str
    asof_utc: Optional[str]


def fetch_yahoo_chart_last_and_7d(symbol: str) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """
    يرجع:
    last_close, close_7d_ago, asof_utc
    """
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=14d&interval=1d"
    try:
        r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        j = r.json()

        result = (j.get("chart") or {}).get("result") or []
        if not result:
            return None, None, None

        s = result[0]
        ts = s.get("timestamp") or []
        closes = (((s.get("indicators") or {}).get("quote") or [{}])[0].get("close")) or []

        pairs = [(int(t), c) for t, c in zip(ts, closes) if c is not None]
        if len(pairs) < 2:
            return None, None, None

        # آخر إغلاق
        last_ts, last_close = pairs[-1]
        asof = dt.datetime.utcfromtimestamp(last_ts).isoformat() + "Z"

        # إغلاق قبل ~7 أيام تداول (تقريباً 5-7 نقاط للخلف حسب عطلات السوق)
        idx_7d = max(0, len(pairs) - 6)
        old_close = float(pairs[idx_7d][1])

        return float(last_close), old_close, asof

    except Exception:
        return None, None, None


def pct_change_7d(symbol: str) -> Tuple[Optional[float], Optional[str]]:
    last_close, old_close, asof = fetch_yahoo_chart_last_and_7d(symbol)
    if last_close is None or old_close is None or old_close == 0:
        return None, asof
    pct = ((last_close - old_close) / old_close) * 100.0
    return pct, asof


def get_commodities_catalog() -> List[Dict]:
    """
    yahoo: رمز Yahoo
    exposure: دول التعرض (تقدر تعدلها)
    """
    return [
        {"key": "wheat", "name_ar": "القمح", "yahoo": "ZW=F",
         "exposure": ["🇷🇺 روسيا", "🇺🇦 أوكرانيا", "🇹🇷 تركيا", "🇪🇬 مصر"]},

        {"key": "rice", "name_ar": "الأرز", "yahoo": "ZR=F",
         "exposure": ["🇮🇳 الهند", "🇵🇰 باكستان"]},

        {"key": "corn", "name_ar": "الذرة", "yahoo": "ZC=F",
         "exposure": ["🇺🇦 أوكرانيا", "🇷🇺 روسيا"]},

        {"key": "barley", "name_ar": "الشعير", "yahoo": None,
         "exposure": ["🇷🇺 روسيا", "🇺🇦 أوكرانيا"]},

        {"key": "veg_oil", "name_ar": "الزيت النباتي", "yahoo": "ZL=F",
         "exposure": ["🇮🇩 إندونيسيا", "🇲🇾 ماليزيا"]},

        {"key": "sugar", "name_ar": "السكر", "yahoo": "SB=F",
         "exposure": ["🇧🇷 البرازيل", "🇮🇳 الهند"]},

        {"key": "milk_powder", "name_ar": "حليب بودرة", "yahoo": None,
         "exposure": ["🇳🇿 نيوزيلندا"]},

        {"key": "feed", "name_ar": "الأعلاف", "yahoo": "ZC=F",
         "exposure": ["🇷🇺 روسيا", "🇺🇦 أوكرانيا"]},
    ]


def classify(pct: Optional[float]) -> Tuple[str, str]:
    if pct is None:
        return "⚪", "غير متاح"
    if pct >= 10:
        return "🔴", "مرتفع"
    if pct >= 5:
        return "🟠", "متوسط"
    return "🟢", "طبيعي"
