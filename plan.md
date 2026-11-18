# Hackathon Build Plan

**Status:** Ready. Waiting for the challenge.
**Goal:** A working, polished, responsive web app in 90 minutes, on desktop and mobile, in Edge and Chrome.

## Problem Statement

> **TO BE PROVIDED**

## Must-Have Features / Branding

> **TO BE PROVIDED**

## 90-Minute Time Budget

| Minutes | Work | Done when |
|---|---|---|
| 0-10 | Read challenge, lock scope, update this file | Core user flow fits in one sentence |
| 10-20 | Scaffold, data model, layout shell | Starter app runs with renamed domain |
| 20-55 | Core features, end to end | Main flow works with real data |
| 55-75 | UI polish, mobile pass, empty/loading/error states | No broken state at phone width |
| 75-85 | Seed demo data, full run-through in Edge and Chrome | Demo works twice in a row |
| 85-90 | Buffer and demo script | Nothing new gets added |

---

## 1. Stack & Architecture Decision

**Frontend:** Jinja2 templates, HTMX, Alpine.js, Tailwind CSS through the CDN.
**Backend:** FastAPI with SQLite through Python's built-in `sqlite3`, managed by `uv`.

This is the fastest route because there is no build step, and Node is not installed on this machine. The server renders HTML, and HTMX swaps it into the page, so there is one codebase, no API client and no duplicated state. Alpine covers small interactions such as live filtering. Tailwind gives polished, responsive UI directly in the markup. SQLite needs no setup and keeps demo data across restarts.

Reconsider this only if the challenge needs heavy client-side state, such as a drag-and-drop canvas.

---

## 2. UI/UX Design System

These are defaults. Replace the colors if the challenge gives branding.

| Token | Hex | Use |
|---|---|---|
| Primary (`primary`) | `#0F766E` | Main actions, active navigation |
| Primary dark (`primary-dark`) | `#115E59` | Hover and pressed states |
| Secondary (`secondary`) | `#1E293B` | Headings, sidebar |
| Background (`background`) | `#F8FAF9` | Page background |
| Accent (`accent`) | `#F59E0B` | Highlights, use sparingly, with dark text |
| Surface (`surface`) | `#FFFFFF` | Cards and inputs |
| Border (`line`) | `#E2E8F0` | Dividers and outlines |
| Muted (`muted`) | `#64748B` | Supporting text |
| Success (`success`) | `#15803D` | Positive status |
| Danger (`danger`) | `#B91C1C` | Errors and destructive actions |

**Typography:** Space Grotesk for headings, Inter for body text.

**Layout:** Fixed sidebar with main content on desktop (`md` and up). Bottom navigation on mobile. Touch targets are at least 44px.

**Components:** `.btn`, `.btn-primary`, `.btn-ghost`, `.card`, `.input`, `.badge`, `.badge-success`, `.badge-accent`, `.skeleton`, `.toast`.

#### `templates/partials/head.html`

```html
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.tailwindcss.com/3.4.17"></script>
<script>
  tailwind.config = {
    theme: {
      extend: {
        colors: {
          primary: { DEFAULT: "#0F766E", dark: "#115E59" },
          secondary: "#1E293B",
          background: "#F8FAF9",
          accent: "#F59E0B",
          surface: "#FFFFFF",
          line: "#E2E8F0",
          muted: "#64748B",
          success: "#15803D",
          danger: "#B91C1C",
        },
        fontFamily: {
          sans: ["Inter", "system-ui", "sans-serif"],
          display: ["Space Grotesk", "Inter", "sans-serif"],
        },
        boxShadow: { soft: "0 1px 2px rgb(15 23 42 / 0.04), 0 8px 24px rgb(15 23 42 / 0.06)" },
      },
    },
  };
</script>
<style type="text/tailwindcss">
  @layer base {
    body { @apply bg-background font-sans text-secondary antialiased; }
    h1, h2, h3 { @apply font-display tracking-tight; }
    :focus-visible { @apply outline-none ring-2 ring-primary ring-offset-2; }
  }
  @layer components {
    .btn { @apply inline-flex min-h-[44px] items-center justify-center gap-2 rounded-xl px-4 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60; }
    .btn-primary { @apply bg-primary text-white hover:bg-primary-dark; }
    .btn-ghost { @apply text-muted hover:bg-slate-100 hover:text-secondary; }
    .card { @apply rounded-2xl border border-line bg-surface shadow-soft; }
    .input { @apply min-h-[44px] w-full rounded-xl border border-line bg-surface px-3 text-sm placeholder:text-muted focus:border-primary; }
    .badge { @apply inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold; }
    .badge-success { @apply bg-green-100 text-success; }
    .badge-accent { @apply bg-amber-100 text-amber-800; }
    .skeleton { @apply animate-pulse rounded-lg bg-slate-200; }
    .toast { @apply rounded-xl bg-secondary px-4 py-3 text-sm font-medium text-white shadow-soft; }
    .toast-error { @apply bg-danger; }
  }
</style>
<style>
  [x-cloak] { display: none !important; }
  .empty-state { display: none; }
  ul:not(:has(li)) + .empty-state { display: block; }
  @media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
</style>
<script src="https://cdn.jsdelivr.net/npm/htmx.org@2.0.4/dist/htmx.min.js" defer></script>
<script src="https://cdn.jsdelivr.net/npm/alpinejs@3.14.8/dist/cdn.min.js" defer></script>
<script src="/static/app.js" defer></script>
```

