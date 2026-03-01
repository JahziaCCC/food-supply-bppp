import datetime as dt
import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List

import requests


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


def fetch_stooq_close(symbol: str) -> Tuple[Optional[float], Optional[str]]:
    url = f"https://stooq.com/q/l/?s={symbol}&f=sd2t2ohlcv&h&e=csv"
    try:
        txt = _http_get(url)
        lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
        if len(lines) < 2 or "Date" not in lines[0]:
            return None, "Stooq CSV invalid"
        cols = lines[0].split(",")
        vals = lines[1].split(",")
        d = dict(zip(cols, vals))
        close = _safe_float(d.get("Close", ""))
        date = d.get("Date")
        if close is None:
            return None, "Stooq close missing"
        return close, f"Stooq {date}"
    except Exception as e:
        return None, f"Stooq error: {type(e).__name__}"


def fetch_yahoo_chart_close(symbol: str) -> Tuple[Optional[float], Optional[str]]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=10d&interval=1d"
    try:
        r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        data = r.json()
        result = data.get("chart", {}).get("result", [])
        if not result:
            return None, "Yahoo chart empty"
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
            return None, "Yahoo close missing"
        asof = dt.datetime.utcfromtimestamp(last_ts).isoformat() + "Z" if last_ts else None
        return last_close, f"Yahoo {asof or ''}".strip()
    except Exception as e:
        return None, f"Yahoo error: {type(e).__name__}"


def fetch_gdelt_counts(query: str, hours: int = 168) -> Tuple[Optional[int], str]:
    end = dt.datetime.utcnow()
    start = end - dt.timedelta(hours=hours)
    fmt = "%Y%m%d%H%M%S"
    url = (
        "https://api.gdeltproject.org/api/v2/doc/doc"
        f"?query={requests.utils.quote(query)}"
        f"&mode=timelinevolraw&format=json"
        f"&startdatetime={start.strftime(fmt)}&enddatetime={end.strftime(fmt)}"
    )
    try:
        r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        j = r.json()
        timeline = j.get("timeline", [])
        total = 0
        for row in timeline:
            total += int(row.get("value", 0))
        return total, "GDELT"
    except Exception as e:
        return None, f"GDELT error: {type(e).__name__}"


def compute_logistics_pressure_from_ais(aoi_summary: Optional[dict]) -> Tuple[int, str]:
    if not aoi_summary:
        return 12, "Baseline (no AIS feed)"
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
        note = f"AIS msgs={total_msgs} vessels={unique} anomalies={anomalies} stopped={stopped}"
        return score, note
    except Exception:
        return 12, "Baseline (AIS parse failed)"


def get_commodities_catalog() -> List[dict]:
    return [
        {"key": "wheat", "name_ar": "القمح", "stooq": "zw.f", "yahoo": "ZW=F", "exposure": ["🇷🇺 روسيا", "🇺🇦 أوكرانيا", "🇹🇷 تركيا", "🇪🇬 مصر"]},
        {"key": "rice", "name_ar": "الأرز", "stooq": None, "yahoo": "ZR=F", "exposure": ["🇮🇳 الهند", "🇵🇰 باكستان"]},
        {"key": "corn", "name_ar": "الذرة", "stooq": "zc.f", "yahoo": "ZC=F", "exposure": ["🇺🇦 أوكرانيا", "🇷🇺 روسيا"]},
        {"key": "barley", "name_ar": "الشعير", "stooq": None, "yahoo": None, "exposure": ["🇷🇺 روسيا", "🇺🇦 أوكرانيا"]},
        {"key": "veg_oil", "name_ar": "الزيت النباتي", "stooq": None, "yahoo": None, "exposure": ["🇮🇩 إندونيسيا", "🇲🇾 ماليزيا"]},
        {"key": "sugar", "name_ar": "السكر", "stooq": "sb.f", "yahoo": "SB=F", "exposure": ["🇧🇷 البرازيل", "🇮🇳 الهند"]},
        {"key": "milk_powder", "name_ar": "حليب بودرة", "stooq": None, "yahoo": None, "exposure": ["🇳🇿 نيوزيلندا"]},
        {"key": "feed", "name_ar": "الأعلاف", "stooq": "zc.f", "yahoo": "ZC=F", "exposure": ["🇷🇺 روسيا", "🇺🇦 أوكرانيا"]},
    ]


