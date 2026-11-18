"""Loads the challenge CSV files at startup and applies the ZU rules to them.

Nothing about a student is stored in this file: every value comes from data/.
"""
from __future__ import annotations

import csv
import hmac
import math
from collections import Counter, defaultdict
from datetime import date, datetime
from fractions import Fraction
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CORE_DIR = BASE_DIR / "data" / "core"
EXTRAS_DIR = BASE_DIR / "data" / "extras"

TODAY = date(2026, 11, 18)
CURRENT_TERM = "202610"
PROBATION_GPA = Fraction(2)
WARNING_1 = 5
WARNING_2 = 10
WF_LIMIT = 15
DAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_NAMES = {
    "Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday", "Thu": "Thursday",
    "Fri": "Friday", "Sat": "Saturday", "Sun": "Sunday",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [
            {key: (value or "").strip() for key, value in row.items()}
            for row in csv.DictReader(handle)
        ]


def group_by(rows: list[dict], key: str) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row[key]].append(row)
    return grouped


def index_by(rows: list[dict], key: str) -> dict[str, dict]:
    return {row[key]: row for row in rows}


class Data:
    def __init__(self) -> None:
        core = {path.stem: read_csv(path) for path in CORE_DIR.glob("*.csv")}
        extras = {path.stem: read_csv(path) for path in EXTRAS_DIR.glob("*.csv")}
        self.row_counts = {name: len(rows) for name, rows in {**core, **extras}.items()}

        self.students = index_by(core["students"], "student_id")
        self.programs = index_by(core["programs"], "program_code")
        self.courses = index_by(core["courses"], "course_code")
        self.terms = index_by(core["terms"], "term_code")
        self.sections = index_by(core["sections"], "crn")
        self.faculty = index_by(core["faculty"], "faculty_id")
        self.scale = index_by(core["grade_scale"], "letter_grade")
        self.tickets = index_by(core["time_tickets"], "student_id")
        self.requirements = group_by(core["degree_requirements"], "program_code")
        self.enrollments = group_by(core["enrollments"], "student_id")
        self.grades = group_by(core["grades"], "student_id")
        self.transfers = group_by(core["transfer_credits"], "student_id")
        self.attendance = group_by(core["attendance"], "student_id")
        self.holds = group_by(core["holds"], "student_id")

        self.courses_full = index_by(extras["courses_full"], "course_code")
        self.exams = index_by(extras["exam_schedule"], "crn")
        self.scores = group_by(extras["score_records"], "student_id")
        self.entry_logs = group_by(extras["entry_logs"], "student_id")
        self.news = sorted(extras["news"], key=lambda n: n["date"], reverse=True)


DB = Data()


# ---------------------------------------------------------------- helpers

def round2(value: Fraction) -> float:
    """Round the way students.csv was rounded, so both always agree."""
    return round(float(value), 2)


def to_minutes(clock: str) -> int:
    hours, minutes = clock.split(":")
    return int(hours) * 60 + int(minutes)


def parse_date(text: str) -> date:
    return datetime.strptime(text, "%Y-%m-%d").date()


def nice_date(text: str) -> str:
    value = parse_date(text)
    return f"{value.day} {value.strftime('%b %Y')}"


def term_name(code: str) -> str:
    term = DB.terms.get(code)
    return term["term_name"] if term else code


def quality(letter: str) -> Fraction | None:
    points = DB.scale.get(letter, {}).get("quality_points", "")
    return Fraction(points) if points else None


def counts_in_gpa(letter: str) -> bool:
    return DB.scale.get(letter, {}).get("counts_in_gpa") == "Yes"


def earns_credit(letter: str) -> bool:
    return DB.scale.get(letter, {}).get("earns_credit") == "Yes"


def is_fail(letter: str) -> bool:
    return counts_in_gpa(letter) and not earns_credit(letter)


def gpa_of(rows: list[dict]) -> tuple[Fraction | None, int]:
    points = Fraction(0)
    credits = 0
    for row in rows:
        points += quality(row["letter_grade"]) * int(row["credits"])
        credits += int(row["credits"])
    return (points / credits if credits else None), credits


# ---------------------------------------------------------------- login

def authenticate(student_id: str, password: str) -> tuple[str | None, str | None]:
    student_id = student_id.strip()
    if not student_id or not password:
        return None, "Enter both your student ID and your password."
    student = DB.students.get(student_id)
    if student is None:
        return None, "We can't find that student ID. Check the number and try again."
    if not hmac.compare_digest(student["password"].encode(), password.encode()):
        return None, "That password is incorrect. Please try again."
    return student_id, None


