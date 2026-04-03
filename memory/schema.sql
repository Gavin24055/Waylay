-- J — SQLite Schema
-- All structured data tables for the personal AI life OS.

CREATE TABLE IF NOT EXISTS conversations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL DEFAULT (datetime('now')),
    role        TEXT    NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content     TEXT    NOT NULL,
    session_id  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS people (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT    NOT NULL UNIQUE,
    relationship     TEXT,
    notes            TEXT,
    last_interaction TEXT,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS projects (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL UNIQUE,
    stack      TEXT,
    status     TEXT    DEFAULT 'active',
    notes      TEXT,
    updated_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER REFERENCES projects(id),
    title       TEXT    NOT NULL,
    status      TEXT    DEFAULT 'todo' CHECK (status IN ('todo', 'in_progress', 'done', 'blocked')),
    priority    TEXT    DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    done_at     TEXT
);

CREATE TABLE IF NOT EXISTS health_sleep (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    date    TEXT    NOT NULL,
    hours   REAL    NOT NULL,
    quality TEXT    CHECK (quality IN ('terrible', 'bad', 'ok', 'good', 'great')),
    notes   TEXT
);

CREATE TABLE IF NOT EXISTS health_mood (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL DEFAULT (datetime('now')),
    mood            TEXT    NOT NULL,
    sentiment_score REAL,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS health_water (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    date    TEXT    NOT NULL,
    glasses INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS health_exercise (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    date         TEXT    NOT NULL,
    type         TEXT    NOT NULL,
    duration_min INTEGER NOT NULL,
    notes        TEXT
);

CREATE TABLE IF NOT EXISTS finance_expenses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT    NOT NULL DEFAULT (date('now')),
    amount_inr  REAL    NOT NULL,
    category    TEXT    NOT NULL,
    description TEXT,
    method      TEXT    DEFAULT 'upi'
);

CREATE TABLE IF NOT EXISTS finance_budgets (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    month      TEXT    NOT NULL,
    category   TEXT    NOT NULL,
    budget_inr REAL    NOT NULL,
    UNIQUE(month, category)
);

CREATE TABLE IF NOT EXISTS finance_savings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    target_inr  REAL    NOT NULL,
    current_inr REAL    NOT NULL DEFAULT 0,
    deadline    TEXT
);

CREATE TABLE IF NOT EXISTS stock_watchlist (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT    NOT NULL UNIQUE,
    alert_above REAL,
    alert_below REAL,
    notes       TEXT
);

CREATE TABLE IF NOT EXISTS diecast_collection (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    brand         TEXT,
    scale         TEXT,
    acquired_date TEXT,
    price_inr     REAL,
    notes         TEXT
);

CREATE TABLE IF NOT EXISTS onboarding_questions (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    question  TEXT    NOT NULL,
    asked_date TEXT,
    answer    TEXT,
    answered  INTEGER NOT NULL DEFAULT 0
);
