# A Better ZU SAP

A modern Student Access Portal built for Vibe Code Jam 2026. It loads the challenge CSV files from `data/` when it starts. No student data is stored in the code.

## Run

```powershell
uv sync
uv run uvicorn main:app --port 8000
```

Open <http://127.0.0.1:8000> and sign in with a `student_id` and `password` from `data/core/students.csv`. On Windows, `.\run.ps1` does the same. Styling, fonts and scripts are served locally, so the core app works offline.

## ZU Assistant

The assistant answers common questions from the signed-in student's own record with no setup. To let Claude answer free-form questions, set `ANTHROPIC_API_KEY` in the terminal before starting the app. If the service is unavailable, the assistant falls back to the built-in answers.

## Where the numbers come from

- **GPA:** sum of (quality points × credits) ÷ sum of credits, over grades in `grades.csv` that count in GPA according to `grade_scale.csv`. A later passing grade replaces an F in the cumulative GPA. Transfer credits are excluded.
- **Term GPA:** the same formula for one term, as the grades were earned that term.
- **Degree audit:** each row of `degree_requirements.csv` is matched to passed courses and transfer equivalents (Done), this term's registrations (In progress), or neither (Remaining). Other courses fill elective rows. Progress = completed requirement credits ÷ 120.
- **Attendance:** absences ÷ `meetings_allotted`. Warnings at 5% and 10%, alert above 15%.
- **Holds:** a hold is active while `released_date` is empty. An active hold with `blocks_registration = Yes` blocks registration.

## Preview screens

Smart Parking uses real arrival times from `entry_logs.csv`, but its zones and free spaces are simulated. Library room availability and borrowed books are sample content. Both screens are labelled Preview. Library loan rules and links come from ZU Library's public pages.

## Code map

`portal_data.py` holds the rules, `main.py` the routes, `assistant.py` the assistant, `pdf_export.py` the PDF exports, `i18n.py` and `i18n_data.py` the Arabic text, and `templates/` the pages.
