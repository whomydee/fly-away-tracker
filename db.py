"""Database layer using SQLite."""

import sqlite3
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "tracker.db"
UPLOADS_DIR = Path(__file__).parent / "data" / "uploads"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            icon TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sections (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            weight REAL NOT NULL DEFAULT 1.0,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS milestones (
            id TEXT PRIMARY KEY,
            section_id TEXT NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            description TEXT,
            deadline TIMESTAMP,
            weight REAL NOT NULL DEFAULT 1.0,
            status TEXT NOT NULL DEFAULT 'not_started'
                CHECK(status IN ('not_started','in_progress','complete')),
            notes TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            milestone_id TEXT NOT NULL REFERENCES milestones(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            description TEXT,
            deadline TIMESTAMP,
            weight REAL NOT NULL DEFAULT 1.0,
            status TEXT NOT NULL DEFAULT 'not_started'
                CHECK(status IN ('not_started','in_progress','complete')),
            notes TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS progress_snapshots (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            date TEXT NOT NULL,
            progress REAL NOT NULL DEFAULT 0.0,
            tasks_complete INTEGER NOT NULL DEFAULT 0,
            tasks_total INTEGER NOT NULL DEFAULT 0,
            UNIQUE(user_id, date)
        );
        CREATE TABLE IF NOT EXISTS rubric_questions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            question TEXT NOT NULL,
            weight REAL NOT NULL DEFAULT 1.0,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS rubric_evaluations (
            id TEXT PRIMARY KEY,
            question_id TEXT NOT NULL REFERENCES rubric_questions(id) ON DELETE CASCADE,
            university_name TEXT NOT NULL,
            answer TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS university_analyses (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            university_name TEXT NOT NULL,
            reason_to_pick TEXT,
            reason_not_to_pick TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, university_name)
        );
        CREATE TABLE IF NOT EXISTS attachments (
            id TEXT PRIMARY KEY,
            parent_type TEXT NOT NULL CHECK(parent_type IN ('university_analysis', 'rubric_evaluation')),
            parent_id TEXT NOT NULL,
            attachment_type TEXT NOT NULL CHECK(attachment_type IN ('image', 'pdf', 'link')),
            file_name TEXT,
            stored_name TEXT,
            url TEXT,
            file_size INTEGER,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_attachments_parent ON attachments(parent_type, parent_id);
    """)
    # Migration: add weight column if missing (existing DBs)
    try:
        conn.execute("ALTER TABLE rubric_questions ADD COLUMN weight REAL NOT NULL DEFAULT 1.0")
    except sqlite3.OperationalError:
        pass
    # Migration: add text_answer column if missing (existing DBs)
    try:
        conn.execute("ALTER TABLE rubric_evaluations ADD COLUMN text_answer TEXT")
    except sqlite3.OperationalError:
        pass
    # Migration: add start_date / target_date to users
    for col in ("start_date", "target_date"):
        try:
            conn.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass
    conn.commit()


def _uid() -> str:
    return str(uuid.uuid4())


def _future(days: int) -> str:
    return (datetime.now() + timedelta(days=days)).isoformat()


def _past(days: int) -> str:
    return (datetime.now() - timedelta(days=days)).isoformat()


def seed(conn: sqlite3.Connection) -> None:
    """Populate the database with sample data matching the Next.js version."""
    for table in [
        "attachments", "progress_snapshots",
        "university_analyses", "rubric_evaluations", "rubric_questions",
        "tasks", "milestones", "sections", "users",
    ]:
        conn.execute(f"DELETE FROM {table}")

    # Clear uploaded files
    if UPLOADS_DIR.exists():
        shutil.rmtree(UPLOADS_DIR)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    maria_id, shad_id = _uid(), _uid()
    now = datetime.now().isoformat()
    maria_start = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    maria_target = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
    shad_start = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d")
    shad_target = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")

    conn.execute(
        "INSERT INTO users VALUES (?,?,?,?,?,?)",
        (maria_id, "Maria", "graduation-cap", now, maria_start, maria_target),
    )
    conn.execute(
        "INSERT INTO users VALUES (?,?,?,?,?,?)",
        (shad_id, "Shad", "code", now, shad_start, shad_target),
    )

    def add_section(sid, uid, title, weight, order):
        conn.execute(
            "INSERT INTO sections VALUES (?,?,?,?,?,?,?)",
            (sid, uid, title, weight, order, now, now),
        )

    def add_milestone(mid, sid, title, deadline, weight, status, order):
        conn.execute(
            "INSERT INTO milestones VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (mid, sid, title, None, deadline, weight, status, None, order, now, now),
        )

    def add_task(mid, title, weight, status, order, deadline=None):
        conn.execute(
            "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (_uid(), mid, title, None, deadline, weight, status, None, order, now, now),
        )

    # --- Maria ---
    ielts_id = _uid()
    add_section(ielts_id, maria_id, "IELTS Preparation", 1.5, 0)
    ielts_m1, ielts_m2 = _uid(), _uid()
    add_milestone(ielts_m1, ielts_id, "Study Phase", _future(30), 1.0, "in_progress", 0)
    add_milestone(ielts_m2, ielts_id, "Practice & Exam", _future(60), 1.5, "not_started", 1)
    add_task(ielts_m1, "Complete vocabulary building", 1.0, "complete", 0)
    add_task(ielts_m1, "Practice reading comprehension", 1.0, "in_progress", 1)
    add_task(ielts_m1, "Writing practice essays", 1.0, "not_started", 2)
    add_task(ielts_m1, "Speaking practice sessions", 1.0, "not_started", 3)
    add_task(ielts_m2, "Take practice test 1", 1.0, "not_started", 0, _future(35))
    add_task(ielts_m2, "Take practice test 2", 1.0, "not_started", 1, _future(45))
    add_task(ielts_m2, "Book IELTS exam", 0.5, "not_started", 2, _future(50))
    add_task(ielts_m2, "Take IELTS exam", 2.0, "not_started", 3, _future(60))

    uni_sel_id = _uid()
    add_section(uni_sel_id, maria_id, "University Selection", 1.0, 1)
    uni_sel_m1 = _uid()
    add_milestone(uni_sel_m1, uni_sel_id, "Research & Compare", _future(45), 1.0, "in_progress", 0)
    add_task(uni_sel_m1, "Create evaluation rubric", 1.0, "complete", 0)
    add_task(uni_sel_m1, "Research 5 universities", 2.0, "in_progress", 1)
    add_task(uni_sel_m1, "Evaluate universities with rubric", 1.5, "not_started", 2)
    add_task(uni_sel_m1, "Finalize top 3 choices", 1.0, "not_started", 3)

    uni_app_id = _uid()
    add_section(uni_app_id, maria_id, "University Application", 2.0, 2)
    uni_app_m1, uni_app_m2 = _uid(), _uid()
    add_milestone(uni_app_m1, uni_app_id, "Prepare Documents", _future(50), 1.0, "not_started", 0)
    add_milestone(uni_app_m2, uni_app_id, "Submit Applications", _future(90), 1.5, "not_started", 1)
    add_task(uni_app_m1, "Write statement of purpose", 2.0, "not_started", 0)
    add_task(uni_app_m1, "Gather recommendation letters", 1.5, "not_started", 1)
    add_task(uni_app_m1, "Prepare transcripts", 1.0, "not_started", 2)
    add_task(uni_app_m1, "Update CV/Resume", 1.0, "not_started", 3)
    add_task(uni_app_m2, "Submit application to University 1", 1.0, "not_started", 0, _future(70))
    add_task(uni_app_m2, "Submit application to University 2", 1.0, "not_started", 1, _future(80))
    add_task(uni_app_m2, "Pay application fees", 0.5, "not_started", 2)

    # Importance: High=2.0, Moderate=1.5, Low=1.0
    rubric_data = [
        ("Is the program aligned with my career goals?", 2.0),    # High
        ("Is the tuition affordable?", 1.5),                       # Moderate
        ("Is the university located in a desirable city?", 1.0),   # Low
        ("What are the post-study work opportunities?", 2.0),      # High
        ("What is the program ranking?", 1.5),                     # Moderate
        ("Is there scholarship availability?", 1.0),               # Low
    ]
    rubric_q_ids = []
    for i, (q, w) in enumerate(rubric_data):
        qid = _uid()
        rubric_q_ids.append(qid)
        conn.execute(
            "INSERT INTO rubric_questions VALUES (?,?,?,?,?,?)",
            (qid, maria_id, q, w, i, now),
        )

    # Sample university analyses
    # Each entry: (uni_name, [(score, text_answer), ...], reason_pick, reason_not)
    sample_unis = [
        ("University of Toronto", [
            (8, "Strong CS and data science programs aligned with tech career goals"),
            (5, "Tuition is around $55K CAD/year for international students"),
            (9, "Toronto is a vibrant, multicultural city with great public transit"),
            (9, "3-year post-graduation work permit available, strong tech job market"),
            (9, "Consistently ranked top 3 in Canada, top 30 globally"),
            (4, "Very limited scholarships for international graduate students"),
        ], "Top-ranked program, great city, strong alumni network", "Very expensive, highly competitive admission"),
        ("University of British Columbia", [
            (7, "Good applied science programs but less specialized in target area"),
            (6, "Slightly cheaper than UofT but still expensive at $50K/year"),
            (10, "Vancouver is stunning — mountains, ocean, mild climate"),
            (8, "Good co-op programs help with employment, 3-year PGWP available"),
            (8, "Top 5 in Canada, well-respected internationally"),
            (5, "Some merit-based awards available but highly competitive"),
        ], "Beautiful campus, good co-op programs", "Far from family, high cost of living"),
        ("McGill University", [
            (7, "Solid program but more research-focused than applied"),
            (7, "More affordable — around $25K CAD/year for international students"),
            (8, "Montreal is a great cultural city, very affordable to live in"),
            (7, "Quebec has different immigration pathways, PEQ program is an option"),
            (8, "Top 3 in Canada, strong international reputation"),
            (6, "Some departmental funding available for graduate students"),
        ], "Affordable tuition, bilingual environment", "Cold winters, limited post-study work support"),
    ]
    for uni_name, score_answers, reason_pick, reason_not in sample_unis:
        for qid, (score, text_ans) in zip(rubric_q_ids, score_answers):
            upsert_rubric_evaluation(conn, qid, uni_name, str(score), text_ans)
        conn.execute(
            "INSERT INTO university_analyses VALUES (?,?,?,?,?,?,?)",
            (_uid(), maria_id, uni_name, reason_pick, reason_not, now, now),
        )

    # --- Shad ---
    ml_id = _uid()
    add_section(ml_id, shad_id, "Machine Learning", 2.0, 0)
    ml_m1, ml_m2, ml_m3 = _uid(), _uid(), _uid()
    add_milestone(ml_m1, ml_id, "Phase 1 - Foundation", _future(30), 1.0, "in_progress", 0)
    add_milestone(ml_m2, ml_id, "Phase 2 - Intensive Prep", _future(60), 1.5, "not_started", 1)
    add_milestone(ml_m3, ml_id, "Phase 3 - Interview Ready", _future(90), 1.0, "not_started", 2)
    add_task(ml_m1, "Review ML fundamentals", 1.0, "complete", 0)
    add_task(ml_m1, "Study supervised learning algorithms", 1.0, "in_progress", 1)
    add_task(ml_m1, "Study unsupervised learning", 1.0, "not_started", 2)
    add_task(ml_m1, "Deep learning basics", 1.0, "not_started", 3)
    add_task(ml_m2, "Build end-to-end ML project", 2.0, "not_started", 0)
    add_task(ml_m2, "Study production ML systems", 1.5, "not_started", 1)
    add_task(ml_m2, "ML case studies practice", 1.0, "not_started", 2)
    add_task(ml_m3, "Mock ML interviews", 2.0, "not_started", 0)
    add_task(ml_m3, "Review ML system design patterns", 1.0, "not_started", 1)

    ps_id = _uid()
    add_section(ps_id, shad_id, "Problem Solving", 1.5, 1)
    ps_m1, ps_m2 = _uid(), _uid()
    add_milestone(ps_m1, ps_id, "Phase 1 - Foundation", _future(30), 1.0, "in_progress", 0)
    add_milestone(ps_m2, ps_id, "Phase 2 - Advanced", _future(60), 1.5, "not_started", 1)
    add_task(ps_m1, "Review data structures", 1.0, "complete", 0)
    add_task(ps_m1, "Solve 50 easy LeetCode problems", 2.0, "in_progress", 1)
    add_task(ps_m1, "Study common algorithms", 1.0, "not_started", 2)
    add_task(ps_m2, "Solve 30 medium LeetCode problems", 2.0, "not_started", 0)
    add_task(ps_m2, "Solve 10 hard LeetCode problems", 1.5, "not_started", 1)
    add_task(ps_m2, "Mock coding interviews", 2.0, "not_started", 2)

    sd_id = _uid()
    add_section(sd_id, shad_id, "System Design", 1.5, 2)
    sd_m1 = _uid()
    add_milestone(sd_m1, sd_id, "Core Concepts", _future(45), 1.0, "not_started", 0)
    add_task(sd_m1, "Study distributed systems basics", 1.0, "not_started", 0)
    add_task(sd_m1, "Practice architecture design", 1.5, "not_started", 1)
    add_task(sd_m1, "Study ML infrastructure patterns", 1.0, "not_started", 2)
    add_task(sd_m1, "Scalability patterns", 1.0, "not_started", 3)

    port_id = _uid()
    add_section(port_id, shad_id, "Portfolio", 1.0, 3)
    port_m1 = _uid()
    add_milestone(port_m1, port_id, "Build Professional Presence", _future(60), 1.0, "not_started", 0)
    add_task(port_m1, "Update GitHub profile", 1.0, "not_started", 0)
    add_task(port_m1, "Build portfolio project 1", 2.0, "not_started", 1)
    add_task(port_m1, "Write technical blog post", 1.0, "not_started", 2)
    add_task(port_m1, "Update resume", 1.0, "not_started", 3)
    add_task(port_m1, "Optimize LinkedIn profile", 1.0, "not_started", 4)

    # --- Seed progress snapshots (simulate ~30 days of history for Maria, ~20 for Shad) ---
    # Maria: 19 tasks total, gradual progress over 30 days
    maria_snapshots = [
        (-30, 0.00, 0, 19), (-27, 0.02, 0, 19), (-24, 0.04, 1, 19),
        (-21, 0.06, 1, 19), (-18, 0.08, 1, 19), (-15, 0.10, 2, 19),
        (-12, 0.11, 2, 19), (-9, 0.12, 2, 19),  (-6, 0.13, 2, 19),
        (-3, 0.14, 2, 19),  (0, 0.15, 3, 19),
    ]
    for days_ago, progress, complete, total in maria_snapshots:
        d = (datetime.now() + timedelta(days=days_ago)).strftime("%Y-%m-%d")
        conn.execute(
            "INSERT INTO progress_snapshots VALUES (?,?,?,?,?,?)",
            (_uid(), maria_id, d, progress, complete, total),
        )

    # Shad: 22 tasks total, gradual progress over 20 days
    shad_snapshots = [
        (-20, 0.00, 0, 22), (-17, 0.02, 0, 22), (-14, 0.04, 1, 22),
        (-11, 0.06, 1, 22), (-8, 0.08, 2, 22),  (-5, 0.10, 2, 22),
        (-2, 0.11, 2, 22),  (0, 0.12, 2, 22),
    ]
    for days_ago, progress, complete, total in shad_snapshots:
        d = (datetime.now() + timedelta(days=days_ago)).strftime("%Y-%m-%d")
        conn.execute(
            "INSERT INTO progress_snapshots VALUES (?,?,?,?,?,?)",
            (_uid(), shad_id, d, progress, complete, total),
        )

    conn.commit()


# --- Query helpers ---

def get_users(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY name").fetchall()]


def get_sections(conn: sqlite3.Connection, user_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM sections WHERE user_id = ? ORDER BY sort_order",
        (user_id,),
    ).fetchall()]


def get_milestones(conn: sqlite3.Connection, section_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM milestones WHERE section_id = ? ORDER BY sort_order",
        (section_id,),
    ).fetchall()]


def get_tasks(conn: sqlite3.Connection, milestone_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM tasks WHERE milestone_id = ? ORDER BY sort_order",
        (milestone_id,),
    ).fetchall()]


def update_task_status(conn: sqlite3.Connection, task_id: str, status: str) -> None:
    conn.execute(
        "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
        (status, datetime.now().isoformat(), task_id),
    )
    conn.commit()


def update_milestone_status(conn: sqlite3.Connection, milestone_id: str, status: str) -> None:
    conn.execute(
        "UPDATE milestones SET status = ?, updated_at = ? WHERE id = ?",
        (status, datetime.now().isoformat(), milestone_id),
    )
    conn.commit()


def get_stats(conn: sqlite3.Connection) -> dict:
    total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    completed = conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'complete'").fetchone()[0]
    now = datetime.now().isoformat()
    week_later = (datetime.now() + timedelta(days=7)).isoformat()
    due_this_week = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE deadline IS NOT NULL AND deadline <= ? AND deadline >= ? AND status != 'complete'",
        (week_later, now),
    ).fetchone()[0]
    overdue = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE deadline IS NOT NULL AND deadline < ? AND status != 'complete'",
        (now,),
    ).fetchone()[0]
    return {
        "total_tasks": total,
        "completed_tasks": completed,
        "due_this_week": due_this_week,
        "overdue": overdue,
    }


def get_rubric_questions(conn: sqlite3.Connection, user_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM rubric_questions WHERE user_id = ? ORDER BY weight DESC, sort_order",
        (user_id,),
    ).fetchall()]


def get_rubric_evaluations(conn: sqlite3.Connection, question_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM rubric_evaluations WHERE question_id = ? ORDER BY university_name",
        (question_id,),
    ).fetchall()]


def upsert_rubric_evaluation(
    conn: sqlite3.Connection, question_id: str, university_name: str, answer: str,
    text_answer: str | None = None,
) -> str:
    existing = conn.execute(
        "SELECT id FROM rubric_evaluations WHERE question_id = ? AND university_name = ?",
        (question_id, university_name),
    ).fetchone()
    now = datetime.now().isoformat()
    if existing:
        eval_id = existing["id"]
        conn.execute(
            "UPDATE rubric_evaluations SET answer = ?, text_answer = ?, updated_at = ? WHERE id = ?",
            (answer, text_answer, now, eval_id),
        )
    else:
        eval_id = _uid()
        conn.execute(
            "INSERT INTO rubric_evaluations (id, question_id, university_name, answer, created_at, updated_at, text_answer) VALUES (?,?,?,?,?,?,?)",
            (eval_id, question_id, university_name, answer, now, now, text_answer),
        )
    conn.commit()
    return eval_id


# --- Section CRUD ---

def create_section(conn: sqlite3.Connection, user_id: str, title: str, weight: float = 1.0, sort_order: int = 0) -> str:
    sid = _uid()
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO sections VALUES (?,?,?,?,?,?,?)",
        (sid, user_id, title, weight, sort_order, now, now),
    )
    conn.commit()
    return sid


def update_section(conn: sqlite3.Connection, section_id: str, **fields) -> None:
    allowed = {"title", "weight", "sort_order"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return
    updates["updated_at"] = datetime.now().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(
        f"UPDATE sections SET {set_clause} WHERE id = ?",
        (*updates.values(), section_id),
    )
    conn.commit()


def delete_section(conn: sqlite3.Connection, section_id: str) -> None:
    conn.execute("DELETE FROM sections WHERE id = ?", (section_id,))
    conn.commit()


# --- Milestone CRUD ---

def create_milestone(
    conn: sqlite3.Connection, section_id: str, title: str,
    description: str | None = None, deadline: str | None = None,
    weight: float = 1.0, sort_order: int = 0,
) -> str:
    mid = _uid()
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO milestones VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (mid, section_id, title, description, deadline, weight, "not_started", None, sort_order, now, now),
    )
    conn.commit()
    return mid


def update_milestone(conn: sqlite3.Connection, milestone_id: str, **fields) -> None:
    allowed = {"title", "description", "deadline", "weight", "status", "notes", "sort_order"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    updates["updated_at"] = datetime.now().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(
        f"UPDATE milestones SET {set_clause} WHERE id = ?",
        (*updates.values(), milestone_id),
    )
    conn.commit()


def delete_milestone(conn: sqlite3.Connection, milestone_id: str) -> None:
    conn.execute("DELETE FROM milestones WHERE id = ?", (milestone_id,))
    conn.commit()


# --- Task CRUD ---

def create_task(
    conn: sqlite3.Connection, milestone_id: str, title: str,
    description: str | None = None, deadline: str | None = None,
    weight: float = 1.0, status: str = "not_started",
    notes: str | None = None, sort_order: int = 0,
) -> str:
    tid = _uid()
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (tid, milestone_id, title, description, deadline, weight, status, notes, sort_order, now, now),
    )
    conn.commit()
    return tid


def update_task(conn: sqlite3.Connection, task_id: str, **fields) -> None:
    allowed = {"title", "description", "deadline", "weight", "status", "notes", "sort_order"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    updates["updated_at"] = datetime.now().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(
        f"UPDATE tasks SET {set_clause} WHERE id = ?",
        (*updates.values(), task_id),
    )
    conn.commit()


def delete_task(conn: sqlite3.Connection, task_id: str) -> None:
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()


# --- Rubric Question CRUD ---

def create_rubric_question(conn: sqlite3.Connection, user_id: str, question: str, sort_order: int = 0, weight: float = 1.0) -> str:
    qid = _uid()
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO rubric_questions VALUES (?,?,?,?,?,?)",
        (qid, user_id, question, weight, sort_order, now),
    )
    conn.commit()
    return qid


def update_rubric_question(conn: sqlite3.Connection, question_id: str, **fields) -> None:
    allowed = {"question", "weight", "sort_order"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(
        f"UPDATE rubric_questions SET {set_clause} WHERE id = ?",
        (*updates.values(), question_id),
    )
    conn.commit()


def delete_rubric_question(conn: sqlite3.Connection, question_id: str) -> None:
    conn.execute("DELETE FROM rubric_questions WHERE id = ?", (question_id,))
    conn.commit()


# --- Rubric Evaluation delete ---

def delete_rubric_evaluation(conn: sqlite3.Connection, evaluation_id: str) -> None:
    conn.execute("DELETE FROM rubric_evaluations WHERE id = ?", (evaluation_id,))
    conn.commit()


def delete_rubric_evaluations_by_university(conn: sqlite3.Connection, user_id: str, university_name: str) -> None:
    conn.execute("""
        DELETE FROM rubric_evaluations WHERE university_name = ?
        AND question_id IN (SELECT id FROM rubric_questions WHERE user_id = ?)
    """, (university_name, user_id))
    conn.commit()


def get_next_sort_order(conn: sqlite3.Connection, table: str, parent_col: str, parent_id: str) -> int:
    row = conn.execute(
        f"SELECT COALESCE(MAX(sort_order), -1) + 1 FROM {table} WHERE {parent_col} = ?",
        (parent_id,),
    ).fetchone()
    return row[0]


# --- University Analysis CRUD ---

def get_university_analyses(conn: sqlite3.Connection, user_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM university_analyses WHERE user_id = ? ORDER BY university_name",
        (user_id,),
    ).fetchall()]


def get_university_analysis(conn: sqlite3.Connection, user_id: str, university_name: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM university_analyses WHERE user_id = ? AND university_name = ?",
        (user_id, university_name),
    ).fetchone()
    return dict(row) if row else None


def upsert_university_analysis(
    conn: sqlite3.Connection, user_id: str, university_name: str,
    reason_to_pick: str | None = None, reason_not_to_pick: str | None = None,
) -> str:
    now = datetime.now().isoformat()
    existing = conn.execute(
        "SELECT id FROM university_analyses WHERE user_id = ? AND university_name = ?",
        (user_id, university_name),
    ).fetchone()
    if existing:
        analysis_id = existing["id"]
        conn.execute(
            "UPDATE university_analyses SET reason_to_pick = ?, reason_not_to_pick = ?, updated_at = ? WHERE id = ?",
            (reason_to_pick, reason_not_to_pick, now, analysis_id),
        )
    else:
        analysis_id = _uid()
        conn.execute(
            "INSERT INTO university_analyses VALUES (?,?,?,?,?,?,?)",
            (analysis_id, user_id, university_name, reason_to_pick, reason_not_to_pick, now, now),
        )
    conn.commit()
    return analysis_id


def delete_university_analysis(conn: sqlite3.Connection, user_id: str, university_name: str) -> None:
    # Cascade-delete attachments for the analysis itself
    analysis = conn.execute(
        "SELECT id FROM university_analyses WHERE user_id = ? AND university_name = ?",
        (user_id, university_name),
    ).fetchone()
    if analysis:
        delete_attachments_for_parent(conn, "university_analysis", analysis["id"])

    # Cascade-delete attachments for related rubric evaluations
    eval_rows = conn.execute("""
        SELECT re.id FROM rubric_evaluations re
        JOIN rubric_questions rq ON re.question_id = rq.id
        WHERE re.university_name = ? AND rq.user_id = ?
    """, (university_name, user_id)).fetchall()
    for ev in eval_rows:
        delete_attachments_for_parent(conn, "rubric_evaluation", ev["id"])

    conn.execute(
        "DELETE FROM university_analyses WHERE user_id = ? AND university_name = ?",
        (user_id, university_name),
    )
    delete_rubric_evaluations_by_university(conn, user_id, university_name)


def get_user_tasks(conn: sqlite3.Connection, user_id: str) -> list[dict]:
    """Get all tasks for a user with section/milestone context."""
    rows = conn.execute("""
        SELECT t.*, m.title AS milestone_title, s.title AS section_title, s.id AS section_id
        FROM tasks t
        JOIN milestones m ON t.milestone_id = m.id
        JOIN sections s ON m.section_id = s.id
        WHERE s.user_id = ?
        ORDER BY t.deadline ASC, t.weight DESC
    """, (user_id,)).fetchall()
    return [dict(r) for r in rows]


def get_university_scores(conn: sqlite3.Connection, user_id: str) -> list[dict]:
    """Calculate ranked university scores from rubric evaluations."""
    questions = get_rubric_questions(conn, user_id)
    if not questions:
        return []

    # Gather all scores per university
    uni_scores: dict[str, dict[str, int]] = {}
    for q in questions:
        for ev in get_rubric_evaluations(conn, q["id"]):
            uni = ev["university_name"]
            if uni not in uni_scores:
                uni_scores[uni] = {}
            try:
                uni_scores[uni][q["id"]] = int(ev["answer"])
            except (ValueError, TypeError):
                uni_scores[uni][q["id"]] = 0

    # Calculate weighted percentage
    total_weight = sum(q.get("weight", 1.0) for q in questions)
    max_possible = total_weight * 10  # max score per question is 10

    results = []
    analyses = {a["university_name"]: a for a in get_university_analyses(conn, user_id)}
    for uni, scores in uni_scores.items():
        weighted = sum(
            scores.get(q["id"], 0) * q.get("weight", 1.0)
            for q in questions
        )
        pct = (weighted / max_possible * 100) if max_possible > 0 else 0
        analysis = analyses.get(uni, {})
        results.append({
            "name": uni,
            "weighted_score": weighted,
            "pct": pct,
            "reason_to_pick": analysis.get("reason_to_pick", ""),
            "reason_not_to_pick": analysis.get("reason_not_to_pick", ""),
        })

    results.sort(key=lambda x: x["weighted_score"], reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1

    return results


# --- User dates ---

def update_user_dates(conn: sqlite3.Connection, user_id: str, start_date: str | None = None, target_date: str | None = None) -> None:
    if start_date is not None:
        conn.execute("UPDATE users SET start_date = ? WHERE id = ?", (start_date, user_id))
    if target_date is not None:
        conn.execute("UPDATE users SET target_date = ? WHERE id = ?", (target_date, user_id))
    conn.commit()


# --- Progress snapshots ---

def record_snapshot(conn: sqlite3.Connection, user_id: str, progress: float, tasks_complete: int, tasks_total: int) -> None:
    """Record a daily progress snapshot (upserts on same day)."""
    today = datetime.now().strftime("%Y-%m-%d")
    existing = conn.execute(
        "SELECT id FROM progress_snapshots WHERE user_id = ? AND date = ?",
        (user_id, today),
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE progress_snapshots SET progress = ?, tasks_complete = ?, tasks_total = ? WHERE id = ?",
            (progress, tasks_complete, tasks_total, existing["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO progress_snapshots VALUES (?,?,?,?,?,?)",
            (_uid(), user_id, today, progress, tasks_complete, tasks_total),
        )
    conn.commit()


def get_snapshots(conn: sqlite3.Connection, user_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM progress_snapshots WHERE user_id = ? ORDER BY date",
        (user_id,),
    ).fetchall()]


# --- Attachment helpers ---

def save_attachment_file(file_bytes: bytes, original_name: str) -> str:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(original_name).suffix
    stored_name = f"{uuid.uuid4()}{ext}"
    (UPLOADS_DIR / stored_name).write_bytes(file_bytes)
    return stored_name


def delete_attachment_file(stored_name: str) -> None:
    path = UPLOADS_DIR / stored_name
    if path.exists():
        path.unlink()


def get_attachment_file_path(stored_name: str) -> Path:
    return UPLOADS_DIR / stored_name


def create_attachment(
    conn: sqlite3.Connection, parent_type: str, parent_id: str,
    attachment_type: str, file_name: str | None = None,
    stored_name: str | None = None, url: str | None = None,
    file_size: int | None = None, sort_order: int = 0,
) -> str:
    aid = _uid()
    conn.execute(
        "INSERT INTO attachments (id, parent_type, parent_id, attachment_type, file_name, stored_name, url, file_size, sort_order, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (aid, parent_type, parent_id, attachment_type, file_name, stored_name, url, file_size, sort_order, datetime.now().isoformat()),
    )
    conn.commit()
    return aid


def get_attachments(conn: sqlite3.Connection, parent_type: str, parent_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM attachments WHERE parent_type = ? AND parent_id = ? ORDER BY sort_order, created_at",
        (parent_type, parent_id),
    ).fetchall()]


def delete_attachment(conn: sqlite3.Connection, attachment_id: str) -> None:
    row = conn.execute("SELECT stored_name FROM attachments WHERE id = ?", (attachment_id,)).fetchone()
    if row and row["stored_name"]:
        delete_attachment_file(row["stored_name"])
    conn.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
    conn.commit()


def delete_attachments_for_parent(conn: sqlite3.Connection, parent_type: str, parent_id: str) -> None:
    rows = conn.execute(
        "SELECT id, stored_name FROM attachments WHERE parent_type = ? AND parent_id = ?",
        (parent_type, parent_id),
    ).fetchall()
    for row in rows:
        if row["stored_name"]:
            delete_attachment_file(row["stored_name"])
    conn.execute(
        "DELETE FROM attachments WHERE parent_type = ? AND parent_id = ?",
        (parent_type, parent_id),
    )
    conn.commit()