def fetch_latest_price_for_item(item: dict) -> PricePoint:
    name_ar = item["name_ar"]
    currency = "USD"

    if item.get("stooq"):
        p, note = fetch_stooq_close(item["stooq"])
        if p is not None:
            return PricePoint(symbol=item["stooq"], name_ar=name_ar, price=p, currency=currency, source="Stooq", asof_utc=note, note=None)
        stooq_err = note
    else:
        stooq_err = "No Stooq symbol"

    if item.get("yahoo"):
        p, note = fetch_yahoo_chart_close(item["yahoo"])
        if p is not None:
            return PricePoint(symbol=item["yahoo"], name_ar=name_ar, price=p, currency=currency, source="Yahoo", asof_utc=note, note=None)
        yahoo_err = note
    else:
        yahoo_err = "No Yahoo symbol"

    return PricePoint(symbol=item.get("yahoo") or item.get("stooq") or item["key"], name_ar=name_ar, price=None, currency=currency, source="N/A", asof_utc=None, note=f"{stooq_err} | {yahoo_err}")


def fetch_price_history_approx_7d(item: dict) -> Tuple[PricePoint, Optional[float], Optional[float], str]:
    name_ar = item["name_ar"]
    currency = "USD"

    if item.get("yahoo"):
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{item['yahoo']}?range=14d&interval=1d"
        try:
            r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            data = r.json()
            result = data.get("chart", {}).get("result", [])
            if result:
                series = result[0]
                ts = series.get("timestamp", [])
                closes = series.get("indicators", {}).get("quote", [{}])[0].get("close", [])
                pts = [(t, c) for t, c in zip(ts, closes) if c is not None]
                if len(pts) >= 8:
                    latest_t, latest_c = pts[-1]
                    old_t, old_c = pts[-8]
                    latest = PricePoint(
                        symbol=item["yahoo"],
                        name_ar=name_ar,
                        price=float(latest_c),
                        currency=currency,
                        source="Yahoo",
                        asof_utc=dt.datetime.utcfromtimestamp(latest_t).isoformat() + "Z",
                    )
                    old_price = float(old_c)
                    pct = ((latest.price - old_price) / old_price) * 100.0 if old_price else None
                    return latest, old_price, pct, "Yahoo chart(14d)"
        except Exception:
            pass

    latest = fetch_latest_price_for_item(item)
    return latest, None, None, "Fallback latest-only"


def get_geopolitical_signal() -> Dict[str, object]:
    queries = {
        "export_ban": '(export ban OR export restriction OR "export quota") (wheat OR rice OR sugar OR corn)',
        "port_disruption": '("port closure" OR "shipping disruption" OR "vessel attack" OR "strait" OR "blockade") (Red Sea OR Bab el-Mandeb OR Suez OR Hormuz)',
        "black_sea": '(Black Sea) (grain OR wheat OR corn) (shipment OR export)',
    }
    out = {}
    heat = 0
    details = []
    for k, q in queries.items():
        cnt, src = fetch_gdelt_counts(q, hours=168)
        out[k] = {"count": cnt, "src": src}
        if cnt is None:
            details.append(f"{k}: N/A")
            continue
        details.append(f"{k}: {cnt}")
        if k == "export_ban":
            heat += min(40, cnt // 50 * 10)
        elif k == "port_disruption":
            heat += min(40, cnt // 30 * 10)
        else:
            heat += min(20, cnt // 80 * 5)
    heat = max(0, min(100, heat))
    return {"heat": heat, "details": details, "raw": out}
