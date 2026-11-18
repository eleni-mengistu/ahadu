"""Real, selectable PDF exports in English or Arabic."""
from __future__ import annotations

import io
import re
from pathlib import Path
from xml.sax.saxutils import escape

import arabic_reshaper
from bidi import get_display
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

import i18n
import portal_data as data

BASE_DIR = Path(__file__).resolve().parent
BRAND = colors.HexColor("#8E2A42")
SOFT = colors.HexColor("#FAECEF")
LINE = colors.HexColor("#E8D9DD")
MUTED = colors.HexColor("#6B5B60")
INK = colors.HexColor("#2B181E")
DANGER = colors.HexColor("#B91C1C")
MARGIN = 16 * mm
WIDTH = A4[0] - 2 * MARGIN
TITLES = {
    "summary": "Student summary", "transcript": "Academic transcript", "audit": "Degree audit",
    "schedule": "Class schedule", "attendance": "Attendance report", "holds": "Holds report",
    "exams": "Exam schedule",
}
FONT_CANDIDATES = [("segoeui.ttf", "segoeuib.ttf"), ("tahoma.ttf", "tahomabd.ttf"), ("arial.ttf", "arialbd.ttf")]


def register_fonts() -> tuple[str, str]:
    if "ZU" in pdfmetrics.getRegisteredFontNames():
        return "ZU", "ZU-Bold"
    for regular, bold in FONT_CANDIDATES:
        r, b = Path("C:/Windows/Fonts") / regular, Path("C:/Windows/Fonts") / bold
        if r.exists() and b.exists():
            pdfmetrics.registerFont(TTFont("ZU", str(r)))
            pdfmetrics.registerFont(TTFont("ZU-Bold", str(b)))
            return "ZU", "ZU-Bold"
    return "Helvetica", "Helvetica-Bold"


