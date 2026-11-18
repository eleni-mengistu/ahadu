"""English is the source language. Arabic is applied to the finished page."""
from __future__ import annotations

import html
import re

from i18n_data import COURSE_TITLES, FACULTY, JS_LITERALS, MONTHS, RECORD_VALUES, SEASONS, UI

AR = {**COURSE_TITLES, **FACULTY, **RECORD_VALUES, **UI}
DATE = r"(?:(Mon|Tue|Wed|Thu|Fri|Sat|Sun|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),? )?(\d{1,2}) ([A-Z][a-z]+) (\d{4})"


def _date(m, offset=0) -> str:
    day, number, month, year = m.group(1 + offset, 2 + offset, 3 + offset, 4 + offset)
    text = f"{number} {MONTHS.get(month, month)} {year}"
    return f"{AR[day]} {text}" if day else text


def _times(n: str) -> str:
    return {"1": "مرة واحدة إضافية", "2": "مرتين إضافيتين"}.get(n, f"{n} مرات إضافية")


GPA_STATE = {"met": "متحقق", "not met": "غير متحقق", "no GPA yet": "لا يوجد معدل بعد"}


PATTERNS = [
    (rf"{DATE}", lambda m, t: _date(m)),
    (rf"{DATE}, (\d\d:\d\d)", lambda m, t: f"{_date(m)}، {m[5]}"),
    (r"(\d{4}) (Fall|Spring|Summer) Semester", lambda m, t: f"فصل {SEASONS[m[2]]} {m[1]}"),
    (r"((?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)(?:, (?:Mon|Tue|Wed|Thu|Fri|Sat|Sun))+)", lambda m, t: "، ".join(AR[d] for d in m[1].split(", "))),
    (r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), (\d\d:\d\d–\d\d:\d\d)", lambda m, t: f"{AR[m[1]]}، {m[2]}"),
    (r"Semester (\d+)", lambda m, t: f"الفصل {m[1]}"),
    (r"Room (.+)", lambda m, t: f"قاعة {m[1]}"),
    (r"Office (.+)", lambda m, t: f"مكتب {m[1]}"),
    (r"Ext\. (.+)", lambda m, t: f"تحويلة {m[1]}"),
    (r"Section (.+)", lambda m, t: f"الشعبة {m[1]}"),
    (r"CRN (.+)", lambda m, t: f"الرقم المرجعي {m[1]}"),
    (r"(AUH|DXB)-Exam Hall (\d+)", lambda m, t: f"{AR[m[1]]} - قاعة الاختبارات {m[2]}"),
    (r"(AUH|DXB) campus", lambda m, t: f"حرم {AR[m[1]]}"),
    (r"(\d+) cr", lambda m, t: f"{m[1]} ساعة"),
    (r"(\d+) credits?", lambda m, t: f"{m[1]} ساعة"),
    (r"of (\d+) credits", lambda m, t: f"من {m[1]} ساعة"),
    (r"(\d+) of (\d+) credits", lambda m, t: f"{m[1]} من {m[2]} ساعة"),
    (r"of (\d+) required", lambda m, t: f"من {m[1]} مطلوبة"),
    (r"(\d+) credits registered", lambda m, t: f"{m[1]} ساعة مسجلة"),
    (r"(\d+) credits earned", lambda m, t: f"{m[1]} ساعة مكتسبة"),
    (r"(\d+) courses", lambda m, t: f"{m[1]} مقررات"),
    (r"(\d+) classes", lambda m, t: f"{m[1]} محاضرات"),
    (r"in (\d+) days", lambda m, t: f"بعد {m[1]} يوم"),
    (r"Opens in (\d+) days", lambda m, t: f"يبدأ بعد {m[1]} يوم"),
    (r"(\d+) / (\d+) credits", lambda m, t: f"{m[1]} / {m[2]} ساعة"),
    (r"(\d+) of (\d+) required credits complete", lambda m, t: f"اكتملت {m[1]} من {m[2]} ساعة مطلوبة"),
    (r"Graduation credits: (\d+) / (\d+)", lambda m, t: f"ساعات التخرج: {m[1]} / {m[2]}"),
    (r"Minimum GPA 2\.00: (met|not met|no GPA yet) \((.+)\)", lambda m, t: f"الحد الأدنى للمعدل 2.00: {GPA_STATE[m[1]]} ({m[2]})"),
    (r"(All|Remaining|In progress|Done) (\d+)", lambda m, t: f"{AR[m[1]]} {m[2]}"),
    (r"Replaced by (.+) in GPA", lambda m, t: f"استبدلت بدرجة {m[1]} في المعدل"),
    (r"Repeat: replaces (.+)", lambda m, t: f"إعادة: تحل محل {m[1]}"),
    (r"Retaking after (.+)", lambda m, t: f"إعادة بعد {m[1]}"),
    (r"(.+) in (\d{4} (?:Fall|Spring|Summer) Semester): must be retaken", lambda m, t: f"{m[1]} في {t(m[2])}: يجب إعادته"),
    (r"([\d.]+) quality points", lambda m, t: f"{m[1]} نقطة جودة"),
    (r"Term GPA is shown as earned that term\. Without the replaced grade it would be ([\d.]+)\.", lambda m, t: f"يظهر المعدل الفصلي كما تحقق في ذلك الفصل. وبدون الدرجة المستبدلة يكون {m[1]}."),
    (r"This is your first semester\. Grades appear here once (.+) is complete\.", lambda m, t: f"هذا فصلك الأول. تظهر الدرجات هنا بعد انتهاء {t(m[1])}."),
    (r"You are not registered in any class for (.+)\.", lambda m, t: f"أنت غير مسجل في أي محاضرة في {t(m[1])}."),
    (r"GPA = sum of \(quality points × credits\) ÷ sum of credits, using grades that count in GPA: ([\d.]+) ÷ (\d+) =", lambda m, t: f"المعدل = مجموع (نقاط الجودة × الساعات) ÷ مجموع الساعات، للدرجات المحتسبة: {m[1]} ÷ {m[2]} ="),
    (r"GPA = sum of \(quality points × credits\) ÷ sum of credits, using grades that count in GPA\. Transfer credits are not included\. When you pass a course you failed earlier, the passing grade replaces the F in your cumulative GPA, and the transcript keeps both\.", lambda m, t: "المعدل = مجموع (نقاط الجودة × الساعات) ÷ مجموع الساعات للدرجات المحتسبة. لا تدخل الساعات المعادلة. وعند النجاح في مقرر رسبت فيه تحل درجة النجاح محل F في المعدل التراكمي، ويبقى كلاهما في السجل."),
    (r"\. Transfer credits are not included\. When you pass a course you failed earlier, the passing grade replaces the F in your cumulative GPA, and the transcript keeps both\.", lambda m, t: ". لا تدخل الساعات المعادلة. وعند النجاح في مقرر رسبت فيه تحل درجة النجاح محل F في المعدل التراكمي، ويبقى كلاهما في السجل."),
    (r"Each requirement of your program is matched to your record\. A passed course or accepted transfer credit is", lambda m, t: "تتم مطابقة كل متطلب في برنامجك مع سجلك. المقرر الناجح أو الساعات المعادلة المقبولة تعد"),
    (r", a course you are registered in this term is", lambda m, t: "، والمقرر المسجل هذا الفصل يعد"),
    (r", and anything else is", lambda m, t: "، وما عدا ذلك يعد"),
    (r"\. Courses outside the named requirements fill your elective slots\. Progress = completed requirement credits ÷ (\d+)\.", lambda m, t: f". وتملأ المقررات الأخرى خانات المقررات الاختيارية. التقدم = الساعات المكتملة ÷ {m[1]}."),
    (r"recorded up to (.+)", lambda m, t: f"مسجل حتى {t(m[1])}"),
    (r"as of (.+)", lambda m, t: f"حتى {t(m[1])}"),
    (r"across (\d+) classes", lambda m, t: f"في {m[1]} مقررات"),
    (r"(\d+) of (\d+) meetings held", lambda m, t: f"عقد {m[1]} من {m[2]} لقاء"),
    (r"(\d+) absences of (\d+) meetings", lambda m, t: f"{m[1]} غياب من {m[2]} لقاء"),
    (r"You can miss (\d+) more class(?:es)? and stay within 15%\.", lambda m, t: f"يمكنك الغياب {_times(m[1])} مع البقاء ضمن 15%."),
    (r"Over the limit by (\d+) absences?\.", lambda m, t: f"تجاوزت الحد بعدد {m[1]} غياب."),
    (r"Appeal: (.+?)\.?", lambda m, t: f"التظلم: {t(m[1])}."),
    (r"Attendance appeal: (.+?)\.", lambda m, t: f"تظلم الحضور: {t(m[1])}."),
    (r"(\S+) is over the 15% limit: (.+)", lambda m, t: f"{m[1]} تجاوز حد 15%: {m[2]}"),
    (r"You missed (\d+) of (\d+) meetings\. More than 15% leads to a WF grade, which counts as 0\.0 in your GPA\.", lambda m, t: f"غبت عن {m[1]} من {m[2]} لقاء. تجاوز 15% يؤدي إلى درجة WF التي تحتسب 0.0 في معدلك."),
    (r"(\d+) of (\d+) meetings missed\. Over 15% leads to a WF grade\.( Appeal: (.+)\.)?", lambda m, t: f"غياب {m[1]} من {m[2]} لقاء. تجاوز 15% يؤدي إلى درجة WF." + (f" التظلم: {t(m[4])}." if m[4] else "")),
    (r"(\S+): ([\d.]+%) absences", lambda m, t: f"{m[1]}: غياب {m[2]}"),
    (r"(\S+): second attendance warning", lambda m, t: f"{m[1]}: الإنذار الثاني للغياب"),
    (r"([\d.]+%) absences\. You have reached the limit: one more absence puts you over 15%\.", lambda m, t: f"غياب {m[1]}. وصلت إلى الحد: غياب واحد إضافي يتجاوز 15%."),
    (r"([\d.]+%) absences\. 1 more and you reach the limit\.", lambda m, t: f"غياب {m[1]}. غياب واحد إضافي وتصل إلى الحد."),
    (r"([\d.]+%) absences\. (\d+) more before you pass 15%\.", lambda m, t: f"غياب {m[1]}. يتبقى {m[2]} قبل تجاوز 15%."),
    (r"Registration blocked: (.+) hold", lambda m, t: f"التسجيل محظور: حظر {t(m[1])}"),
    (r"(.+)\. Contact (.+)\.", lambda m, t: f"{t(m[1])}. تواصل مع {t(m[2])}."),
    (r"(.+)\. It does not block registration\.", lambda m, t: f"{t(m[1])}. لا يمنع التسجيل."),
    (r"(Financial|Advising|Library|Registrar) hold", lambda m, t: f"حظر {AR[m[1]]}"),
    (r"Your cumulative GPA is ([\d.–]+), below the 2\.00 minimum\. Talk to your advisor\.", lambda m, t: f"معدلك التراكمي {m[1]} أقل من الحد الأدنى 2.00. تحدث مع مرشدك."),
    (r"You cannot register for (.+) until this hold is released: (.+)\.", lambda m, t: f"لا يمكنك التسجيل في {t(m[1])} حتى يُرفع هذا الحظر: {t(m[2])}."),
    (r"You cannot register for (.+) until these holds are released: (.+)\.", lambda m, t: f"لا يمكنك التسجيل في {t(m[1])} حتى ترفع حالات الحظر: {'، '.join(t(x) for x in m[2].split(', '))}."),
    (r"(.+) time ticket", lambda m, t: f"موعد تسجيل {t(m[1])}"),
    (r"Exam (.+)", lambda m, t: f"الاختبار {t(m[1])}"),
    (r"(\d+)% of the course graded, (\d+)% still to come", lambda m, t: f"تم تقييم {m[1]}% من المقرر، ويتبقى {m[2]}%"),
    (r"Tracking at (.+)", lambda m, t: f"المستوى الحالي {m[1]}"),
    (r"Overlaps (.+)", lambda m, t: f"يتعارض مع {m[1]}"),
    (r"No final exam listed for: (.+)\.", lambda m, t: f"لا يوجد اختبار نهائي مدرج لـ: {m[1]}."),
    (r"(.+) final exams, soonest first", lambda m, t: f"اختبارات {t(m[1])} النهائية، الأقرب أولا"),
    (r"Time conflict:", lambda m, t: "تعارض في الوقت:"),
    (r"(\S+) and (\S+) overlap on (.+)\.", lambda m, t: f"{m[1]} و{m[2]} يتعارضان يوم {t(m[3])}."),
    (r"from today's (.+)", lambda m, t: f"من معدل اليوم {m[1]}"),
    (r"(\d+)h (\d+)m", lambda m, t: f"{m[1]} س {m[2]} د"),
    (r"Next: (.+) at (\d\d:\d\d), (\S+) in (.+)", lambda m, t: f"التالي: {t(m[1])} الساعة {m[2]}، {m[3]} في {m[4]}"),
    (r"(\d+) more in Attendance, Holds and Exams\.", lambda m, t: f"{m[1]} أخرى في الحضور والحظر والاختبارات."),
    (r"Welcome back, (.+)", lambda m, t: f"مرحبا بعودتك، {t(m[1])}"),
    (r"(.+) \| ZU Student Access Portal", lambda m, t: f"{t(m[1])} | بوابة طالب جامعة زايد"),
    (r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)", lambda m, t: MONTHS[m[1]]),
    (r"(\S+) or (\S+)", lambda m, t: f"{m[1]} أو {m[2]}"),
    (r"Zone ([A-C])", lambda m, t: f"المنطقة {m[1]}"),
    (r"(\d+) free spaces", lambda m, t: f"{m[1]} موقفا متاحا"),
    (r"of (\d+) spaces", lambda m, t: f"من {m[1]} موقف"),
    (r"(\d+)% free", lambda m, t: f"{m[1]}% متاح"),
    (r"(\d+) arrivals", lambda m, t: f"{m[1]} وصول"),
    (r"Enter through (.+)", lambda m, t: f"ادخل عبر {t(m[1])}"),
    (r"Best match for your usual (\d\d:\d\d) arrival\.", lambda m, t: f"الأنسب لوصولك المعتاد الساعة {m[1]}."),
    (r"Quietest arrival time: (\d\d:\d\d)", lambda m, t: f"أهدأ وقت للوصول: {m[1]}"),
    (r"(\d+) visits", lambda m, t: f"{m[1]} زيارات"),
    (r"Course reading: (.+)", lambda m, t: f"قراءات مقرر: {t(m[1])}"),
    (r"(\d{1,2}) ([A-Z][a-z]{2})", lambda m, t: f"{m[1]} {MONTHS.get(m[2], m[2])}"),
    (r"Due in (\d+) days", lambda m, t: f"يستحق بعد {m[1]} يوم"),
    (r"(\d+) days overdue", lambda m, t: f"متأخر {m[1]} يوم"),
]
PATTERNS = [(re.compile(p, re.S), fn) for p, fn in PATTERNS]
TOKEN = re.compile(r"""(<script\b.*?</script>|<style\b.*?</style>|<!--.*?-->|<(?:[^<>"']|"[^"]*"|'[^']*')+>)""", re.S | re.I)
ATTR = re.compile(r'\b(placeholder|title|aria-label|alt)="([^"]*)"')
JS_ATTR = re.compile(r'(\s(?:x-text|:aria-label|:placeholder)=")([^"]*)(")')
JS_TEXT = re.compile(r"'([^']*)'")
ISOLATE = re.compile(r"(?<![\w\u2066])([A-Za-z0-9@+][A-Za-z0-9@._:/%+–\-]*[A-Za-z0-9%]|\d)(?![\w\u2069])")


