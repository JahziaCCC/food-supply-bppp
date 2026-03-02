import datetime as dt
from typing import Optional, List, Tuple

from sources import KSA_TZ, get_commodities_catalog, pct_change_7d, classify


def fmt_pct(p: Optional[float]) -> str:
    if p is None:
        return "غير متاح"
    sign = "+" if p >= 0 else ""
    return f"{sign}{p:.1f}%"


def trend_arrow(delta: Optional[float]) -> Tuple[str, str]:
    if delta is None:
        return "↔", "مستقر"
    if delta >= 0.5:
        return "↑", "يتدهور"
    if delta <= -0.5:
        return "↓", "يتحسن"
    return "↔", "مستقر"


def build_report():
    now = dt.datetime.now(KSA_TZ)
    ts = now.strftime("%Y-%m-%d %H:%M KSA")

    catalog = get_commodities_catalog()

    # ===== نجمع نسب 7 أيام =====
    rows = []
    pct_map = {}

    for item in catalog:
        pct = None
        if item.get("yahoo"):
            pct, _ = pct_change_7d(item["yahoo"])
        pct_map[item["key"]] = pct

        icon, level = classify(pct)
        rows.append((item, icon, level, pct))

    # ===== مؤشر بسيط (0-100) =====
    # نحسب متوسط النسب المتاحة (نطاق حساس)
    vals = [v for v in pct_map.values() if v is not None]
    if vals:
        avg = sum(vals) / len(vals)
        # تحويل تقريبي إلى 0-100
        index = max(0, min(100, int(round((avg / 10.0) * 50))))
    else:
        index = 14

    # ===== الحالة العامة =====
    if index >= 40:
        state_icon = "🟠"
        state_txt = "مراقبة"
    else:
        state_icon = "🟢"
        state_txt = "طبيعي"

    # اتجاه الحالة (مبسط: بدون State file هنا)
    arrow, trend_txt = "↔", "مستقر"
    delta_txt = "(+0)"

    # ===== أعلى 3 ضغوط =====
    ranked = [(it["name_ar"], p) for (it, _, _, p) in rows if p is not None]
    ranked.sort(key=lambda x: x[1], reverse=True)
    top3 = ranked[:3]

    lines = []
    lines.append("🍞📦 رصد سلاسل إمداد الغذاء (B++ أسبوعي – Level 1) – المملكة العربية السعودية")
    lines.append(f"🕒 {ts}")
    lines.append("")
    lines.append("════════════════════")
    lines.append("📊 الملخص التنفيذي")
    lines.append("")
    lines.append(f"📌 الحالة العامة: {state_icon} {state_txt}")
    lines.append(f"📈 مؤشر الأمن الغذائي: {index}/100")
    lines.append(f"📊 اتجاه الحالة: {arrow} {trend_txt} {delta_txt}")
    lines.append("")
    lines.append("🏷️ أعلى السلع ضغطًا (7 أيام):")

    if top3:
        for i, (name, p) in enumerate(top3, start=1):
            icon, lvl = classify(p)
            lines.append(f"{i}️⃣ {name} — {icon} {lvl} {fmt_pct(p)} (7d)")
    else:
        lines.append("• لا توجد بيانات كافية حالياً.")

    lines.append("")
    lines.append("════════════════════")
    lines.append("📦 تفاصيل السلع (أسبوعي)")
    lines.append("")

    for item, icon, level, pct in rows:
        name = item["name_ar"]
        exposure = " | ".join(item.get("exposure", []))

        if pct is None:
            lines.append(f"• {name}: ⚪ غير متاح | بيانات سعر غير متاحة حاليًا")
            lines.append(f"  السبب: تعذر جلب بيانات السعر من المصدر المتاح حاليًا")
            lines.append(f"  دول التعرض: {exposure}" if exposure else "  دول التعرض: غير محدد")
        else:
            lines.append(f"• {name}: {icon} {level} | {fmt_pct(pct)} (7d) | ↔ مستقر (+0.0%)")
            lines.append(f"  دول التعرض: {exposure}" if exposure else "  دول التعرض: غير محدد")

    lines.append("")
    lines.append("════════════════════")
    lines.append("🧭 التوصية")
    lines.append("• استمرار الرصد الأسبوعي حسب الجدولة.")
    lines.append("• رفع التنبيه عند تغيرات ≥ +5% خلال 7 أيام.")

    return "\n".join(lines)


if __name__ == "__main__":
    print(build_report())
