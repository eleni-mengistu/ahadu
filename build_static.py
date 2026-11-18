"""Builds dist/, a static copy of the portal for hosts that cannot run Python.

Run with: uv run python build_static.py
No source code or CSV file is copied into dist/. Each student's pages live under a
folder named from a hash of their ID and password.
"""
import asyncio
import base64
import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import unquote

os.environ["SESSION_SECRET"] = "static-build-only"

import itsdangerous

import assistant
import main
import pdf_export
import portal_data as data

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
SALT = "zu-sap-static-v1"
PAGES = ["/", "/transcript", "/audit", "/schedule", "/attendance", "/holds", "/library", "/parking",
         "/courses", "/exams", "/gpa", "/entry-log", "/links"]
signer = itsdangerous.TimestampSigner("static-build-only")
LINK = re.compile(r'\b(href|action)="(/[^"]*)"')
JSON_LINK = re.compile(r'"href": "(/[^"]*)"')
original_today = data.todays_classes


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def route(path: str) -> str:
    path = unquote(path.split("?")[0])
    if path in ("/", "/login", ""):
        return "/"
    return path if path.endswith(".pdf") else path.rstrip("/") + "/"


def target(path: str, base: str | None, lang: str) -> str:
    if path.startswith("/static/") or path.startswith("/#"):
        return path
    if path.startswith("/lang/"):
        code = path[6:8]
        next_path = path.split("next=", 1)[1] if "next=" in path else "/"
        if base is None:
            return "/ar/" if code == "ar" else "/"
        return f"{base}/{code}{route(next_path)}"
    if base is None:
        return "/ar/" if lang == "ar" else "/"
    return f"{base}/{lang}{route(path)}"


def rewrite(page: str, base: str | None, lang: str) -> str:
    home = "/ar/" if lang == "ar" else "/"
    page = page.replace('method="post" action="/logout"', f'method="get" action="{home}" data-static')
    page = page.replace('method="post" action="/login"', 'action="#" data-static-login')
    page = LINK.sub(lambda m: f'{m[1]}="{m[2]}"' if m[0].endswith('data-static"') else f'{m[1]}="{target(m[2], base, lang)}"', page)
    page = JSON_LINK.sub(lambda m: f'"href": "{target(m[1], base, lang)}"', page)
    page = page.replace(f'action="{target(home, base, lang)}" data-static', f'action="{home}" data-static')
    return page.replace("</head>", '<script src="/static/static-site.js" defer></script></head>', 1)


async def fetch(path: str, student: str | None, lang: str) -> tuple[int, bytes]:
    cookies = [f"lang={lang}"]
    if student:
        payload = base64.b64encode(json.dumps({"student_id": student}).encode())
        cookies.append("session=" + signer.sign(payload).decode())
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET",
        "scheme": "http", "path": path, "raw_path": path.encode(), "query_string": b"",
        "root_path": "", "server": ("localhost", 80), "client": ("127.0.0.1", 1),
        "headers": [(b"host", b"localhost"), (b"cookie", "; ".join(cookies).encode())],
    }
    status, body = 500, bytearray()

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        nonlocal status
        if message["type"] == "http.response.start":
            status = message["status"]
        elif message["type"] == "http.response.body":
            body.extend(message.get("body", b""))

    await main.app(scope, receive, send)
    return status, bytes(body)


def write(relative: str, content: bytes | str) -> None:
    path = DIST / relative.lstrip("/")
    if relative.endswith("/"):
        path = path / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode() if isinstance(content, str) else content)


def assistant_data(sid: str, base: str) -> dict:
    def clean(answer: dict, lang: str) -> dict:
        return {"reply": answer["reply"], "source": "records", "links": [
            {**link, "href": target(link["href"], base, lang) if link["href"].startswith("/") else link["href"]}
            for link in answer["links"]
        ]}

    classes = data.current_classes(sid)
    result = {"courses": [{
        "code": c["code"],
        "names": [assistant.normalize(c["title"]), assistant.normalize(assistant.i18n.tr(c["title"]))],
    } for c in classes]}
    for lang in ("en", "ar"):
        say = assistant.Reply(lang)
        result[lang] = {
            "intents": {name: clean(assistant.local_answer(sid, words[0], lang), lang) for name, words in assistant.INTENTS},
            "days": {day: clean(assistant.local_answer(sid, names[0], lang), lang) for day, names in assistant.DAYS.items()},
            "courses": {c["code"]: clean(assistant.course_answer(say, sid, c["crn"]), lang) for c in classes},
            "fallback": clean(assistant.local_answer(sid, "qqqq", lang), lang),
        }
    return result


async def build() -> None:
    data.todays_classes = lambda classes: {
        **original_today(classes),
        "items": [{**c, "status": None} for c in original_today(classes)["items"]],
    }
    if DIST.exists():
        assert DIST.parent == ROOT and DIST.name == "dist"
        shutil.rmtree(DIST)
    shutil.copytree(ROOT / "static", DIST / "static")
    for lang, output in (("en", "/"), ("ar", "/ar/")):
        _, page = await fetch("/login", None, lang)
        write(output, rewrite(page.decode(), None, lang))
    _, page = await fetch("/not-a-page", None, "en")
    write("/404.html", rewrite(page.decode(), None, "en"))
    write("/_redirects", "/login / 302\n")
    write("/_headers", "/s/*\n  X-Robots-Tag: noindex\n  Cache-Control: no-store\n")
    write("/auth-ids.json", json.dumps(sorted(sha(f"{SALT}|{sid}") for sid in data.DB.students)))
    write("/assistant-rules.json", json.dumps({
        "intents": [[name, [assistant.normalize(w) for w in words]] for name, words in assistant.INTENTS],
        "days": [[day, list(names)] for day, names in assistant.DAYS.items()],
        "noTitleMatch": ["gpa", "holds", "library", "room", "loan", "aisha"],
    }, ensure_ascii=False))

    pages = pdfs = 0
    for sid, student in data.DB.students.items():
        token = sha(f"{SALT}|{sid}|{student['password']}")[:32]
        base = f"/s/{token}"
        courses = [f"/courses/{c['crn']}" for c in data.current_classes(sid)]
        answers = assistant_data(sid, base)
        for lang in ("en", "ar"):
            write(f"{base}/{lang}/assistant.json", json.dumps(answers, ensure_ascii=False))
            for path in PAGES + courses:
                status, page = await fetch(path, sid, lang)
                assert status == 200, (sid, lang, path, status)
                write(f"{base}/{lang}{route(path)}", rewrite(page.decode(), base, lang))
                pages += 1
            for kind in pdf_export.TITLES:
                write(f"{base}/{lang}/export/{kind}.pdf", pdf_export.export_pdf(sid, kind, lang))
                pdfs += 1
        print(f"built {sid}", flush=True)
    print(f"done: {pages} pages, {pdfs} PDFs")


if __name__ == "__main__":
    asyncio.run(build())