---

## 3. Setup Commands (PowerShell, using `uv`)

`uv` is not installed on this machine yet, so install it first.

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

If company policy blocks that, use this instead:

```powershell
python -m pip install --user uv
```

Reopen the terminal, then run these from `c:\Users\ituser\Documents\Ahadu`:

```powershell
uv init --bare
uv add fastapi "uvicorn[standard]" jinja2 python-multipart
New-Item -ItemType Directory -Force templates\partials, static
```

---

## 4. The Codebase

This starter is complete and runs as is. It is built around a generic `items` resource, which gets renamed to fit the challenge.

```text
Ahadu/
  main.py
  static/app.js
  templates/base.html
  templates/index.html
  templates/partials/head.html    (in section 2)
  templates/partials/item.html
  templates/partials/stats.html
```

#### `main.py`

```python
import json
import sqlite3
from collections.abc import Iterator
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

APP_NAME = "Hackathon App"
MAX_TITLE_LENGTH = 120
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "app.db"

SEED_ITEMS = [
    ("Read the challenge brief", "Agree on the one flow to demo.", 1),
    ("Build the core flow", "Make it work end to end with real data.", 0),
    ("Polish the mobile layout", "Check every screen at phone width.", 0),
]


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_db() -> None:
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                done INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        if conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO items (title, notes, done, created_at) VALUES (?, ?, ?, ?)",
                [(title, notes, done, now()) for title, notes, done in SEED_ITEMS],
            )


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title=APP_NAME, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
templates.env.globals["app_name"] = APP_NAME


def list_items(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM items ORDER BY id DESC").fetchall()
    return [dict(row) for row in rows]


def get_item(conn: sqlite3.Connection, item_id: int) -> dict:
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Item not found.")
    return dict(row)


def get_stats(conn: sqlite3.Connection) -> dict:
    row = conn.execute(
        "SELECT COUNT(*) AS total, COALESCE(SUM(done), 0) AS done FROM items"
    ).fetchone()
    total, done = row["total"], row["done"]
    return {
        "total": total,
        "done": done,
        "open": total - done,
        "progress": round(done / total * 100) if total else 0,
    }


def render(name: str, **context) -> str:
    return templates.get_template(name).render(**context)


def fragment(html: str, toast: str) -> HTMLResponse:
    return HTMLResponse(html, headers={"HX-Trigger": json.dumps({"toast": toast})})


def stats_oob(conn: sqlite3.Connection) -> str:
    return render("partials/stats.html", stats=get_stats(conn), oob=True)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    with db() as conn:
        context = {"items": list_items(conn), "stats": get_stats(conn), "oob": False}
    return templates.TemplateResponse(request, "index.html", context)


@app.post("/items", response_class=HTMLResponse)
def create_item(title: str = Form(""), notes: str = Form("")):
    title = title.strip()
    notes = notes.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Please enter a title.")
    if len(title) > MAX_TITLE_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"Title must be {MAX_TITLE_LENGTH} characters or fewer.",
        )
    with db() as conn:
        cursor = conn.execute(
            "INSERT INTO items (title, notes, done, created_at) VALUES (?, ?, 0, ?)",
            (title, notes, now()),
        )
        item = get_item(conn, cursor.lastrowid)
        html = render("partials/item.html", item=item) + stats_oob(conn)
    return fragment(html, "Item added")


@app.patch("/items/{item_id}/toggle", response_class=HTMLResponse)
def toggle_item(item_id: int):
    with db() as conn:
        get_item(conn, item_id)
        conn.execute("UPDATE items SET done = 1 - done WHERE id = ?", (item_id,))
        item = get_item(conn, item_id)
        html = render("partials/item.html", item=item) + stats_oob(conn)
    return fragment(html, "Marked done" if item["done"] else "Marked open")


@app.delete("/items/{item_id}", response_class=HTMLResponse)
def delete_item(item_id: int):
    with db() as conn:
        get_item(conn, item_id)
        conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        html = stats_oob(conn)
    return fragment(html, "Item deleted")


@app.get("/api/items")
def api_items():
    with db() as conn:
        return {"items": list_items(conn), "stats": get_stats(conn)}


@app.get("/health")
def health():
    return {"status": "ok"}
```

