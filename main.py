import os
import secrets
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

import assistant as zu_assistant
import i18n
import pdf_export
import portal_data as data

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="ZU Student Access Portal", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET") or secrets.token_hex(32),
    same_site="lax",
    max_age=8 * 60 * 60,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def gpa_text(value) -> str:
    return f"{value:.2f}" if value is not None else "–"


templates.env.filters["gpa"] = gpa_text
templates.env.filters["nice_date"] = data.nice_date
templates.env.globals["current_term_name"] = data.term_name(data.CURRENT_TERM)
templates.env.globals["today_label"] = (
    f"{data.TODAY.strftime('%a')} {data.TODAY.day} {data.TODAY.strftime('%b %Y')}"
)
ACCENTS = [
    {"key": "burgundy", "label": "Burgundy", "color": "#8E2A42"},
    {"key": "plum", "label": "Plum", "color": "#7A1F82"},
    {"key": "teal", "label": "Teal", "color": "#0D6E6E"},
    {"key": "ocean", "label": "Ocean", "color": "#1E5696"},
    {"key": "forest", "label": "Forest", "color": "#2E6B3E"},
]
templates.env.globals["accents"] = ACCENTS


def language(request: Request) -> str:
    return "ar" if request.cookies.get("lang") == "ar" else "en"


def localized(request: Request, template: str, context: dict, status: int = 200, names: dict | None = None):
    lang = language(request)
    context = {**context, "lang": lang, "dir": "rtl" if lang == "ar" else "ltr", "path": request.url.path}
    page = templates.TemplateResponse(request, template, context).body.decode()
    if lang == "ar":
        page = i18n.translate_html(page, names)
    return HTMLResponse(page, status_code=status, headers={"Cache-Control": "no-store"})


def navigation(base: dict) -> list[dict]:
    attendance_count = base["attendance"]["alerts"] + base["attendance"]["warnings"]
    return [
        {"group": "Home", "items": [
            {"key": "home", "label": "Dashboard", "href": "/", "icon": "home"},
        ]},
        {"group": "Academics", "items": [
            {"key": "transcript", "label": "Academic transcript", "href": "/transcript", "icon": "file"},
            {"key": "audit", "label": "Degree audit", "href": "/audit", "icon": "check"},
            {"key": "gpa", "label": "GPA calculator", "href": "/gpa", "icon": "calc"},
        ]},
        {"group": "Courses", "items": [
            {"key": "schedule", "label": "Class schedule", "href": "/schedule", "icon": "calendar"},
            {"key": "courses", "label": "My courses", "href": "/courses", "icon": "book"},
            {"key": "exams", "label": "Exam schedule", "href": "/exams", "icon": "clock"},
        ]},
        {"group": "Student Essentials", "items": [
            {"key": "attendance", "label": "Class attendance", "href": "/attendance", "icon": "user",
             "badge": attendance_count,
             "badge_level": "bad" if base["attendance"]["alerts"] else "warn"},
            {"key": "holds", "label": "Holds", "href": "/holds", "icon": "lock",
             "badge": len(base["holds"]["active"]),
             "badge_level": "bad" if base["holds"]["blocked"] else "warn"},
            {"key": "library", "label": "Library services", "href": "/library", "icon": "library"},
            {"key": "parking", "label": "Smart parking", "href": "/parking", "icon": "car"},
            {"key": "entry", "label": "Campus entry log", "href": "/entry-log", "icon": "door"},
        ]},
        {"group": "Quick Links", "items": [
            {"key": "links", "label": "Advisor, people & news", "href": "/links", "icon": "users"},
        ]},
    ]


def signed_in(request: Request) -> str | None:
    student_id = request.session.get("student_id")
    return student_id if student_id in data.DB.students else None


def to_login() -> RedirectResponse:
    return RedirectResponse("/login", status_code=303)


