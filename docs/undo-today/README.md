# undo-today

Undo today's completion: a habit marked done today can be un-marked the same day. The API removes
today's `Completion` row for that habit (idempotent, 404 for an unknown habit), and streaks, weekly
counts, at-risk and stats follow from the stored rows. Code: `app/api/habits.py`,
`app/services/habit_service.py`. Tests: `tests/test_habits_api.py`. Invariants `DAY-1`,
`STREAK-1`, `TIME-1`, `WEEK-1`, `OUT-1`, `DB-1` in `AGENTS.md`. Client half:
`../habit-tracker-client/docs/undo-today/`.

Related areas: `../habits/` (complete and freeze), `../streaks/` (streak and week math).

## design

- [2026-10-15-undo-today-contract.md](design/2026-10-15-undo-today-contract.md): change contract, primary (server and client sections)
- [2026-10-15-undo-today-design.md](design/2026-10-15-undo-today-design.md): design, primary (shared shape, server interfaces, settled decisions, the five ordered slices across both repositories)

## evidence

- [undo-today-server-1.verify.md](evidence/undo-today-server-1.verify.md): server slice 1 verification (`f709e49`, service `uncomplete_habit`), verdict green

## guides

(none yet)