#### `templates/base.html`

```html
<!doctype html>
<html lang="en">
<head>
  <title>{% block title %}{{ app_name }}{% endblock %}</title>
  {% include "partials/head.html" %}
</head>
<body class="min-h-screen">
  <aside class="fixed inset-y-0 left-0 hidden w-64 flex-col bg-secondary p-5 text-white md:flex">
    <a href="/" class="flex items-center gap-3 font-display text-lg font-bold">
      <span class="grid h-9 w-9 place-items-center rounded-xl bg-accent text-secondary">{{ app_name[:1] }}</span>
      {{ app_name }}
    </a>
    <nav class="mt-8 space-y-1 text-sm font-medium" aria-label="Main">
      <a href="#overview" class="flex min-h-[44px] items-center rounded-xl bg-white/10 px-3">Overview</a>
      <a href="#items" class="flex min-h-[44px] items-center rounded-xl px-3 text-slate-300 hover:bg-white/10 hover:text-white">Items</a>
    </nav>
  </aside>

  <main class="px-4 pb-28 pt-6 sm:px-6 md:ml-64 md:px-10 md:pb-10 md:pt-10">
    <div class="mx-auto max-w-4xl">
      {% block content %}{% endblock %}
    </div>
  </main>

  <nav class="fixed inset-x-0 bottom-0 z-20 grid grid-cols-2 border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] text-sm font-semibold md:hidden" aria-label="Mobile">
    <a href="#overview" class="flex min-h-[56px] items-center justify-center text-primary">Overview</a>
    <a href="#items" class="flex min-h-[56px] items-center justify-center text-muted">Items</a>
  </nav>

  <div id="toasts" class="fixed inset-x-4 bottom-20 z-30 flex flex-col items-center gap-2 md:inset-x-auto md:bottom-6 md:right-6 md:items-end" aria-live="polite"></div>
</body>
</html>
```

#### `templates/index.html`

```html
{% extends "base.html" %}
{% block content %}
<header class="mb-6">
  <p class="text-sm font-semibold text-primary">Dashboard</p>
  <h1 class="mt-1 text-3xl font-bold sm:text-4xl">Keep the build moving</h1>
  <p class="mt-2 text-muted">Add work, track progress and see every change right away.</p>
</header>

<section id="overview" class="scroll-mt-6" aria-label="Overview">
  {% include "partials/stats.html" %}
</section>

<section class="card mt-6 p-4 sm:p-5" aria-labelledby="add-heading">
  <h2 id="add-heading" class="text-lg font-semibold">Add an item</h2>
  <form class="mt-3 grid gap-3 sm:grid-cols-[1fr_1fr_auto]"
        hx-post="/items"
        hx-target="#item-list"
        hx-swap="afterbegin"
        hx-disabled-elt="#create-button"
        hx-on::after-request="if (event.detail.successful) this.reset()">
    <label class="block">
      <span class="sr-only">Title</span>
      <input class="input" name="title" placeholder="What needs doing?" maxlength="120" required>
    </label>
    <label class="block">
      <span class="sr-only">Notes</span>
      <input class="input" name="notes" placeholder="Notes (optional)">
    </label>
    <button id="create-button" class="btn btn-primary" type="submit">Add item</button>
  </form>
</section>

<section id="items" class="mt-8 scroll-mt-6" x-data="{ q: '' }" aria-labelledby="items-heading">
  <div class="mb-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
    <h2 id="items-heading" class="text-xl font-semibold">Items</h2>
    <label class="block sm:w-64">
      <span class="sr-only">Filter items</span>
      <input class="input" type="search" placeholder="Filter items" x-model="q">
    </label>
  </div>
  <ul id="item-list" class="space-y-3">
    {% for item in items %}
      {% include "partials/item.html" %}
    {% endfor %}
  </ul>
  <div class="empty-state card p-8 text-center">
    <h3 class="font-semibold">Nothing here yet</h3>
    <p class="mt-1 text-sm text-muted">Add your first item above to get started.</p>
  </div>
</section>
{% endblock %}
```