def assistant_config(student: dict, lang: str) -> dict:
    t = lambda text: i18n.tr(text, lang)
    first = student["full_name_ar"].split()[0] if lang == "ar" else student["first_name"]
    ar = lang == "ar"
    return {
        "key": student["student_id"],
        "lang": lang,
        "text": {
            "title": "مساعد الجامعة" if ar else "ZU Assistant",
            "subtitle": "إجابات من سجلك الخاص" if ar else "Answers from your own record",
            "greeting": f"مرحبا {first}! كيف يمكنني مساعدتك اليوم؟" if ar else f"Hi {first}! How can I help you today?",
            "placeholder": "اكتب سؤالك…" if ar else "Ask a question…",
            "send": "إرسال" if ar else "Send", "open": "فتح المساعد" if ar else "Open assistant",
            "close": "إغلاق" if ar else "Close", "clear": "محادثة جديدة" if ar else "New chat",
            "error": "تعذر الوصول إلى المساعد. حاول مرة أخرى." if ar else "I couldn't reach the assistant. Please try again.",
            "expired": "انتهت جلستك. سجّل الدخول مرة أخرى." if ar else "Your session has ended. Please sign in again.",
            "thinking": "يكتب…" if ar else "Typing…",
        },
        "chips": [
            "ما محاضراتي اليوم؟", "كم معدلي؟", "هل أنا معرض لخطر الغياب؟", "هل يمكنني التسجيل؟", "متى اختباري القادم؟", "قواعد استعارة الكتب",
        ] if ar else [
            "What classes do I have today?", "What is my GPA?", "Am I at risk for attendance?",
            "Can I register?", "When is my next exam?", "Library loan rules",
        ],
    }


def render(request: Request, template: str, active: str, title: str, student_id: str, **extra):
    base = data.dashboard(student_id)
    lang = language(request)
    nav = navigation(base)
    palette = [
        {"label": i18n.tr(item["label"], lang), "hint": i18n.tr(group["group"], lang), "href": item["href"]}
        for group in nav for item in group["items"]
    ] + [
        {"label": f"{c['code']} {i18n.tr(c['title'], lang)}", "hint": i18n.tr("Course", lang), "href": f"/courses/{c['crn']}"}
        for c in base["classes"]
    ]
    student = base["student"]
    names = {student["full_name"]: student["full_name_ar"]}
    context = {
        **base, "active": active, "title": title, "nav": nav, "palette": palette,
        "assistant_config": assistant_config(student, lang), **extra,
    }
    return localized(request, template, context, names=names)


@app.get("/lang/{code}")
def set_language(code: str, next: str = "/"):
    target = next if next.startswith("/") and not next.startswith("//") and "\\" not in next else "/"
    response = RedirectResponse(target, status_code=303)
    response.set_cookie("lang", "ar" if code == "ar" else "en", max_age=60 * 60 * 24 * 365, samesite="lax")
    return response


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if signed_in(request):
        return RedirectResponse("/", status_code=303)
    return localized(request, "login.html", {"error": None, "student_id": ""})


@app.post("/login", response_class=HTMLResponse)
def login(request: Request, student_id: str = Form(""), password: str = Form("")):
    found, error = data.authenticate(student_id, password)
    if error:
        return localized(request, "login.html", {"error": error, "student_id": student_id.strip()}, status=401)
    request.session.clear()
    request.session["student_id"] = found
    return RedirectResponse("/", status_code=303)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return to_login()


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    sid = signed_in(request)
    return render(request, "home.html", "home", "Dashboard", sid) if sid else to_login()


@app.get("/transcript", response_class=HTMLResponse)
def transcript(request: Request):
    sid = signed_in(request)
    return render(request, "transcript.html", "transcript", "Academic transcript", sid) if sid else to_login()


@app.get("/audit", response_class=HTMLResponse)
def audit(request: Request):
    sid = signed_in(request)
    return render(request, "audit.html", "audit", "Degree audit", sid) if sid else to_login()


@app.get("/schedule", response_class=HTMLResponse)
def schedule(request: Request):
    sid = signed_in(request)
    if not sid:
        return to_login()
    calendar = data.weekly_calendar(data.current_classes(sid))
    return render(request, "schedule.html", "schedule", "Class schedule", sid, calendar=calendar)


