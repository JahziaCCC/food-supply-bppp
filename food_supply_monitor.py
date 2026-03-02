import os
import json
import datetime as dt
from typing import Dict, Optional, List, Tuple

from sources import (
    KSA_TZ,
    get_commodities_catalog,
    fetch_price_history_approx_7d,
    get_geopolitical_signal,
    compute_logistics_pressure_from_ais,
)
from scoring import compute_risk_index, compute_level_from_index, compute_trend
from narrative import (
    fmt_pct,
    commodity_status_from_pct,
    build_operational_reading,
    build_early_warning_rules,
    build_scenarios,
)
from telegram_utils import send_telegram


STATE_FILE = "food_supply_state.json"


def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def pick_top_pressures(pct_map: Dict[str, Optional[float]], name_map: Dict[str, str], k: int = 3) -> List[str]:
    items = [(key, pct) for key, pct in pct_map.items() if pct is not None]
    items.sort(key=lambda x: x[1], reverse=True)
    top = []
    for key, pct in items[:k]:
        _emoji, label = commodity_status_from_pct(pct)
        top.append(f"{name_map.get(key, key)} ({label} {fmt_pct(pct)})")
    return top


def fmt_header(now_ksa: dt.datetime) -> str:
    return "\n".join([
        "🍞📦 رصد سلاسل إمداد الغذاء - المملكة العربية السعودية",
        f"🕒 {now_ksa.strftime('%Y-%m-%d %H:%M')} KSA",
        "",
        "════════════════════",
    ])


def build_report() -> Tuple[str, int]:
    now_ksa = dt.datetime.now(tz=KSA_TZ)

    # AIS summary (اختياري)
    ais_summary = None
    if os.getenv("AIS_SUMMARY_JSON"):
        try:
            ais_summary = json.loads(os.getenv("AIS_SUMMARY_JSON", "{}"))
        except Exception:
            ais_summary = None
    logistics_index, logistics_note = compute_logistics_pressure_from_ais(ais_summary)

    # حرارة المخاطر من الأخبار
    geo = get_geopolitical_signal()
    geo_heat = int(geo["heat"])
    geo_details = geo["details"]

    catalog = get_commodities_catalog()

    pct_7d: Dict[str, Optional[float]] = {}
    name_map: Dict[str, str] = {}

    for item in catalog:
        key = item["key"]
        name_map[key] = item["name_ar"]
        _latest, _old, pct, _src_note = fetch_price_history_approx_7d(item)
        pct_7d[key] = pct

    # حساب المؤشر الموحد
    risk_idx, _drivers, triggers = compute_risk_index(pct_7d, logistics_index, geo_heat)
    level, level_label = compute_level_from_index(risk_idx)

    # الاتجاه مقارنة بالسابق
    state = load_state()
    prev_idx = state.get("prev_risk_index")
    trend_symbol, trend_delta = compute_trend(prev_idx, risk_idx)

    # أعلى الضغوط
    top_pressures = pick_top_pressures(pct_7d, name_map, k=3)

    # القراءة التشغيلية
    reading = build_operational_reading(level, top_pressures, triggers)

    # بناء التقرير
    lines = []
    lines.append(fmt_header(now_ksa))

    # 1) التقييم التنفيذي
    lines.append("📊 التقييم التنفيذي")
    lines.append("")
    lines.append(f"📌 مستوى الخطر: {level_label}")
    lines.append(f"📈 مؤشر ضغط الإمداد الموحد: {risk_idx}/100")
    lines.append(f"📊 الاتجاه: {trend_symbol} ({trend_delta:+d})" if prev_idx is not None else f"📊 الاتجاه: {trend_symbol} (+0)")
    lines.append("")
    lines.append("🧠 القراءة التشغيلية:")
    lines.append(reading)
    lines.append("")
    lines.append("════════════════════")

    # 2) رادار المخاطر العالمية
    lines.append("🌍 رادار المخاطر العالمية")
    lines.append("")
    lines.append(f"📊 مؤشر حرارة المخاطر: {geo_heat}/100")
    for d in geo_details[:3]:
        lines.append(f"• {d}".replace("N/A", "غير متاح"))
    lines.append("")
    lines.append("════════════════════")

    # 3) ضغط سلاسل النقل
    lines.append("🚢 ضغط سلاسل النقل")
    lines.append("")
    lines.append(f"📊 مؤشر ضغط النقل: {logistics_index}/100")
    lines.append(f"ℹ️ {logistics_note}".replace("Baseline (no AIS feed)", "لا توجد تغذية AIS حالياً (خط أساس)"))
    lines.append("")
    lines.append("════════════════════")

    # 4) مصفوفة السلع
    lines.append("📦 مصفوفة السلع الاستراتيجية (7 أيام)")
    lines.append("")
    for item in catalog:
        key = item["key"]
        p = pct_7d.get(key)
        emoji, label = commodity_status_from_pct(p)
        lines.append(f"{emoji} {name_map[key]}: {label} | {fmt_pct(p)} (7d)")
    lines.append("")
    lines.append("════════════════════")

    # 5) أعلى الضغوط
    lines.append("🏷️ أعلى السلع ضغطاً (7 أيام)")
    if top_pressures:
        for i, t in enumerate(top_pressures, 1):
            lines.append(f"{i}️⃣ {t}")
    else:
        lines.append("• لا توجد بيانات كافية لترتيب الضغوط.")
    lines.append("")
    lines.append("════════════════════")

    # 6) محرك الإنذار المبكر
    lines.append(build_early_warning_rules())
    lines.append("")
    lines.append("════════════════════")

    # 7) تحليل السيناريوهات
    corn_pct = pct_7d.get("corn")
    lines.append(build_scenarios(level, logistics_index, geo_heat, corn_pct))
    lines.append("")
    lines.append("════════════════════")

    # 8) توصية غرفة العمليات
    lines.append("🧭 توصية غرفة العمليات")
    lines.append("")
    if level == 1:
        lines.append("• استمرار الرصد الأسبوعي حسب الجدولة.")
        lines.append("• رفع التنبيه عند تغيرات ≥ +5% خلال 7 أيام.")
    elif level == 2:
        lines.append("• رفع المتابعة إلى مستوى نصف أسبوعي مؤقتاً.")
        lines.append("• مراقبة الذرة/الأعلاف كإشارة مبكرة.")
    else:
        lines.append("• رفع الجاهزية إلى مستوى (3) وتفعيل متابعة مكثفة.")
        lines.append("• مراجعة البدائل اللوجستية وخطط الاستمرارية.")
    lines.append("")

    # حفظ الحالة
    state["prev_risk_index"] = risk_idx
    state["last_run_ksa"] = now_ksa.isoformat()
    save_state(state)

    return "\n".join(lines), level


def main() -> None:
    bot = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    report, _level = build_report()
    print(report)

    if bot and chat_id:
        send_telegram(bot, chat_id, report)


if __name__ == "__main__":
    main()