def profile(student_id: str) -> dict:
    student = {k: v for k, v in DB.students[student_id].items() if k != "password"}
    student["advisor"] = DB.faculty.get(student["advisor_id"], {})
    student["entry_term_name"] = term_name(student["entry_term"])
    student["initials"] = student["first_name"][:1] + student["last_name"].split()[-1][:1]
    student["on_probation"] = "probation" in student["academic_standing"].lower()
    return student


# ---------------------------------------------------------------- transcript

def academic_record(student_id: str) -> dict:
    rows = sorted(
        (dict(row) for row in DB.grades.get(student_id, [])),
        key=lambda row: row["term_code"],
    )
    attempts: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        attempts[row["course_code"]].append(row)

    for row in rows:
        letter = row["letter_grade"]
        row["credits_int"] = int(row["credits"])
        row["points"] = quality(letter)
        row["points_label"] = f"{float(row['points']):.1f}" if row["points"] is not None else "–"
        row["counts"] = counts_in_gpa(letter)
        row["earned"] = earns_credit(letter)
        row["meaning"] = DB.scale.get(letter, {}).get("meaning", "")
        row["replaced_in"] = None
        row.setdefault("replaces", None)
        if is_fail(letter):
            for later in attempts[row["course_code"]]:
                if later["term_code"] > row["term_code"] and earns_credit(later["letter_grade"]):
                    row["replaced_in"] = later["term_code"]
                    row["replaced_by"] = later["letter_grade"]
                    later["replaces"] = letter
                    break

    term_codes = sorted({row["term_code"] for row in rows})
    terms = []
    for code in term_codes:
        term_rows = [row for row in rows if row["term_code"] == code]
        counted = [row for row in term_rows if row["counts"]]
        term_gpa, attempted = gpa_of(counted)
        adjusted, _ = gpa_of([row for row in counted if not row["replaced_in"]])
        running = [
            row for row in rows
            if row["term_code"] <= code and row["counts"]
            and not (row["replaced_in"] and row["replaced_in"] <= code)
        ]
        cumulative, _ = gpa_of(running)
        terms.append({
            "code": code,
            "name": term_name(code),
            "rows": term_rows,
            "attempted": attempted,
            "earned": sum(row["credits_int"] for row in term_rows if row["earned"]),
            "gpa": round2(term_gpa) if term_gpa is not None else None,
            "gpa_without_replaced": (
                round2(adjusted) if adjusted is not None and adjusted != term_gpa else None
            ),
            "cumulative": round2(cumulative) if cumulative is not None else None,
        })

    counted = [row for row in rows if row["counts"] and not row["replaced_in"]]
    gpa, gpa_credits = gpa_of(counted)
    points = sum((row["points"] * row["credits_int"] for row in counted), Fraction(0))

    transfers = [dict(row) for row in DB.transfers.get(student_id, [])]
    for row in transfers:
        row["credits_int"] = int(row["credits"])
        row["term_name"] = term_name(row["term_awarded"])
    transfer_credits = sum(row["credits_int"] for row in transfers)
    earned_here = sum(row["credits_int"] for row in rows if row["earned"])

    return {
        "rows": rows,
        "terms": terms,
        "gpa": round2(gpa) if gpa is not None else None,
        "gpa_exact": gpa,
        "points": points,
        "points_label": f"{float(points):.1f}",
        "gpa_credits": gpa_credits,
        "earned_at_zu": earned_here,
        "transfer_credits": transfer_credits,
        "credits_earned": earned_here + transfer_credits,
        "transfers": transfers,
        "replaced": [row for row in rows if row["replaced_in"]],
    }


# ---------------------------------------------------------------- classes

def current_classes(student_id: str) -> list[dict]:
    attendance = {row["crn"]: row for row in DB.attendance.get(student_id, [])}
    classes = []
    enrolled = [
        row for row in DB.enrollments.get(student_id, [])
        if row["term_code"] == CURRENT_TERM and row["registration_status"] == "Registered"
    ]
    for color, enrollment in enumerate(enrolled):
        section = DB.sections.get(enrollment["crn"])
        if section is None:
            continue
        days = [day.strip() for day in section["days"].split(",") if day.strip()]
        classes.append({
            **section,
            "code": section["course_code"],
            "title": section["course_title"],
            "credits_int": int(section["credits"]),
            "day_list": days,
            "days_label": ", ".join(days),
            "start_min": to_minutes(section["start_time"]),
            "end_min": to_minutes(section["end_time"]),
            "time_label": f"{section['start_time']}–{section['end_time']}",
            "instructor": DB.faculty.get(section["instructor_id"], {}),
            "color": color % 6,
            "appeal": enrollment["attendance_appeal_status"],
            "registration_method": enrollment["registration_method"],
            "attendance_row": attendance.get(enrollment["crn"]),
        })
    return sorted(classes, key=lambda c: (c["start_min"], c["code"]))