class Doc:
    def __init__(self, sid: str, kind: str, lang: str):
        self.d = data.dashboard(sid)
        self.s = self.d["student"]
        self.kind, self.lang = kind, lang
        self.font, self.bold = register_fonts()
        self.names = {self.s["full_name"]: self.s["full_name_ar"]}
        self.story: list = []
        align = TA_RIGHT if self.rtl else TA_LEFT
        self.body = ParagraphStyle("b", fontName=self.font, fontSize=8.6, leading=11.5, textColor=INK, alignment=align)
        self.head = ParagraphStyle("h", parent=self.body, fontName=self.bold, textColor=colors.white)
        self.h2 = ParagraphStyle("h2", parent=self.body, fontName=self.bold, fontSize=11.5, leading=15, textColor=BRAND, spaceBefore=9, spaceAfter=4)
        self.note = ParagraphStyle("n", parent=self.body, textColor=MUTED, fontSize=8, leading=10.5)
        self.stat = ParagraphStyle("s", parent=self.body, fontName=self.bold, fontSize=13, leading=16)

    @property
    def rtl(self) -> bool:
        return self.lang == "ar"

    def t(self, text) -> str:
        return i18n.tr(str(text), self.lang, self.names)

    def visual(self, text: str) -> str:
        if not re.search(r"[\u0600-\u06ff]", text):
            return text
        return get_display(arabic_reshaper.reshape(text))

    def markup(self, text, style: ParagraphStyle, width: float) -> str:
        text = self.t(text)
        if not re.search(r"[\u0600-\u06ff]", text):
            return escape(text)
        lines, current = [], ""
        for word in text.split():
            trial = f"{current} {word}".strip()
            shown = self.visual(trial)
            if current and pdfmetrics.stringWidth(shown, style.fontName, style.fontSize) > width:
                lines.append(current)
                current = word
            else:
                current = trial
        if current:
            lines.append(current)
        return "<br/>".join(escape(self.visual(line)) for line in lines)

    def p(self, text, style=None, width: float = WIDTH) -> Paragraph:
        style = style or self.body
        return Paragraph(self.markup(text, style, width - 1), style)

    def heading(self, text):
        self.story.append(self.p(text, self.h2))

    def para(self, text, style=None):
        self.story.append(self.p(text, style or self.note))
        self.story.append(Spacer(1, 3))

    def stats(self, pairs):
        pairs = list(reversed(pairs)) if self.rtl else pairs
        w = WIDTH / len(pairs)
        cells = [[[self.p(label, self.note, w - 14), self.p(value, self.stat, w - 14)] for label, value in pairs]]
        table = Table(cells, colWidths=[w] * len(pairs))
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), SOFT), ("INNERGRID", (0, 0), (-1, -1), 3, colors.white),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ]))
        self.story += [table, Spacer(1, 6)]

    def table(self, headers, rows, ratios, keep=False):
        total = sum(ratios)
        widths = [WIDTH * r / total for r in ratios]
        order = list(reversed(range(len(headers)))) if self.rtl else list(range(len(headers)))
        grid = [[self.p(headers[i], self.head, widths[i] - 10) for i in order]]
        for row in rows:
            grid.append([self.p(row[i], self.body, widths[i] - 10) for i in order])
        table = Table(grid, colWidths=[widths[i] for i in order], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LINEBELOW", (0, 1), (-1, -1), .4, LINE), ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        self.story.append(KeepTogether([table]) if keep and len(rows) < 14 else table)
        self.story.append(Spacer(1, 7))

    def banner(self, title, text, bad=True):
        color = DANGER if bad else colors.HexColor("#15763A")
        style = ParagraphStyle("banner", parent=self.body, fontName=self.bold, fontSize=10.5, leading=14, textColor=color)
        self.story.append(self.p(title, style))
        if text:
            self.para(text, self.body)

    # ---- documents
    def build_summary(self):
        d, s, r, a = self.d, self.s, self.d["record"], self.d["audit"]
        self.stats([("Cumulative GPA", data_gpa(r["gpa"])), ("Credits earned", r["credits_earned"]), ("Degree progress", f"{a['percent']}%"), ("Holds", len(d["holds"]["active"]))])
        self.table(["Program", "Status", "Academic standing", "Advisor"], [[s["program_name"], s["status"], s["academic_standing"], s["advisor_name"]]], [4, 1.4, 2, 2.2])
        if d["alerts"]:
            self.heading("Needs attention")
            self.table(["Summary", "Note"], [[x["title"], x["text"]] for x in d["alerts"]], [2, 4])
        if d["ticket"]:
            t = d["ticket"]
            self.heading("Registration time ticket")
            self.table(["Term", "Opens", "Closes", "Status"], [[t["term_name"], t["start"], t["end"], "Blocked" if t["blocked"] else t["countdown"]]], [2, 2.2, 2.2, 1.5])
        self.heading("This term's courses")
        self.class_table()

    def class_table(self):
        self.table(["Course", "Title", "Days", "Time", "Room", "Instructor"],
                   [[c["code"], c["title"], c["days_label"], c["time_label"], c["room"], c["instructor_name"]] for c in self.d["classes"]],
                   [1.1, 3.2, 1.5, 1.5, 1.5, 1.9])

    def build_transcript(self):
        r = self.d["record"]
        self.stats([("Cumulative GPA", data_gpa(r["gpa"])), ("Credits earned", r["credits_earned"]), ("GPA credits", r["gpa_credits"]), ("Transfer credits", r["transfer_credits"])])
        if not r["terms"]:
            self.para("No grades yet")
        for term in r["terms"]:
            self.heading(f"{term['name']} · Term GPA {data_gpa(term['gpa'])} · Cumulative {data_gpa(term['cumulative'])}" if not self.rtl else
                         f"{self.t(term['name'])} · {self.t('Term GPA')} {data_gpa(term['gpa'])} · {self.t('Cumulative')} {data_gpa(term['cumulative'])}")
            rows = []
            for c in term["rows"]:
                note = f"Replaced by {c['replaced_by']} in GPA" if c["replaced_in"] else f"Repeat: replaces {c['replaces']}" if c["replaces"] else ""
                rows.append([c["course_code"], c["course_title"], c["credits"], c["letter_grade"], c["points_label"], note])
            self.table(["Course", "Title", "Credits", "Grade", "Points", "Note"], rows, [1.1, 4, .8, .8, .8, 2], keep=True)
        if r["transfers"]:
            self.heading("Transfer credits")
            self.table(["Institution", "External course", "ZU equivalent", "Credits", "Grade"],
                       [[c["institution"], c["external_course_code"], c["zu_equivalent_code"], c["credits"], c["grade"]] for c in r["transfers"]], [3.6, 1.7, 1.7, .8, .8])

    def build_audit(self):
        a = self.d["audit"]
        self.stats([("Overall progress", f"{a['percent']}%"), ("Done", f"{a['done']} · {a['done_credits']} cr"), ("In progress", f"{a['in_progress']} · {a['progress_credits']} cr"), ("Remaining", f"{a['remaining']} · {a['remaining_credits']} cr")])
        label = {"done": "Done", "progress": "In progress", "remaining": "Remaining"}
        for group in a["groups"]:
            self.heading(group["label"])
            rows = [[(i["via"] or {}).get("code") or i["course_code"] or i["requirement_type"], (i["via"] or {}).get("title") or i["course_title"], i["credits"], label[i["status"]], (i["via"] or {}).get("grade", "")] for i in group["items"]]
            self.table(["Course", "Title", "Credits", "Status", "Grade"], rows, [1.7, 4.6, .8, 1.3, .8], keep=True)

    def build_schedule(self):
        self.stats([("This term", f"{len(self.d['classes'])} classes"), ("Credits", self.d["term_credits"])])
        if self.d["classes"]:
            self.class_table()
            for day in data.DAY_ORDER:
                found = [c for c in self.d["classes"] if day in c["day_list"]]
                if found:
                    self.heading(data.DAY_NAMES[day])
                    self.table(["Time", "Course", "Title", "Room"], [[c["time_label"], c["code"], c["title"], c["room"]] for c in found], [1.4, 1, 4, 1.5], keep=True)

    def build_attendance(self):
        a = self.d["attendance"]
        self.stats([("Total absences", a["total"]), ("Warnings", a["warnings"]), ("Over 15%", a["alerts"])])
        if a["as_of"]:
            self.para(f"recorded up to {a['as_of']}")
        self.table(["Course", "Title", "Absences", "Meetings", "Absence %", "Status"],
                   [[r["code"], r["title"], r["absences"], r["allotted"], r["percent_label"], r["label"]] for r in a["rows"]], [1.1, 3.8, .9, .9, 1, 1.8])

    def build_holds(self):
        h = self.d["holds"]
        if h["blocked"]:
            self.banner("Registration is blocked", "")
        else:
            self.banner("You can register", "", bad=False)
        self.heading("Active holds")
        if h["active"]:
            self.table(["Type", "Reason", "Office", "Since", "Status"], [[x["hold_type"], x["reason"], x["office"], x["start_label"], "Blocks registration" if x["blocks"] else "Does not block"] for x in h["active"]], [1.2, 3.3, 2, 1.3, 1.6])
        else:
            self.para("There are no active holds on your account.")
        if h["released"]:
            self.heading("Released holds")
            self.table(["Type", "Reason", "Office", "Started", "Released"], [[x["hold_type"], x["reason"], x["office"], x["start_label"], x["released_label"]] for x in h["released"]], [1.2, 3.3, 2, 1.3, 1.3])

    def build_exams(self):
        e = self.d["exams"]
        if e["items"]:
            self.table(["Date", "Time", "Course", "Title", "Room", "Note"],
                       [[x["date_label"], f"{x['start_time']}–{x['end_time']}", x["code"], x["title"], x["room"], f"Overlaps {x['clash']}" if x["clash"] else ""] for x in e["items"]], [1.7, 1.3, 1, 3, 1.7, 1.4])
        else:
            self.para("No exams listed")
        if e["without"]:
            self.para("No final exam listed for: " + ", ".join(c["code"] for c in e["without"]) + ".")

    def decorate(self, canvas, document):
        canvas.saveState()
        top = A4[1] - 12 * mm
        logo = ImageReader(str(BASE_DIR / "static" / "zu-logo.png"))
        lw, lh = logo.getSize()
        h = 21 * mm
        w = h * lw / lh
        logo_x = A4[0] - MARGIN - w if not self.rtl else MARGIN
        canvas.drawImage(logo, logo_x, top - h, w, h, mask=None)
        text_x = MARGIN if not self.rtl else A4[0] - MARGIN
        draw = canvas.drawString if not self.rtl else canvas.drawRightString
        canvas.setFillColor(BRAND); canvas.setFont(self.bold, 15)
        draw(text_x, top - 6 * mm, self.visual(self.t(TITLES[self.kind])))
        canvas.setFillColor(INK); canvas.setFont(self.bold, 9.5)
        draw(text_x, top - 12 * mm, self.visual(f"{self.t(self.s['full_name'])}  ·  {self.s['student_id']}"))
        canvas.setFillColor(MUTED); canvas.setFont(self.font, 8.2)
        draw(text_x, top - 16.5 * mm, self.visual(f"{self.t(self.s['program_name'])}"))
        draw(text_x, top - 20.5 * mm, self.visual(self.t(data.term_name(data.CURRENT_TERM))))
        canvas.setStrokeColor(BRAND); canvas.setLineWidth(1.2)
        canvas.line(MARGIN, top - 24 * mm, A4[0] - MARGIN, top - 24 * mm)
        canvas.setFont(self.font, 7.5); canvas.setFillColor(MUTED)
        stamp = data.TODAY.strftime("%d %b %Y").lstrip("0")
        canvas.drawString(MARGIN, 9 * mm, self.visual(f"{self.t('Unofficial copy')} · {self.t(stamp)}"))
        canvas.drawRightString(A4[0] - MARGIN, 9 * mm, str(document.page))
        canvas.restoreState()

    def render(self) -> bytes:
        getattr(self, f"build_{self.kind}")()
        buffer = io.BytesIO()
        title = f"{TITLES[self.kind]} - {self.s['student_id']}"
        pdf = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=40 * mm, bottomMargin=16 * mm, title=title, author="ZU Student Access Portal")
        pdf.build(self.story or [Spacer(1, 1)], onFirstPage=self.decorate, onLaterPages=self.decorate)
        return buffer.getvalue()


def data_gpa(value) -> str:
    return f"{value:.2f}" if value is not None else "–"


def export_pdf(student_id: str, kind: str, lang: str) -> bytes:
    return Doc(student_id, kind, lang).render()