def tr(text: str, lang: str = "ar", names: dict | None = None) -> str:
    if lang != "ar" or not text:
        return text
    table = names or {}

    def t(value: str) -> str:
        value = re.sub(r"\s+", " ", value).strip()
        if value in table:
            return table[value]
        if value in AR:
            return AR[value]
        if " · " in value or value.startswith("· "):
            return " · ".join(t(part) if part else "" for part in re.split(r"\s*·\s*", value))
        for pattern, build in PATTERNS:
            match = pattern.fullmatch(value)
            if match:
                return build(match, t)
        return value

    return t(text)


def _isolate(text: str) -> str:
    return ISOLATE.sub(lambda m: f"\u2066{m[1]}\u2069" if re.search(r"\d", m[1]) else m[1], text)


def _text(token: str, names: dict) -> str:
    if not token.strip():
        return token
    lead = token[: len(token) - len(token.lstrip())]
    tail = token[len(token.rstrip()):]
    source = html.unescape(token.strip())
    return lead + html.escape(_isolate(tr(source, "ar", names)), quote=False) + tail


def _tag(tag: str, names: dict) -> str:
    tag = ATTR.sub(lambda m: f'{m[1]}="{html.escape(tr(html.unescape(m[2]), "ar", names), quote=True)}"', tag)
    def literals(m):
        code = JS_TEXT.sub(lambda s: "'" + JS_LITERALS.get(s[1], s[1]) + "'", m[2])
        return m[1] + code + m[3]
    return JS_ATTR.sub(literals, tag)


def translate_html(page: str, names: dict | None = None) -> str:
    names = names or {}
    out = []
    for index, part in enumerate(TOKEN.split(page)):
        if index % 2 == 0:
            out.append(_text(part, names))
        elif part[:7].lower() == "<script" or part[:6].lower() == "<style" or part.startswith("<!"):
            out.append(part)
        else:
            out.append(_tag(part, names))
    return "".join(out)