def overlaps(a: dict, b: dict) -> bool:
    return a["start_min"] < b["end_min"] and b["start_min"] < a["end_min"]


def weekly_calendar(classes: list[dict]) -> dict:
    used = {day for item in classes for day in item["day_list"]}
    days = [d for d in DAY_ORDER if d in DAY_ORDER[:5] or d in used]
    first = min((c["start_min"] for c in classes), default=8 * 60)
    last = max((c["end_min"] for c in classes), default=17 * 60)
    start_hour = min(8, first // 60)
    end_hour = max(17, math.ceil(last / 60))
    span = (end_hour - start_hour) * 60

    columns = []
    conflicts = []
    for day in days:
        todays = sorted(
            (c for c in classes if day in c["day_list"]),
            key=lambda c: (c["start_min"], c["end_min"]),
        )
        lanes: list[int] = []
        placed = []
        for item in todays:
            lane = next((i for i, end in enumerate(lanes) if end <= item["start_min"]), None)
            if lane is None:
                lanes.append(item["end_min"])
                lane = len(lanes) - 1
            else:
                lanes[lane] = item["end_min"]
            placed.append({"item": item, "lane": lane})
        for index, a in enumerate(todays):
            for b in todays[index + 1:]:
                if overlaps(a, b):
                    conflicts.append({"day": DAY_NAMES[day], "a": a["code"], "b": b["code"]})
        lane_total = max(len(lanes), 1)
        columns.append({
            "day": day,
            "name": DAY_NAMES[day],
            "is_today": day == TODAY.strftime("%a"),
            "events": [{
                **entry["item"],
                "top": (entry["item"]["start_min"] - start_hour * 60) / span * 100,
                "height": (entry["item"]["end_min"] - entry["item"]["start_min"]) / span * 100,
                "left": entry["lane"] / lane_total * 100,
                "width": 100 / lane_total,
            } for entry in placed],
        })
    return {
        "columns": columns,
        "hours": [
            {"label": f"{hour:02d}:00", "top": (hour - start_hour) / (end_hour - start_hour) * 100}
            for hour in range(start_hour, end_hour)
        ],
        "conflicts": conflicts,
        "height": (end_hour - start_hour) * 62,
    }


def todays_classes(classes: list[dict]) -> dict:
    today = TODAY.strftime("%a")
    now = datetime.now()
    clock = now.hour * 60 + now.minute if now.date() == TODAY else None
    items = []
    for item in classes:
        if today not in item["day_list"]:
            continue
        status = None
        if clock is not None:
            if clock >= item["end_min"]:
                status = "Finished"
            elif clock >= item["start_min"]:
                status = "Now"
            else:
                status = "Upcoming"
        items.append({**item, "status": status})

    next_day = None
    if not items and classes:
        start = DAY_ORDER.index(today)
        for offset in range(1, 8):
            day = DAY_ORDER[(start + offset) % 7]
            found = [c for c in classes if day in c["day_list"]]
            if found:
                next_day = {"name": DAY_NAMES[day], "first": found[0], "count": len(found)}
                break
    return {
        "label": f"{TODAY.strftime('%A')}, {TODAY.day} {TODAY.strftime('%B %Y')}",
        "items": items,
        "next_day": next_day,
    }


# ---------------------------------------------------------------- attendance

def attendance_report(student_id: str, classes: list[dict] | None = None) -> dict:
    classes = classes if classes is not None else current_classes(student_id)
    rows = []
    as_of = ""
    for item in classes:
        record = item["attendance_row"]
        if record is None:
            continue
        absences = int(record["absences"])
        allotted = int(record["meetings_allotted"])
        held = int(record["meetings_held_to_date"])
        as_of = record["as_of_date"]
        percent = absences / allotted * 100 if allotted else 0.0
        scaled = absences * 100
        if allotted and scaled > WF_LIMIT * allotted:
            level, label = "alert", "Over 15%: WF risk"
        elif allotted and scaled >= WARNING_2 * allotted:
            level, label = "second", "Second warning"
        elif allotted and scaled >= WARNING_1 * allotted:
            level, label = "first", "First warning"
        else:
            level, label = "ok", "On track"
        limit = math.floor(allotted * WF_LIMIT / 100)
        rows.append({
            "crn": item["crn"],
            "code": item["code"],
            "title": item["title"],
            "instructor": item["instructor_name"],
            "absences": absences,
            "allotted": allotted,
            "held": held,
            "percent": percent,
            "percent_label": f"{percent:.1f}%",
            "bar": min(percent / 20 * 100, 100),
            "level": level,
            "label": label,
            "limit": limit,
            "left": limit - absences,
            "appeal": item["appeal"],
        })
    rank = {"alert": 0, "second": 1, "first": 2, "ok": 3}
    rows.sort(key=lambda r: (rank[r["level"]], -r["percent"], r["code"]))
    return {
        "rows": rows,
        "as_of": nice_date(as_of) if as_of else "",
        "total": sum(r["absences"] for r in rows),
        "worst": rows[0] if rows else None,
        "alerts": sum(1 for r in rows if r["level"] == "alert"),
        "warnings": sum(1 for r in rows if r["level"] in ("first", "second")),
    }


# ---------------------------------------------------------------- holds + ticket

def holds_report(student_id: str) -> dict:
    rows = []
    for hold in DB.holds.get(student_id, []):
        active = not hold["released_date"]
        rows.append({
            **hold,
            "active": active,
            "blocks": hold["blocks_registration"] == "Yes",
            "blocking_now": active and hold["blocks_registration"] == "Yes",
            "start_label": nice_date(hold["start_date"]),
            "released_label": nice_date(hold["released_date"]) if hold["released_date"] else "",
        })
    active = [h for h in rows if h["active"]]
    active.sort(key=lambda h: not h["blocks"])
    blocking = [h for h in active if h["blocks"]]
    return {
        "active": active,
        "released": [h for h in rows if not h["active"]],
        "blocking": blocking,
        "blocked": bool(blocking),
        "total": len(rows),
    }


def time_ticket(student_id: str, holds: dict) -> dict | None:
    row = DB.tickets.get(student_id)
    if row is None:
        return None
    start = datetime.strptime(row["registration_start"], "%Y-%m-%d %H:%M")
    end = datetime.strptime(row["registration_end"], "%Y-%m-%d %H:%M")
    days = (start.date() - TODAY).days
    if TODAY < start.date():
        state = "upcoming"
        countdown = "Opens tomorrow" if days == 1 else f"Opens in {days} days"
    elif TODAY <= end.date():
        state, countdown = "open", "Open now"
    else:
        state, countdown = "closed", "Closed"
    fmt = lambda v: f"{v.strftime('%a')} {v.day} {v.strftime('%b %Y')}, {v.strftime('%H:%M')}"
    return {
        "term_name": row["term_name"],
        "start": fmt(start),
        "end": fmt(end),
        "state": state,
        "countdown": countdown,
        "days": days,
        "blocked": holds["blocked"],
    }


# ---------------------------------------------------------------- degree audit

def degree_audit(student_id: str, record: dict | None = None,
                 classes: list[dict] | None = None) -> dict:
    student = DB.students[student_id]
    record = record or academic_record(student_id)
    classes = classes if classes is not None else current_classes(student_id)
    program = DB.programs.get(student["program_code"], {})
    requirements = DB.requirements.get(student["program_code"], [])

    passed: dict[str, dict] = {}
    failed: dict[str, dict] = {}
    for row in record["rows"]:
        if row["earned"]:
            passed[row["course_code"]] = {
                "code": row["course_code"], "title": row["course_title"],
                "credits": row["credits_int"], "grade": row["letter_grade"],
                "term": term_name(row["term_code"]), "source": "ZU",
            }
        elif is_fail(row["letter_grade"]):
            failed[row["course_code"]] = row
    for row in record["transfers"]:
        passed.setdefault(row["zu_equivalent_code"], {
            "code": row["zu_equivalent_code"], "title": row["zu_equivalent_title"],
            "credits": row["credits_int"], "grade": "TR",
            "term": row["term_name"], "source": row["institution"],
        })
    current = {item["code"]: item for item in classes}

    used: set[str] = set()
    results: list[dict] = []
    for requirement in requirements:
        options = [c for c in (requirement["course_code"], requirement["alternative_course_code"]) if c]
        result = {
            **requirement,
            "credits_int": int(requirement["credits"]),
            "is_elective": not requirement["course_code"],
            "status": "remaining", "via": None, "note": "",
        }
        chosen = next((c for c in options if c in passed and c not in used), None)
        if chosen:
            result.update(status="done", via=passed[chosen])
            used.add(chosen)
        else:
            chosen = next((c for c in options if c in current and c not in used), None)
            if chosen:
                result.update(status="progress", via={
                    "code": chosen, "title": current[chosen]["title"], "grade": "",
                    "term": term_name(CURRENT_TERM), "source": "ZU",
                    "crn": current[chosen]["crn"],
                })
                used.add(chosen)
                if chosen in failed:
                    result["note"] = f"Retaking after {failed[chosen]['letter_grade']}"
            else:
                missed = next((c for c in options if c in failed), None)
                if missed:
                    row = failed[missed]
                    result["note"] = (
                        f"{row['letter_grade']} in {term_name(row['term_code'])}: must be retaken"
                    )
        results.append(result)

    program_subjects = {
        r["course_code"][:3] for r in requirements
        if r["course_code"] and r["requirement_type"] == "Program Required"
    }

    def fits(slot: dict, code: str) -> bool:
        kind = slot["requirement_type"]
        if kind == "Art History Elective":
            return code.startswith("AAH")
        if kind == "Program Elective":
            return code[:3] in program_subjects
        return True

    rank = {"Art History Elective": 0, "Program Elective": 1, "ZU Elective": 2}
    slots = sorted(
        (r for r in results if r["is_elective"]),
        key=lambda r: rank.get(r["requirement_type"], 3),
    )
    for pool, status in ((passed, "done"), (current, "progress")):
        for code in pool:
            if code in used:
                continue
            slot = next(
                (s for s in slots if s["status"] == "remaining" and fits(s, code)), None
            )
            if slot is None:
                continue
            used.add(code)
            if status == "done":
                via = pool[code]
            else:
                item = pool[code]
                via = {"code": code, "title": item["title"], "grade": "",
                       "term": term_name(CURRENT_TERM), "source": "ZU", "crn": item["crn"]}
            slot.update(status=status, via=via)

    not_applied = [v for c, v in passed.items() if c not in used]

    groups: list[dict] = []
    for result in results:
        semester = result["recommended_semester"]
        label = f"Semester {semester}" if semester.isdigit() else semester
        if not groups or groups[-1]["label"] != label:
            groups.append({"label": label, "items": []})
        groups[-1]["items"].append(result)
    for group in groups:
        group["credits"] = sum(i["credits_int"] for i in group["items"])
        group["done_credits"] = sum(
            i["credits_int"] for i in group["items"] if i["status"] == "done"
        )
        statuses = {i["status"] for i in group["items"]}
        group["state"] = (
            "done" if statuses == {"done"}
            else "progress" if "progress" in statuses or "done" in statuses
            else "remaining"
        )

    def tally(status: str) -> tuple[int, int]:
        chosen = [r for r in results if r["status"] == status]
        return len(chosen), sum(r["credits_int"] for r in chosen)

    done_n, done_cr = tally("done")
    progress_n, progress_cr = tally("progress")
    remaining_n, remaining_cr = tally("remaining")
    total_cr = done_cr + progress_cr + remaining_cr
    return {
        "program": program,
        "groups": groups,
        "done": done_n, "in_progress": progress_n, "remaining": remaining_n,
        "total": len(results),
        "done_credits": done_cr, "progress_credits": progress_cr,
        "remaining_credits": remaining_cr, "total_credits": total_cr,
        "percent": round(done_cr / total_cr * 100) if total_cr else 0,
        "percent_done_exact": done_cr / total_cr * 100 if total_cr else 0,
        "percent_progress_exact": progress_cr / total_cr * 100 if total_cr else 0,
        "not_applied": not_applied,
        "gpa_ok": record["gpa_exact"] is not None and record["gpa_exact"] >= PROBATION_GPA,
    }


# ---------------------------------------------------------------- extras

def exam_report(classes: list[dict]) -> dict:
    exams = []
    without = []
    for item in classes:
        exam = DB.exams.get(item["crn"])
        if exam is None:
            without.append(item)
            continue
        when = parse_date(exam["exam_date"])
        days = (when - TODAY).days
        exams.append({
            **exam,
            "title": exam["course_title"],
            "code": exam["course_code"],
            "date_label": f"{when.strftime('%a')} {when.day} {when.strftime('%b %Y')}",
            "month": when.strftime("%b"),
            "day": when.day,
            "weekday": when.strftime("%A"),
            "days": days,
            "start_min": to_minutes(exam["start_time"]),
            "end_min": to_minutes(exam["end_time"]),
            "clash": None,
            "gap": None,
        })
    exams.sort(key=lambda e: (e["exam_date"], e["start_min"]))
    for index, exam in enumerate(exams):
        for other in exams[index + 1:]:
            if exam["exam_date"] == other["exam_date"] and overlaps(exam, other):
                exam["clash"] = other["code"]
                other["clash"] = exam["code"]
        if index:
            exam["gap"] = (parse_date(exam["exam_date"]) - parse_date(exams[index - 1]["exam_date"])).days
    return {"items": exams, "without": without, "next": exams[0] if exams else None,
            "clashes": sum(1 for e in exams if e["clash"])}


def course_scores(student_id: str, crn: str) -> dict:
    rows = []
    earned = 0.0
    weight_done = 0
    for row in DB.scores.get(student_id, []):
        if row["crn"] != crn:
            continue
        score, maximum, weight = float(row["score"]), float(row["max_score"]), int(row["weight_percent"])
        percent = score / maximum * 100 if maximum else 0
        earned += percent * weight / 100
        weight_done += weight
        rows.append({
            **row, "percent": percent, "weight": weight,
            "score_label": f"{score:g} / {maximum:g}",
            "contribution": percent * weight / 100,
            "date_label": nice_date(row["date"]),
        })
    average = earned / weight_done * 100 if weight_done else None
    letter = None
    if average is not None:
        rounded = math.floor(average + 0.5)
        for grade, info in DB.scale.items():
            if info["min_score"] and int(info["min_score"]) <= rounded <= int(info["max_score"]):
                letter = grade
                break
    return {"rows": rows, "average": average, "letter": letter, "weight_done": weight_done,
            "earned": earned, "weight_left": 100 - weight_done}


def scores_overview(student_id: str, classes: list[dict]) -> dict[str, dict]:
    return {item["crn"]: course_scores(student_id, item["crn"]) for item in classes}


def course_detail(student_id: str, crn: str) -> dict | None:
    classes = current_classes(student_id)
    item = next((c for c in classes if c["crn"] == crn), None)
    if item is None:
        return None
    full = DB.courses_full.get(item["code"], {})
    report = attendance_report(student_id, classes)
    return {
        "item": item,
        "description": full.get("description", ""),
        "prerequisites": full.get("prerequisites", ""),
        "attendance": next((r for r in report["rows"] if r["crn"] == crn), None),
        "as_of": report["as_of"],
        "exam": next((e for e in exam_report([item])["items"]), None),
        "scores": course_scores(student_id, crn),
    }


def gpa_calculator(student_id: str, record: dict, classes: list[dict]) -> dict:
    fails = {row["course_code"]: row for row in record["replaced"]}
    open_fails = {
        row["course_code"]: row for row in record["rows"]
        if is_fail(row["letter_grade"]) and not row["replaced_in"]
    }
    grades = [
        {"letter": letter, "points": float(info["quality_points"]),
         "passes": info["earns_credit"] == "Yes"}
        for letter, info in DB.scale.items()
        if info["counts_in_gpa"] == "Yes"
    ]
    scores = scores_overview(student_id, classes)
    return {
        "basePoints": float(record["points"]),
        "baseCredits": record["gpa_credits"],
        "currentGpa": record["gpa"],
        "grades": grades,
        "courses": [{
            "crn": item["crn"],
            "code": item["code"],
            "title": item["title"],
            "credits": item["credits_int"],
            "grade": scores[item["crn"]]["letter"] or "",
            "suggested": scores[item["crn"]]["letter"] or "",
            "priorFail": (
                {"letter": open_fails[item["code"]]["letter_grade"],
                 "credits": open_fails[item["code"]]["credits_int"]}
                if item["code"] in open_fails else None
            ),
        } for item in classes],
        "alreadyReplaced": len(fails),
    }


def entry_log_days(student_id: str) -> list[dict]:
    days: dict[str, dict] = {}
    for row in sorted(DB.entry_logs.get(student_id, []), key=lambda r: r["timestamp"]):
        day, clock = row["timestamp"].split(" ")
        entry = days.setdefault(day, {"date": day, "events": []})
        entry["events"].append({**row, "clock": clock})
    result = []
    for day, entry in sorted(days.items(), reverse=True):
        value = parse_date(day)
        entry["label"] = f"{value.strftime('%A')}, {value.day} {value.strftime('%b %Y')}"
        first_in = next((e for e in entry["events"] if e["direction"] == "In"), None)
        last_out = next((e for e in reversed(entry["events"]) if e["direction"] == "Out"), None)
        entry["in"] = first_in
        entry["out"] = last_out
        entry["duration"] = ""
        if first_in and last_out:
            minutes = to_minutes(last_out["clock"]) - to_minutes(first_in["clock"])
            if minutes > 0:
                entry["duration"] = f"{minutes // 60}h {minutes % 60:02d}m"
        result.append(entry)
    return result


def contacts(student_id: str, classes: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for item in classes:
        person = item["instructor"]
        if not person:
            continue
        entry = seen.setdefault(person["faculty_id"], {**person, "teaches": []})
        entry["teaches"].append(item["code"])
    return sorted(seen.values(), key=lambda p: p["last_name"])


def alerts(student: dict, record: dict, attendance: dict, holds: dict,
           ticket: dict | None, exams: dict) -> list[dict]:
    items = []
    for hold in holds["blocking"]:
        items.append({
            "level": "danger", "title": f"Registration blocked: {hold['hold_type']} hold",
            "text": f"{hold['reason']}. Contact {hold['office']}.",
            "href": "/holds", "action": "View hold",
        })
    if student["on_probation"]:
        gpa = f"{record['gpa']:.2f}" if record["gpa"] is not None else "–"
        items.append({
            "level": "danger", "title": student["academic_standing"],
            "text": f"Your cumulative GPA is {gpa}, below the 2.00 minimum. Talk to your advisor.",
            "href": "/transcript", "action": "See grades",
        })
    for row in attendance["rows"]:
        if row["level"] == "alert":
            appeal = f" Appeal: {row['appeal']}." if row["appeal"] else ""
            items.append({
                "level": "danger", "title": f"{row['code']}: {row['percent_label']} absences",
                "text": f"{row['absences']} of {row['allotted']} meetings missed. Over 15% leads to a WF grade.{appeal}",
                "href": "/attendance", "action": "View attendance",
            })
    for row in attendance["rows"]:
        if row["level"] == "second":
            items.append({
                "level": "warning", "title": f"{row['code']}: second attendance warning",
                "text": f"{row['percent_label']} absences. "
                        + ("You have reached the limit: one more absence puts you over 15%."
                           if row["left"] == 0 else
                           f"{row['left']} more before you pass 15%." if row["left"] > 1 else
                           "1 more and you reach the limit."),
                "href": "/attendance", "action": "View attendance",
            })
    for hold in holds["active"]:
        if not hold["blocks"]:
            items.append({
                "level": "warning", "title": f"{hold['hold_type']} hold",
                "text": f"{hold['reason']}. It does not block registration.",
                "href": "/holds", "action": "View hold",
            })
    if exams["clashes"]:
        items.append({
            "level": "warning", "title": "Exam time clash",
            "text": "Two of your final exams overlap. Contact your advisor.",
            "href": "/exams", "action": "View exams",
        })
    return items


# Published by ZU Library (zu.libguides.com, zu.libcal.com). The student CSV files
# hold no borrowing records, so no personal loans or due dates are shown.
LIBRARY = {
    "home": "https://www.zu.ac.ae/main/en/library/index.aspx",
    "rooms": "https://zu.libcal.com/spaces",
    "consultation": "https://zu.libcal.com/appointments/online",
    "aisha": "https://aisha.zu.ac.ae",
    "aisha_guide": "https://zu.libguides.com/ai/aisha-chatbot",
    "loan_rules": "https://zu.libguides.com/borrowing/loanperiods",
    "renew": "https://zu.libguides.com/borrowing/users",
    "quota": "20 books, including up to 4 multimedia items",
    "book_loan": "3 weeks",
    "media_loan": "7 days",
    "room_types": [
        "Group study rooms", "Quiet study rooms", "Presentation rooms",
    ],
    "campuses": {
        "AUH": {"name": "Abu Dhabi", "email": "library@zu.ac.ae",
                "circulation": "02 599 3627", "reference": "02 599 3840"},
        "DXB": {"name": "Dubai", "email": "librarydxb@zu.ac.ae",
                "circulation": "04 402 1701", "reference": "04 402 1702"},
    },
}


def library_info(student: dict, holds: dict) -> dict:
    related = [
        hold for hold in holds["active"]
        if "library" in f"{hold['hold_type']} {hold['reason']} {hold['office']}".lower()
    ]
    return {**LIBRARY, "campus": LIBRARY["campuses"].get(student["campus"]), "notices": related}


def library_preview(student_id: str, classes: list[dict], library: dict) -> dict:
    """Sample content for the library screens. The CSV files have no loans or room data."""
    offsets = [-6 if library["notices"] else 4, 11, 16]
    books = []
    for item, offset in zip(classes[:3], offsets):
        due = date.fromordinal(TODAY.toordinal() + offset)
        books.append({
            "title": f"Course reading: {item['title']}", "code": item["code"],
            "due": f"{due.strftime('%a')} {due.day} {due.strftime('%b %Y')}",
            "days": offset, "overdue": offset < 0,
        })
    days = []
    for offset in range(5):
        value = date.fromordinal(TODAY.toordinal() + offset)
        days.append({"weekday": value.strftime("%a"), "label": f"{value.day} {value.strftime('%b')}"})
    renewed = date.fromordinal(TODAY.toordinal() + 21)
    return {
        "books": books, "days": days,
        "renewed_label": f"{renewed.strftime('%a')} {renewed.day} {renewed.strftime('%b %Y')}",
        "slots": [f"{hour:02d}:00" for hour in range(9, 17)],
        "rooms": [
            {"name": "Group study room", "detail": "Up to 8 people", "floor": "2nd floor"},
            {"name": "Quiet study room", "detail": "Individual study", "floor": "2nd floor"},
            {"name": "Presentation room", "detail": "Screen and whiteboard", "floor": "2nd floor"},
        ],
    }


PARKING_ZONES = {
    "Main Gate": ("Zone A", 180), "Gate 2 (Parking)": ("Zone B", 320), "Gate 3 (Library)": ("Zone C", 140),
}


def parking_view(student_id: str) -> dict | None:
    """Arrival patterns are real entry-log data. Capacity and free spaces are simulated."""
    campus = DB.students[student_id]["campus"]
    mine = [r for r in DB.entry_logs.get(student_id, []) if r["direction"] == "In"]
    if not mine:
        return None
    clock = lambda row: to_minutes(row["timestamp"].split(" ")[1])
    usual = round(sum(clock(r) for r in mine) / len(mine))
    gates = Counter(r["gate"] for r in mine)
    favorite = gates.most_common(1)[0][0]
    arrivals = [r for rows in DB.entry_logs.values() for r in rows if r["campus"] == campus and r["direction"] == "In"]

    bins = []
    for start in range(7 * 60, 10 * 60, 30):
        count = sum(1 for r in arrivals if start <= clock(r) < start + 30)
        bins.append({"label": f"{start // 60:02d}:{start % 60:02d}", "count": count, "mine": start <= usual < start + 30})
    peak = max(b["count"] for b in bins) or 1
    for item in bins:
        item["height"] = round(item["count"] / peak * 100)
        item["peak"] = item["count"] == peak

    zones = []
    for gate, (name, capacity) in PARKING_ZONES.items():
        rows = [r for r in arrivals if r["gate"] == gate]
        share = sum(1 for r in rows if clock(r) <= usual) / len(rows) if rows else 0
        used = round(capacity * min(.96, share * .94))
        free = capacity - used
        percent = round(free / capacity * 100)
        zones.append({
            "name": name, "gate": gate, "capacity": capacity, "free": free, "percent": percent,
            "used_percent": 100 - percent, "favorite": gate == favorite,
            "level": "good" if percent >= 40 else "warn" if percent >= 20 else "bad",
            "uses": gates.get(gate, 0),
        })
    best = max(zones, key=lambda z: z["percent"] + (8 if z["favorite"] else 0))
    for zone in zones:
        zone["best"] = zone is best
    quiet = min(bins, key=lambda b: b["count"])
    return {
        "usual": f"{usual // 60:02d}:{usual % 60:02d}", "favorite": favorite, "visits": len(mine),
        "bins": bins, "zones": sorted(zones, key=lambda z: not z["best"]), "best": best, "quiet": quiet,
    }


def dashboard(student_id: str) -> dict:
    student = profile(student_id)
    record = academic_record(student_id)
    classes = current_classes(student_id)
    attendance = attendance_report(student_id, classes)
    holds = holds_report(student_id)
    ticket = time_ticket(student_id, holds)
    audit = degree_audit(student_id, record, classes)
    exams = exam_report(classes)
    return {
        "student": student,
        "record": record,
        "classes": classes,
        "today": todays_classes(classes),
        "attendance": attendance,
        "holds": holds,
        "ticket": ticket,
        "audit": audit,
        "exams": exams,
        "alerts": alerts(student, record, attendance, holds, ticket, exams),
        "news": DB.news[:3],
        "term_credits": sum(c["credits_int"] for c in classes),
        "library": library_info(student, holds),
    }
