@../dev-agent-kit/WORKSPACE.md

# habit-tracker-server — agent guide

Compact map for agents working in this repository. Do not repeat what the code shows; point at
the file. Rationale lives in `docs/<feature>/guides/`. The four headed sections below are read
by the dev-agent-kit orchestration skill and checked by `bin/check`; keep their exact headings.

## What this is

A FastAPI + SQLAlchemy 2 API for one person's daily habits: create and edit habits, mark a day
done or frozen, and read streaks, weekly progress and aggregate stats. SQLite file at
`DB_URL` (default `/tmp/habits.db`, `app/config.py`), schema created at import time by
`Base.metadata.create_all` (`app/main.py`). Served by uvicorn on :8000; the Next.js client in
the sibling `../habit-tracker-client` is the only consumer.

## Subsystems

| Path | Responsibility |
|---|---|
| `app/main.py` | app factory: CORS, router mount, `/health`, `create_all` |
| `app/config.py` | `Settings` (pydantic-settings): `DB_URL`, `CORS_ORIGINS` |
| `app/database.py` | engine, `SessionLocal`, `Base`, the `get_db` dependency |
| `app/models/habit.py` | ORM: `Habit`, `Completion`, `Skip` (one row per habit-day, unique) |
| `app/schemas.py` | request/response models: `HabitCreate`, `HabitUpdate`, `HabitOut`, `HabitStats` |
| `app/api/habits.py` | the `/habits` router; resolves `date.today()` and 404s, no logic |
| `app/services/habit_service.py` | all logic: CRUD, streaks, weekly target, at-risk, stats, `to_summary` |
| `tests/conftest.py` | in-memory SQLite session + `TestClient` with `get_db` overridden |
| `tests/test_habit_service.py` | pure-function tests for streak and week math |
| `tests/test_habits_api.py` | endpoint tests through `TestClient` |

## Invariants

- `DAY-1` A habit-day is completed, skipped, or neither, never two: unique constraints on `completions` and `skips`; completing deletes a same-day skip; skipping a completed day raises `ValueError` → 409 (`habit_service.py`, `api/habits.py`).
- `STREAK-1` A skipped day neither extends nor breaks a streak; `compute_streak` and `compute_longest_streak` must keep treating skips identically (`habit_service.py`).
- `TIME-1` Only the router calls `date.today()`; every service function takes `today` as a parameter so tests pass explicit dates.
- `WEEK-1` Weeks start on Monday (`start_of_week`, `is_at_risk` use `weekday()`); the client's "week starts on" setting is not wired to this API.
- `OUT-1` Every habit response is `to_summary()` validated by `HabitOut`; a new field is added in `to_summary`, `HabitOut` and the client's `app/types/HabitTypes.ts` in the same feature.
- `DB-1` No migrations: `create_all` creates missing tables but never alters existing ones. A new column on `habits` breaks an existing database file; a new table does not (this is why `Skip` is a table, not a flag).
- `CORS-1` A browser origin not listed in `Settings.CORS_ORIGINS` cannot call the API.

## Mechanical gate

```
.venv/bin/python -m pytest -q          # 58 passed on main e90c38e (2026-10-15); no CI workflow exists
# no linter or formatter is configured in this repository
tests/test_habit_service.py for any change to compute_streak, compute_longest_streak, is_at_risk or count_completions_in_week
```

## Branching

Default branch `main`. Feature branches, PRs into `main`, merge commits (`main` already carries
`Merge feature/... into main` commits). Frozen during fan-out (Lead-owned; builders request changes by message):
`app/models/habit.py`, `app/schemas.py`, `requirements.txt`, `requirements-dev.txt`. Roster is
not pinned; name it at kickoff.

## Build, run, test

```
uv venv --python 3.13 .venv                 # pinned pydantic 2.10 has no wheels for the host 3.14
uv pip install --python .venv/bin/python -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload     # http://localhost:8000, docs at /docs
.venv/bin/python -m pytest -q
```

## Maintaining this file

Keep it a map. Prefer pruning over appending. Move rationale to `docs/<feature>/guides/` and link it.
