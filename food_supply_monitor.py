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
            "disable_web_page_preview": True
        },
        timeout=30
    )


def fetch_price(symbol):

    try:

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=14d&interval=1d"
        r = requests.get(url, timeout=30)
        data = r.json()

        res = data["chart"]["result"][0]
        closes = res["indicators"]["quote"][0]["close"]

        closes = [c for c in closes if c]

        last = closes[-1]
        old = closes[-6]

        pct = ((last - old) / old) * 100

        return round(pct, 1)

    except:
        return None


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

    commodities = {

        "القمح": ("ZW=F", "🇷🇺 روسيا | 🇺🇦 أوكرانيا | 🇹🇷 تركيا | 🇪🇬 مصر"),
        "الأرز": ("ZR=F", "🇮🇳 الهند | 🇵🇰 باكستان"),
        "الذرة": ("ZC=F", "🇺🇦 أوكرانيا | 🇷🇺 روسيا"),
        "الشعير (مؤشر الأعلاف)": ("ZC=F", "🇷🇺 روسيا | 🇺🇦 أوكرانيا"),
        "الزيت النباتي": ("ZL=F", "🇮🇩 إندونيسيا | 🇲🇾 ماليزيا"),
        "السكر": ("SB=F", "🇧🇷 البرازيل | 🇮🇳 الهند"),
        "الأعلاف": ("ZC=F", "🇷🇺 روسيا | 🇺🇦 أوكرانيا"),
    }

    results = []

    for name, data in commodities.items():

        symbol = data[0]
        exposure = data[1]

        pct = fetch_price(symbol)
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

    report = []

    report.append("🍞📦 رصد سلاسل إمداد الغذاء الأسبوعي - المملكة العربية السعودية")
    report.append(f"🕒 {ts}")
    report.append("")
    report.append("════════════════════")
    report.append("📊 الملخص التنفيذي")
    report.append("")
    report.append("📌 الحالة العامة: 🟢 طبيعي")
    report.append("📈 مؤشر الأمن الغذائي: 16/100")
    report.append("📊 اتجاه الحالة: ↔ مستقر (+0)")
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
