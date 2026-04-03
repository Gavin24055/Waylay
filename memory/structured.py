"""
J — Structured Memory (SQLite)
CRUD operations for all structured data tables.
"""

import sqlite3
import logging
from datetime import datetime, date
from pathlib import Path
from config import DB_PATH, SCHEMA_PATH

logger = logging.getLogger("j.memory.structured")


class StructuredMemory:
    """SQLite-backed structured memory for J."""

    def __init__(self):
        self.db_path = str(DB_PATH)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        """Create all tables from schema.sql and seed onboarding questions."""
        schema_sql = SCHEMA_PATH.read_text()
        with self._get_conn() as conn:
            conn.executescript(schema_sql)
            # Seed onboarding questions if table is empty
            count = conn.execute("SELECT COUNT(*) FROM onboarding_questions").fetchone()[0]
            if count == 0:
                questions = [
                    "What's stressing you most right now in life?",
                    "What do you actually want your life to look like by end of 2026?",
                    "How often do you call home? Are you close with your family?",
                    "What are you saving towards — any specific goal?",
                    "How's your sleep been honestly — do you want me to help fix it?",
                    "What does Sandra like? What makes her happy?",
                    "Tell me about your diecast collection — what do you have?",
                    "Where do you see yourself career-wise in 3 years?",
                    "What are your biggest pet peeves — things that just irritate you?",
                    "Tell me more about you and Vaishak — how'd you meet?",
                ]
                conn.executemany(
                    "INSERT INTO onboarding_questions (question) VALUES (?)",
                    [(q,) for q in questions],
                )
        logger.info("SQLite database initialised at %s", self.db_path)

    # ── Conversations ────────────────────────────────────────────
    def save_conversation(self, role: str, content: str, session_id: str):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO conversations (role, content, session_id) VALUES (?, ?, ?)",
                (role, content, session_id),
            )

    def get_recent_conversations(self, session_id: str, limit: int = 20) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT role, content, timestamp FROM conversations WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    # ── People ───────────────────────────────────────────────────
    def save_person(self, name: str, relationship: str = None, notes: str = None):
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO people (name, relationship, notes, last_interaction)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(name) DO UPDATE SET
                     relationship = COALESCE(excluded.relationship, relationship),
                     notes = COALESCE(excluded.notes, notes),
                     last_interaction = excluded.last_interaction""",
                (name, relationship, notes, datetime.now().isoformat()),
            )

    def get_person(self, name: str) -> dict | None:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM people WHERE name = ?", (name,)).fetchone()
        return dict(row) if row else None

    # ── Projects ─────────────────────────────────────────────────
    def save_project(self, name: str, stack: str = None, status: str = "active", notes: str = None):
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO projects (name, stack, status, notes)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(name) DO UPDATE SET
                     stack = COALESCE(excluded.stack, stack),
                     status = excluded.status,
                     notes = COALESCE(excluded.notes, notes),
                     updated_at = datetime('now')""",
                (name, stack, status, notes),
            )

    def get_project(self, name: str) -> dict | None:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM projects WHERE name LIKE ?", (f"%{name}%",)).fetchone()
        return dict(row) if row else None

    # ── Tasks ────────────────────────────────────────────────────
    def add_task(self, project_id: int, title: str, priority: str = "medium") -> int:
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO tasks (project_id, title, priority) VALUES (?, ?, ?)",
                (project_id, title, priority),
            )
            return cur.lastrowid

    def update_task_status(self, task_id: int, status: str):
        done_at = datetime.now().isoformat() if status == "done" else None
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE tasks SET status = ?, done_at = ? WHERE id = ?",
                (status, done_at, task_id),
            )

    def get_tasks(self, project_name: str = None, status: str = None) -> list[dict]:
        query = """SELECT t.*, p.name as project_name FROM tasks t
                   LEFT JOIN projects p ON t.project_id = p.id WHERE 1=1"""
        params = []
        if project_name:
            query += " AND p.name LIKE ?"
            params.append(f"%{project_name}%")
        if status:
            query += " AND t.status = ?"
            params.append(status)
        query += " ORDER BY t.priority DESC, t.created_at DESC"
        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def get_tasks_today(self) -> list[dict]:
        today = date.today().isoformat()
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT t.*, p.name as project_name FROM tasks t
                   LEFT JOIN projects p ON t.project_id = p.id
                   WHERE t.status != 'done'
                   ORDER BY CASE t.priority
                     WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                     WHEN 'medium' THEN 2 ELSE 3 END""",
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Health: Sleep ────────────────────────────────────────────
    def log_sleep(self, hours: float, quality: str = None, notes: str = None):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO health_sleep (date, hours, quality, notes) VALUES (?, ?, ?, ?)",
                (date.today().isoformat(), hours, quality, notes),
            )

    # ── Health: Mood ─────────────────────────────────────────────
    def log_mood(self, mood: str, sentiment_score: float = None, notes: str = None):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO health_mood (mood, sentiment_score, notes) VALUES (?, ?, ?)",
                (mood, sentiment_score, notes),
            )

    # ── Health: Water ────────────────────────────────────────────
    def log_water(self, glasses: int = 1):
        today = date.today().isoformat()
        with self._get_conn() as conn:
            existing = conn.execute("SELECT id, glasses FROM health_water WHERE date = ?", (today,)).fetchone()
            if existing:
                conn.execute(
                    "UPDATE health_water SET glasses = glasses + ? WHERE id = ?",
                    (glasses, existing["id"]),
                )
            else:
                conn.execute("INSERT INTO health_water (date, glasses) VALUES (?, ?)", (today, glasses))

    def get_water_today(self) -> int:
        today = date.today().isoformat()
        with self._get_conn() as conn:
            row = conn.execute("SELECT glasses FROM health_water WHERE date = ?", (today,)).fetchone()
        return row["glasses"] if row else 0

    # ── Health: Exercise ─────────────────────────────────────────
    def log_exercise(self, exercise_type: str, duration_min: int, notes: str = None):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO health_exercise (date, type, duration_min, notes) VALUES (?, ?, ?, ?)",
                (date.today().isoformat(), exercise_type, duration_min, notes),
            )

    def health_summary(self, days: int = 7) -> dict:
        with self._get_conn() as conn:
            sleep = conn.execute(
                "SELECT AVG(hours) as avg_hours FROM health_sleep WHERE date >= date('now', ?)",
                (f"-{days} days",),
            ).fetchone()
            water = conn.execute(
                "SELECT AVG(glasses) as avg_glasses FROM health_water WHERE date >= date('now', ?)",
                (f"-{days} days",),
            ).fetchone()
            exercise = conn.execute(
                "SELECT COUNT(*) as sessions, SUM(duration_min) as total_min FROM health_exercise WHERE date >= date('now', ?)",
                (f"-{days} days",),
            ).fetchone()
        return {
            "avg_sleep_hours": round(sleep["avg_hours"], 1) if sleep["avg_hours"] else 0,
            "avg_water_glasses": round(water["avg_glasses"], 1) if water["avg_glasses"] else 0,
            "exercise_sessions": exercise["sessions"] or 0,
            "exercise_total_min": exercise["total_min"] or 0,
        }

    # ── Finance: Expenses ────────────────────────────────────────
    def log_expense(self, amount_inr: float, category: str, description: str = None, method: str = "upi"):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO finance_expenses (amount_inr, category, description, method) VALUES (?, ?, ?, ?)",
                (amount_inr, category, description, method),
            )

    def budget_status(self, month: str = None) -> list[dict]:
        if not month:
            month = date.today().strftime("%Y-%m")
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT b.category, b.budget_inr,
                          COALESCE(SUM(e.amount_inr), 0) as spent_inr
                   FROM finance_budgets b
                   LEFT JOIN finance_expenses e
                     ON b.category = e.category AND strftime('%Y-%m', e.date) = b.month
                   WHERE b.month = ?
                   GROUP BY b.category""",
                (month,),
            ).fetchall()
        return [dict(r) for r in rows]

    def savings_progress(self) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM finance_savings").fetchall()
        return [dict(r) for r in rows]

    # ── Stock Watchlist ──────────────────────────────────────────
    def add_stock_alert(self, symbol: str, alert_above: float = None, alert_below: float = None, notes: str = None):
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO stock_watchlist (symbol, alert_above, alert_below, notes)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(symbol) DO UPDATE SET
                     alert_above = COALESCE(excluded.alert_above, alert_above),
                     alert_below = COALESCE(excluded.alert_below, alert_below),
                     notes = COALESCE(excluded.notes, notes)""",
                (symbol.upper(), alert_above, alert_below, notes),
            )

    def get_stock_watchlist(self) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM stock_watchlist").fetchall()
        return [dict(r) for r in rows]

    # ── Diecast Collection ───────────────────────────────────────
    def add_diecast(self, name: str, brand: str = None, scale: str = None,
                    price_inr: float = None, notes: str = None):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO diecast_collection (name, brand, scale, acquired_date, price_inr, notes) VALUES (?, ?, ?, ?, ?, ?)",
                (name, brand, scale, date.today().isoformat(), price_inr, notes),
            )

    # ── Onboarding Questions ────────────────────────────────────
    def get_next_onboarding_question(self) -> dict | None:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM onboarding_questions WHERE answered = 0 ORDER BY id ASC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def mark_question_answered(self, question_id: int, answer: str):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE onboarding_questions SET answered = 1, answer = ?, asked_date = ? WHERE id = ?",
                (answer, date.today().isoformat(), question_id),
            )

    # ── Finance Report ───────────────────────────────────────────
    def finance_report(self, month: str = None) -> dict:
        if not month:
            month = date.today().strftime("%Y-%m")
        with self._get_conn() as conn:
            total = conn.execute(
                "SELECT COALESCE(SUM(amount_inr), 0) as total FROM finance_expenses WHERE strftime('%Y-%m', date) = ?",
                (month,),
            ).fetchone()
            by_category = conn.execute(
                """SELECT category, SUM(amount_inr) as total, COUNT(*) as count
                   FROM finance_expenses WHERE strftime('%Y-%m', date) = ?
                   GROUP BY category ORDER BY total DESC""",
                (month,),
            ).fetchall()
        return {
            "month": month,
            "total_spent": total["total"],
            "by_category": [dict(r) for r in by_category],
        }
