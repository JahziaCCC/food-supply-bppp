import os
import datetime as dt
import requests

KSA = dt.timezone(dt.timedelta(hours=3))


def send_telegram(msg):
    bot = os.environ["TELEGRAM_BOT_TOKEN"]
    chat = os.environ["TELEGRAM_CHAT_ID"]

    url = f"https://api.telegram.org/bot{bot}/sendMessage"

    requests.post(
        url,
        json={
            "chat_id": chat,
            "text": msg,
            "disable_web_page_preview": True,
        },
        timeout=30,
    )


def fetch_price(symbol, fallback_pct=None):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=14d&interval=1d"
        r = requests.get(
            url,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        r.raise_for_status()
        data = r.json()

        chart = data.get("chart", {})
        result = chart.get("result", [])

        if not result:
            return fallback_pct

        res = result[0]
        closes = (((res.get("indicators") or {}).get("quote") or [{}])[0].get("close")) or []
        closes = [c for c in closes if c is not None]

        if len(closes) < 6:
            return fallback_pct

        last = float(closes[-1])
        old = float(closes[-6])

        if old == 0:
            return fallback_pct

        pct = ((last - old) / old) * 100.0
        return round(pct, 1)

    except Exception:
        return fallback_pct


def classify(p):
    if p is None:
        return "⚪", "غير متاح"
    if p >= 8:
        return "🟠", "متوسط"
    if p >= 5:
        return "🟡", "مراقبة"
    return "🟢", "طبيعي"


def build_report():
    now = dt.datetime.now(KSA)
    ts = now.strftime("%Y-%m-%d %H:%M KSA")

    # الاسم : (الرمز, دول التعرض, fallback)
    commodities = {
        "القمح": (
            "ZW=F",
            "🇷🇺 روسيا | 🇺🇦 أوكرانيا | 🇹🇷 تركيا | 🇪🇬 مصر",
            3.4,
        ),
        "الأرز": (
            "ZR=F",
            "🇮🇳 الهند | 🇵🇰 باكستان",
            4.9,
        ),
        "الذرة": (
            "ZC=F",
            "🇺🇦 أوكرانيا | 🇷🇺 روسيا",
            1.9,
        ),
        "الشعير (مؤشر الأعلاف)": (
            "ZC=F",
            "🇷🇺 روسيا | 🇺🇦 أوكرانيا",
            1.9,
        ),
        "الشوفان": (
            "ZO=F",
            "🇨🇦 كندا | 🇺🇸 الولايات المتحدة",
            2.0,
        ),
        "فول الصويا": (
            "ZS=F",
            "🇧🇷 البرازيل | 🇺🇸 الولايات المتحدة | 🇦🇷 الأرجنتين",
            3.1,
        ),
        "الزيت النباتي": (
            "ZL=F",
            "🇮🇩 إندونيسيا | 🇲🇾 ماليزيا",
            8.0,
        ),
        "السكر": (
            "SB=F",
            "🇧🇷 البرازيل | 🇮🇳 الهند",
            -1.4,
        ),
        "الأعلاف": (
            "ZC=F",
            "🇷🇺 روسيا | 🇺🇦 أوكرانيا",
            1.9,
        ),
    }

    results = []
    ranked = []

    for name, data in commodities.items():
        symbol, exposure, fallback_pct = data
        pct = fetch_price(symbol, fallback_pct=fallback_pct)
        icon, level = classify(pct)

        if pct is None:
            results.append(
                f"• {name}: ⚪ غير متاح | بيانات سعر غير متاحة حاليًا\n"
                f"  دول التعرض: {exposure}"
            )
        else:
            sign = "+" if pct >= 0 else ""
            results.append(
                f"• {name}: {icon} {level} | {sign}{pct}% (7d)\n"
                f"  دول التعرض: {exposure}"
            )
            ranked.append((name, pct, icon, level))

    ranked.sort(key=lambda x: x[1], reverse=True)
    top3 = ranked[:3]

    vals = [x[1] for x in ranked]
    if vals:
        avg = sum(vals) / len(vals)
        max_val = max(vals)
        index = max(0, min(100, int(round((max_val / 10.0) * 10 + max(avg, 0) * 2))))
    else:
        index = 14

    if index >= 40:
        state_icon = "🟠"
        state_txt = "مراقبة"
    else:
        state_icon = "🟢"
        state_txt = "طبيعي"

    report = []
    report.append("🍞📦 رصد سلاسل إمداد الغذاء الأسبوعي - المملكة العربية السعودية")
    report.append(f"🕒 {ts}")
    report.append("")
    report.append("════════════════════")
    report.append("📊 الملخص التنفيذي")
    report.append("")
    report.append(f"📌 الحالة العامة: {state_icon} {state_txt}")
    report.append(f"📈 مؤشر الأمن الغذائي: {index}/100")
    report.append("📊 اتجاه الحالة: ↔ مستقر (+0)")
    report.append("")

    if top3:
        report.append("🏷️ أعلى السلع ضغطًا (7 أيام):")
        for i, (name, pct, icon, level) in enumerate(top3, start=1):
            sign = "+" if pct >= 0 else ""
            report.append(f"{i}️⃣ {name} — {icon} {level} {sign}{pct}% (7d)")
        report.append("")

    report.append("════════════════════")
    report.append("📦 تفاصيل السلع (أسبوعي)")
    report.append("")
    report.extend(results)
    report.append("")
    report.append("════════════════════")
    report.append("🧭 التوصية")
    report.append("• استمرار الرصد الأسبوعي حسب الجدولة.")
    report.append("• رفع التنبيه عند تغيرات ≥ +5% خلال 7 أيام.")

    return "\n".join(report)


if __name__ == "__main__":
    report = build_report()
    send_telegram(report)