@app.get("/attendance", response_class=HTMLResponse)
def attendance(request: Request):
    sid = signed_in(request)
    return render(request, "attendance.html", "attendance", "Class attendance", sid) if sid else to_login()


@app.get("/holds", response_class=HTMLResponse)
def holds(request: Request):
    sid = signed_in(request)
    return render(request, "holds.html", "holds", "Holds", sid) if sid else to_login()


@app.get("/library", response_class=HTMLResponse)
def library(request: Request):
    sid = signed_in(request)
    if not sid:
        return to_login()
    classes = data.current_classes(sid)
    library_data = data.library_info(data.profile(sid), data.holds_report(sid))
    return render(
        request, "library.html", "library", "Library services", sid,
        preview=data.library_preview(sid, classes, library_data),
    )


@app.get("/parking", response_class=HTMLResponse)
def parking(request: Request):
    sid = signed_in(request)
    if not sid:
        return to_login()
    return render(request, "parking.html", "parking", "Smart parking", sid, parking=data.parking_view(sid))


@app.get("/courses", response_class=HTMLResponse)
def courses(request: Request):
    sid = signed_in(request)
    if not sid:
        return to_login()
    classes = data.current_classes(sid)
    return render(
        request, "courses.html", "courses", "My courses", sid,
        scores=data.scores_overview(sid, classes),
        attendance_by_crn={r["crn"]: r for r in data.attendance_report(sid, classes)["rows"]},
        exam_by_crn={e["crn"]: e for e in data.exam_report(classes)["items"]},
    )


@app.get("/courses/{crn}", response_class=HTMLResponse)
def course(request: Request, crn: str):
    sid = signed_in(request)
    if not sid:
        return to_login()
    detail = data.course_detail(sid, crn)
    if detail is None:
        raise StarletteHTTPException(status_code=404)
    return render(request, "course.html", "courses", detail["item"]["code"], sid, detail=detail)


@app.get("/exams", response_class=HTMLResponse)
def exams(request: Request):
    sid = signed_in(request)
    return render(request, "exams.html", "exams", "Exam schedule", sid) if sid else to_login()


@app.get("/gpa", response_class=HTMLResponse)
def gpa(request: Request):
    sid = signed_in(request)
    if not sid:
        return to_login()
    record = data.academic_record(sid)
    calc = data.gpa_calculator(sid, record, data.current_classes(sid))
    lang = language(request)
    for item in calc["courses"]:
        item["title"] = i18n.tr(item["title"], lang)
    return render(request, "gpa.html", "gpa", "GPA calculator", sid, calc=calc)


@app.get("/entry-log", response_class=HTMLResponse)
def entry_log(request: Request):
    sid = signed_in(request)
    if not sid:
        return to_login()
    return render(request, "entry.html", "entry", "Campus entry log", sid, days=data.entry_log_days(sid))


@app.get("/links", response_class=HTMLResponse)
def links(request: Request):
    sid = signed_in(request)
    if not sid:
        return to_login()
    people = data.contacts(sid, data.current_classes(sid))
    return render(
        request, "links.html", "links", "Advisor, people & news", sid,
        people=people, all_news=data.DB.news,
    )


@app.get("/export/{kind}.pdf")
def export(request: Request, kind: str):
    sid = signed_in(request)
    if not sid:
        return to_login()
    if kind not in pdf_export.TITLES:
        raise StarletteHTTPException(status_code=404)
    content = pdf_export.export_pdf(sid, kind, language(request))
    return Response(content, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="ZU_{kind}_{sid}.pdf"',
        "Cache-Control": "no-store",
    })


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[dict] = Field(default_factory=list, max_length=40)


@app.post("/api/assistant")
def chat(request: Request, body: ChatRequest):
    sid = signed_in(request)
    if not sid:
        return JSONResponse({"error": "signed_out"}, status_code=401)
    return zu_assistant.answer(sid, body.message, body.history, language(request))


@app.exception_handler(StarletteHTTPException)
async def not_found(request: Request, exc: StarletteHTTPException):
    if exc.status_code != 404:
        return HTMLResponse(str(exc.detail), status_code=exc.status_code)
    return localized(request, "404.html", {}, status=404)
