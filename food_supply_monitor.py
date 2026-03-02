import os
import json
import datetime as dt

from sources import (
    KSA_TZ,
    get_commodities_catalog,
    fetch_price_history_approx_7d,
    get_geopolitical_signal,
    compute_logistics_pressure_from_ais,
)

from scoring import (
    compute_risk_index,
    compute_level_from_index,
    compute_trend,
)

from narrative import (
    commodity_status_from_pct,
    fmt_pct,
    build_operational_reading,
)

from telegram_utils import send_telegram


STATE_FILE = "food_state.json"


def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(data):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():

    now = dt.datetime.now(KSA_TZ)
    ts = now.strftime("%Y-%m-%d %H:%M KSA")

    lines = []
    lines.append("🍞📦 رصد سلاسل إمداد الغذاء - المملكة العربية السعودية")
    lines.append(f"🕒 {ts}")
    lines.append("")
    lines.append("════════════════════")

    # ===== السلع =====
    catalog = get_commodities_catalog()

    commodities_pct = {}
    commodity_rows = []

    for item in catalog:

        point, old_price, pct, _ = fetch_price_history_approx_7d(item)

        commodities_pct[item["key"]] = pct

        icon, status = commodity_status_from_pct(pct)
        pct_txt = fmt_pct(pct)

        commodity_rows.append(
            f"{icon} {item['name_ar']}: {status} | {pct_txt} (7d)"
        )

    # ===== رادار المخاطر =====
    geo = get_geopolitical_signal()
    geo_heat = geo["heat"]
    geo_details = geo["details"]

    # ===== النقل =====
    logistics_index, logistics_note = compute_logistics_pressure_from_ais(None)

    # ===== المؤشر الموحد =====
    risk_index, drivers, triggers = compute_risk_index(
        commodities_pct,
        logistics_index,
        geo_heat,
    )

    level_num, level_label = compute_level_from_index(risk_index)

    state = load_state()
    prev_idx = state.get("risk_index")

    trend_arrow, delta = compute_trend(prev_idx, risk_index)

    state["risk_index"] = risk_index
    save_state(state)

    # ===== التقييم التنفيذي =====
    lines.append("📊 التقييم التنفيذي")
    lines.append("")
    lines.append(f"📌 مستوى الخطر: {level_label}")
    lines.append(f"📈 مؤشر ضغط الإمداد الموحد: {risk_index}/100")
    lines.append(f"📊 الاتجاه: {trend_arrow} ({delta:+d})")
    lines.append("")
    lines.append("🧠 القراءة التشغيلية:")
    lines.append(
        build_operational_reading(
            level_num,
            [],
            triggers,
        )
    )

    lines.append("")
    lines.append("════════════════════")

    # ===== رادار المخاطر =====
    lines.append("🌍 رادار المخاطر العالمية")
    lines.append("")
    lines.append(f"📊 مؤشر المخاطر: {geo_heat}/100")

    for d in geo_details[:3]:
        lines.append(f"• {d}")

    lines.append("")
    lines.append("════════════════════")

    # ===== ضغط النقل =====
    lines.append("🚢 ضغط سلاسل النقل")
    lines.append("")
    lines.append(f"📊 مؤشر ضغط النقل: {logistics_index}/100")

    lines.append("")
    lines.append("════════════════════")

    # ===== مصفوفة السلع =====
    lines.append("📦 مصفوفة السلع الاستراتيجية (7 أيام)")
    lines.append("")
    lines.extend(commodity_rows)

    lines.append("")
    lines.append("════════════════════")

    # ===== التوصية =====
    lines.append("🧭 التوصية")
    lines.append("")
    lines.append("• استمرار الرصد الأسبوعي حسب الجدولة.")
    lines.append("• رفع التنبيه عند تغيرات ≥ +5% خلال 7 أيام.")

    msg = "\n".join(lines)

    bot = os.environ["TELEGRAM_BOT_TOKEN"]
    chat = os.environ["TELEGRAM_CHAT_ID"]

    send_telegram(bot, chat, msg)


if __name__ == "__main__":
    main()
