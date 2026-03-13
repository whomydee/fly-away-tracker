# Fly Away Tracker

**Self-update rule:** After making changes to the codebase, update the relevant sections of this file to reflect the current state. Keep descriptions concise. If adding new files, pages, or DB tables, document them here.

## Tech Stack

- **Streamlit** (>=1.40) — UI framework
- **Plotly** — donut charts and visualizations
- **SQLite** — local database at `./data/tracker.db`
- **Python 3** — run with `streamlit run app.py`

## Project Structure

```
app.py                          Entrypoint: config, CSS, DB init, sidebar, router
db.py                           Database layer (schema, CRUD, queries)
progress.py                     Progress calculation and status derivation
requirements.txt                Python dependencies (streamlit, plotly)
data/                           SQLite database directory (gitignored)
  uploads/                      Uploaded attachment files (UUID-named, gitignored)
pages/                          Page modules (one per route)
  __init__.py
  helpers.py                    Shared utilities: nav_to, parse_deadline, build_user_progress, render_donut, importance helpers, attachment helpers
  dashboard.py                  Dashboard page
  user_progress.py              User progress overview hub (journey bar, burn-up chart, nav cards)
  tasks.py                      Tasks page (sections/milestones/tasks management)
  university_analysis.py        University analysis page
  rubric_manage.py              Rubric management page
```

## Database Schema (db.py)

| Table                  | Purpose                                           |
|------------------------|---------------------------------------------------|
| `users`                | User profiles (id, name, icon, start_date, target_date) |
| `sections`             | Top-level progress categories per user (weighted)  |
| `milestones`           | Grouped goals within a section (status, deadline)  |
| `tasks`                | Individual items within a milestone (status, deadline) |
| `rubric_questions`     | University evaluation criteria with weights        |
| `rubric_evaluations`   | Per-question, per-university scores + text answers  |
| `university_analyses`  | Per-university reasons to pick / not to pick       |
| `progress_snapshots`   | Daily progress snapshots per user (date, progress, task counts) |
| `attachments`          | Files/links attached to university analyses or rubric evaluations (polymorphic via `parent_type` + `parent_id`) |

Key helpers: `get_university_scores()` calculates weighted rankings across all rubric evaluations. `get_user_tasks()` fetches all tasks for a user with section/milestone context via JOIN. Attachment files stored as UUID-named files in `data/uploads/`; `upsert_rubric_evaluation()` and `upsert_university_analysis()` return the row ID. Deleting a university cascades to delete all associated attachments (files + DB rows).

## App Pages

Routing is via `st.query_params` with `page` and `user_id` (router in `app.py`).
Each page function receives `(conn, users, ...)` — no module-level globals.

| Page key        | Module                          | Function                          | Description                                                  |
|-----------------|---------------------------------|-----------------------------------|--------------------------------------------------------------|
| `dashboard`     | `pages/dashboard.py`           | `page_dashboard(conn, users)`     | Overview cards for all users with progress bars               |
| `user`          | `pages/user_progress.py`       | `page_user_progress(conn, users, uid)` | Overview hub: donut, upcoming tasks, journey bar, burn-up chart, nav cards to Tasks & University Analysis |
| `tasks`         | `pages/tasks.py`               | `page_tasks(conn, users, uid)`    | Sections/milestones/tasks management with nested expanders, inline editing, task dialogs |
| `analysis`      | `pages/university_analysis.py` | `page_university_analysis(conn, users, uid)` | Ranked university table + per-university details dialog |
| `rubric_manage` | `pages/rubric_manage.py`       | `page_rubric_manage(conn, users, uid)` | View/edit/add rubric questions with importance levels    |

`@st.dialog` is used for "Add University Analysis" (university analysis page), "Add Task", "Edit Task" (tasks page) and "Details" (university analysis page).
Task dialogs are rendered at page level via `_handle_task_dialogs()` for stable widget positioning.

Left sidebar shows nested navigation per user: Overview, Tasks, Universities (if rubric data exists), Rubric.

## Rubric Importance Levels

Rubric question weights are presented to the user as importance levels (defined in `helpers.py`):
- **High** (weight 2.0, red) — **Moderate** (weight 1.5, amber) — **Low** (weight 1.0, blue)
- Numeric weights are stored in DB and used for score calculations; users only see/pick importance labels.

## Rubric Score Levels

Rubric evaluations use qualitative score labels instead of 1-10 sliders (defined in `helpers.py`):
- **Good** (score 8, green) — **Moderate** (score 5, amber) — **Bad** (score 2, red)
- Each evaluation also has a `text_answer` column for detailed descriptions.
- `score_to_label()` maps numeric scores back to labels (>=7 Good, >=4 Moderate, <4 Bad).

## Users

- **Maria** — university/fly-away prep (has rubric questions + university analyses)
- **Shad** — job/interview prep (no rubric data)

## Progress Logic (progress.py)

- Weighted progress: tasks roll up into milestones, milestones into sections, sections into overall
- Status completion: `complete=1.0`, `in_progress=0.5`, `not_started=0.0`
- Status labels: `ahead`, `on_track`, `behind` — derived from milestone deadlines

## UX Patterns

- Sections and milestones use nested `st.expander` (collapsed by default, state retained via stable labels)
- Progress bars rendered ABOVE each expander so they're visible when collapsed
- Section/milestone edit fields shown inline inside expanders (no edit popover) with Save button
- Only Delete buttons remain (via `st.popover` for confirmation)
- "Add Task" opens `@st.dialog` with full fields (title, description, deadline, weight, notes)
- Task editing: inline status selector + edit icon (opens dialog) + delete popover
- Condensed CSS applied globally for tighter vertical spacing

## Conventions

- UUIDs for all primary keys (`uuid.uuid4()`)
- Timestamps stored as ISO strings
- Seed data in `db.seed()` — resets all tables and populates sample data
- All DB writes call `conn.commit()` immediately
- Custom CSS injected via `st.markdown(unsafe_allow_html=True)` for styled cards/tables
