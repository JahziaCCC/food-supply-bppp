from typing import Optional, List, Tuple


def fmt_pct(p: Optional[float]) -> str:
    if p is None:
        return "غير متاح"
    sign = "+" if p >= 0 else ""
    return f"{sign}{p:.1f}%"


def commodity_status_from_pct(p: Optional[float]) -> Tuple[str, str]:
    if p is None:
        return "⚪", "غير متاح"
    if p >= 10:
        return "🔴", "مرتفع"
    if p >= 5:
        return "🟠", "متوسط"
    if p >= 0:
        return "🟢", "طبيعي"
    return "🟢", "طبيعي"


def build_ai_insight(level: int, top_pressures: List[str], triggers: List[str]) -> str:
    if level == 1:
        if top_pressures:
            return f"المؤشرات تشير إلى استقرار عام مع ضغط محدود في: {', '.join(top_pressures)}. لا توجد إشارات تستدعي رفع الجاهزية."
        return "لا توجد مؤشرات اضطراب مؤثرة على الإمدادات خلال 7 أيام القادمة."
    if level == 2:
        base = "تم رصد ضغوط متوسطة قد تؤثر على تكلفة بعض السلع دون مؤشرات نقص فوري."
        if triggers:
            base += f" (محفزات: {', '.join(triggers[:2])})"
        return base
    return "يوجد ضغط مرتفع واحتمالات تعطّل/تأخير؛ يُوصى برفع الجاهزية وتفعيل المتابعة المكثفة."


def build_scenarios(level: int, logistics_index: int, geo_heat: int, corn_pct: Optional[float]) -> str:
    lines = []
    lines.append("🧩 تحليل السيناريوهات المحتملة (Impact Simulation)")
    lines.append("")
    lines.append("🟢 السيناريو الأساسي:")
    lines.append("• استمرار الاستقرار العالمي")
    lines.append("• لا تأثير تشغيلي مباشر على الإمدادات الوطنية")
    lines.append("")
    lines.append("🟠 سيناريو ضغط متوسط:")
    assumed_corn = corn_pct if corn_pct is not None else 7.0
    lines.append(f"• ارتفاع الذرة ~ {assumed_corn:.1f}% خلال 7 أيام")
    lines.append("• التأثير المتوقع:")
    lines.append("  - زيادة تكلفة الأعلاف")
    lines.append("  - ضغط محدود على قطاع الثروة الحيوانية")
    lines.append("  - لا مؤشرات نقص إمدادات")
    lines.append("")
    lines.append("🔴 سيناريو عالي الخطورة:")
    if logistics_index >= 50 or geo_heat >= 60 or level >= 2:
        lines.append("• تعطّل/تباطؤ في مسار بحري رئيسي أو قيود تصدير")
    else:
        lines.append("• تعطّل مفاجئ في ممر بحري رئيسي (افتراضي)")
    lines.append("• التأثير المتوقع:")
    lines.append("  - تأخير الشحن 7–10 أيام (تقديري)")
    lines.append("  - ارتفاع تكاليف النقل")
    lines.append("  - رفع الجاهزية إلى Level 2")
    return "\n".join(lines)


def build_early_warning_rules() -> str:
    return "\n".join([
        "🚨 محرك الإنذار المبكر (Auto Triggers)",
        "",
        "⚠️ يتحول التقرير تلقائياً إلى Level 2 عند تحقق أي شرط:",
        "• ارتفاع ≥ +5% في أي سلعة خلال 7 أيام",
        "• ارتفاع الضجيج الجيوسياسي ≥ 60/100 (مؤشر أخبار)",
        "• ارتفاع ضغط النقل ≥ 50/100 (AIS/Proxy)",
        "• تكرار إشارات قيود تصدير بشكل ملحوظ",
    ])