#### `templates/partials/stats.html`

```html
<div id="stats" {% if oob %}hx-swap-oob="true"{% endif %} class="grid grid-cols-3 gap-3 sm:gap-4">
  <div class="card p-3 sm:p-5">
    <p class="text-xs font-medium text-muted sm:text-sm">Total</p>
    <p class="mt-1 font-display text-2xl font-bold sm:text-3xl">{{ stats.total }}</p>
  </div>
  <div class="card p-3 sm:p-5">
    <p class="text-xs font-medium text-muted sm:text-sm">Open</p>
    <p class="mt-1 font-display text-2xl font-bold sm:text-3xl">{{ stats.open }}</p>
  </div>
  <div class="card p-3 sm:p-5">
    <p class="text-xs font-medium text-muted sm:text-sm">Progress</p>
    <p class="mt-1 font-display text-2xl font-bold text-primary sm:text-3xl">{{ stats.progress }}%</p>
  </div>
</div>
```

#### `templates/partials/item.html`

```html
<li class="card flex items-center gap-2 p-2 sm:gap-3 sm:p-3"
    data-title="{{ item.title|lower }}"
    x-show="!q.trim() || $el.dataset.title.includes(q.trim().toLowerCase())">
  <button class="grid h-11 w-11 shrink-0 place-items-center rounded-xl hover:bg-slate-100"
          type="button"
          hx-patch="/items/{{ item.id }}/toggle"
          hx-target="closest li"
          hx-swap="outerHTML"
          aria-label="{{ 'Mark as open' if item.done else 'Mark as done' }}: {{ item.title }}">
    <span class="grid h-6 w-6 place-items-center rounded-full border-2 text-xs font-bold {{ 'border-primary bg-primary text-white' if item.done else 'border-slate-300 text-transparent' }}" aria-hidden="true">&#10003;</span>
  </button>
  <div class="min-w-0 flex-1">
    <p class="break-words font-medium {{ 'text-muted line-through' if item.done }}">{{ item.title }}</p>
    {% if item.notes %}<p class="break-words text-sm text-muted">{{ item.notes }}</p>{% endif %}
  </div>
  <span class="badge hidden sm:inline-flex {{ 'badge-success' if item.done else 'badge-accent' }}">{{ 'Done' if item.done else 'Open' }}</span>
  <button class="btn btn-ghost px-3"
          type="button"
          hx-delete="/items/{{ item.id }}"
          hx-target="closest li"
          hx-swap="outerHTML"
          hx-confirm="Delete this item?"
          aria-label="Delete: {{ item.title }}">Delete</button>
</li>
```

#### `static/app.js`

```javascript
function showToast(message, kind = "info") {
  const container = document.getElementById("toasts");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = kind === "error" ? "toast toast-error" : "toast";
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

function errorMessage(xhr) {
  try {
    const { detail } = JSON.parse(xhr.responseText);
    if (typeof detail === "string") return detail;
  } catch (_) {
    // The response was not JSON, so the general message below is used.
  }
  return "Something went wrong. Please try again.";
}

document.addEventListener("toast", (event) => showToast(event.detail.value));

document.addEventListener("htmx:responseError", (event) => {
  showToast(errorMessage(event.detail.xhr), "error");
});

document.addEventListener("htmx:sendError", () => {
  showToast("Cannot reach the server. Check that it is running.", "error");
});
```

### What changes once the challenge is known

1. `APP_NAME`, the page heading and the navigation labels.
2. The `items` table, its routes and `SEED_ITEMS`, renamed and reshaped for the challenge's domain.
3. The three stats in `get_stats` and `stats.html`.
4. The palette in `head.html`, if branding is provided.
5. After changing a table, delete `app.db` so it is recreated with the new columns.

---

## 5. Run Instructions

```powershell
uv run uvicorn main:app --reload
```

Open <http://127.0.0.1:8000>.

To test on a phone on the same network:

```powershell
uv run uvicorn main:app --reload --host 0.0.0.0
```

Find the computer's address with `ipconfig`, then open `http://<that-address>:8000` on the phone. Windows Firewall may ask for permission. The starter has no login, so use this only on a network you trust.

The fonts, Tailwind, HTMX and Alpine load from CDNs, so **the demo needs internet access**.

---

## Changelog

- **2026-11-18:** Initial blueprint created. Problem statement and branding still to come.
