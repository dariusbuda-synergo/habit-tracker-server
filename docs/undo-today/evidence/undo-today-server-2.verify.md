# Verification — undo-today / server-2

> Builder model: sonnet · Verifier model: opus
> Every number below is the observed output of a command named next to it. Never assumed,
> never copied from the builder.

Slice under test: `cc10249` (`undo-today slice 2: route DELETE /habits/{habit_id}/complete with endpoint tests`)
on `feature/undo-today`, parent `f81ea81` (slice 1 verify), base main `ceea25a`. All commands
were run from the worktree `.claude/worktrees/undo-today` with its `.venv`.

## Mechanical gate

| Command | Result | Counts |
|---|---|---|
| `.venv/bin/python -m pytest -q` at `cc10249` | pass (exit 0) | `70 passed, 1 warning` |
| same command on a `git archive f81ea81` export (scratch dir, same venv) | pass | `60 passed, 1 warning` (baseline before this slice) |
| `.venv/bin/python -m pytest -v -k uncomplete tests/test_habits_api.py` | pass | `10 passed, 40 deselected`: the ten new endpoint tests |
| `grep -c "^def test_" tests/test_habits_api.py` at `cc10249` / `git show f81ea81:tests/test_habits_api.py \| grep -c "^def test_"` | n/a | `50` / `40` |
| linter / formatter | n/a | none configured (`AGENTS.md § Mechanical gate`) |

Delta 70 − 60 = **+10**: the design's nine plus `test_uncomplete_only_affects_the_given_habit`,
added by the Lead after the slice 1 advisory. The one warning is the starlette
`anyio.abc.BlockingPortal` deprecation, present on the baseline too. The gate was run again after
every mutation probe was restored: `70 passed`, `git status --short` printed 0 lines.

## Invariants

| Code | Checked how | Result |
|---|---|---|
| `TIME-1` | `grep -n "date.today" app/api/habits.py`: the new route has one call at line 65 (`today = date.today()`); lines 66 and 67 pass that same `today` to `habit_service.uncomplete_habit` and `habit_service.to_summary`. Probe P8 replaces `app.api.habits.date` with a fake whose second `today()` call returns tomorrow and spies on both service functions: one call, service and summary got the same date. The service is unchanged in this slice (`git diff --quiet f81ea81..cc10249 -- app/services/habit_service.py` exit 0). | pass |
| `OUT-1` | Line 60 `@router.delete("/{habit_id}/complete", response_model=HabitOut)`; line 67 `return habit_service.to_summary(habit, today)`. Probe P7: OpenAPI `200` response `$ref` ends in `/HabitOut`. `app/schemas.py` unchanged (below). | pass |
| `DAY-1` / D3 | Builder test 8 (`..._after_freeze_then_complete_leaves_day_neither`) asserts `completed_today` false, `skipped_today` false, `skipped_days == []`. Probe P6: undo on a frozen, not-completed day leaves the `Skip` row (count 1) and `skipped_today` true, so the route never touches skips. | pass |
| D5 | `sed -n '60,67p' app/api/habits.py \| grep -c archived` → `0`: no archived check. Builder test 9 and probe P9: archived habit undo → 200, `archived` true, today not in `completed_days`. | pass |
| `STREAK-1` / `WEEK-1` | Not touched (service file unchanged). Builder tests 5 and 6, probe P5 (yesterday, 2 days ago, 9 days ago kept; `streak` 2, `longest_streak` 2 after undo). | pass |
| `DB-1` | `git diff --quiet f81ea81..cc10249 -- app/models/habit.py app/schemas.py app/main.py app/config.py app/services/habit_service.py requirements.txt requirements-dev.txt` → exit 0. | pass |
| `CORS-1` | No change needed: `app/main.py:15` `allow_methods=["*"]` already admits `DELETE`; `app/main.py` unchanged (same command). | pass |

Scope: `git diff --name-only f81ea81..cc10249` prints exactly `app/api/habits.py` and
`tests/test_habits_api.py`. `git diff -U0 f81ea81..cc10249 -- app/api/habits.py | grep -c '^-[^-]'`
→ `0` removed lines: the route file change is purely additive. No frozen file touched.

## Design and contract conformance

- **Route text.** The eight lines at `app/api/habits.py:60-67` and the route block in the design's
  § Interfaces → Server, extracted to scratch files and compared with `diff` → exit 0:
  byte-identical. Placement: directly after `complete_habit` (`:50-57`), before `skip_habit` (`:70`),
  as specified. No `try/except`.
- **Frozen cross-repository contract, each clause:**
  - Path and verb `DELETE /habits/{habit_id}/complete`, no request body: probe P7 (OpenAPI path has
    `post` and `delete`, the delete has no `requestBody`, `operationId` starts `uncomplete_habit`).
  - `200 HabitOut`, `completed_today == false` afterwards: builder tests 1, 8, 9, 10; probes P1, P4.
  - Idempotent, body unchanged: builder test 2 (body equals the `GET /habits` entry); probe P1 (two
    undos in a row → 200 and 200, identical bodies).
  - Archived allowed: builder test 9; probe P9.
  - `404 {"detail": "Habit not found"}`: builder test 3 asserts the exact body; probe P2 (after
    `DELETE /habits/{id}`, the undo route returns that exact 404).
  - `422` for a non-int id: probe P3 (`/habits/abc/complete` → 422, `loc == ["path", "habit_id"]`,
    `type == "int_parsing"`; `/habits/1.5/complete` → 422).
  - `HabitOut` and `app/schemas.py` unchanged (`DB-1` row).
- **Tests.** All ten exist after `test_unskip_unknown_habit_404s` (`tests/test_habits_api.py:310`),
  at `:315-406`, with the design's names and assertions: removes (200, `completed_today` false, today
  not in `completed_days`, `streak` 0); idempotent (equals the `GET /habits` entry); 404 with exact
  body; complete again (`completed_today` true, `streak` 1); anchored on yesterday (seeded via
  `db_session`, 2 → `streak` 1, `longest_streak` 1); `completed_this_week` 1 → 0; stats
  `completed_today` and `total_completions` 1 → 0; freeze → complete → undo neither; archived allowed.
  The tenth, `test_uncomplete_only_affects_the_given_habit`, completes two habits, undoes one, and
  checks via `GET /habits` and `/habits/stats` that the other stays completed. Imports match the
  design (`from datetime import date, timedelta`; `from app.models.habit import Completion`).
- **Settled decisions.** D1, D2, D3, D5 and A1 (route function name `uncomplete_habit`) hold. The
  slice touched no unsettled decision (§ Decisions left to implementation: "None").
- **Deviation:** one, sanctioned. +10 tests instead of the design's +9, by the Lead's instruction.

**The cross-repository contract (route `DELETE /habits/{habit_id}/complete` and the `HabitOut`
200 response, 404 `{"detail": "Habit not found"}`, 422 for a non-int id) is now frozen as designed.
`build-client-undo-today-1` may start from it.**

## Adversarial probes

Probes P1–P9 were a throwaway pytest file in the session scratch directory, outside the repository,
run with `PYTHONPATH=. .venv/bin/python -m pytest -q -p no:cacheprovider -p tests.conftest --rootdir=. <scratch>/probe_route.py`
so the repository's own `client` and `db_session` fixtures applied. Nothing was committed. Result on
`cc10249`: `9 passed`. On the first run P5 failed because my own expectation was wrong:
after undo, the longest run is yesterday plus the day before, so 2, not 3. I fixed the probe's
expectation and did not touch the code. The rerun gave `9 passed`.

| # | Probe | Result |
|---|---|---|
| P1 | Complete, then `DELETE /habits/{id}/complete` twice: both 200, bodies identical, `completed_today` false. | pass |
| P2 | `DELETE /habits/{id}` on a completed habit → 204, empty body, gone from `GET /habits`, 0 `Completion` rows (cascade). The new route does not shadow it. A following undo → 404 `{"detail": "Habit not found"}`. | pass |
| P3 | `DELETE /habits/abc/complete` and `/habits/1.5/complete` → 422, `int_parsing` on `path.habit_id`. | pass |
| P4 | Two habits, undo one; its `GET /habits` entry equals the DELETE body. No `GET /habits/{id}` route exists (that request returns 405), so the list is the read-back. | pass |
| P5 | Seed completions 1, 2 and 9 days ago, complete today, undo: `completed_days` is exactly the three earlier days, `streak` 2, `longest_streak` 2, 3 rows in the DB. | pass |
| P6 | Freeze today (no completion), undo: `skipped_today` stays true, 1 `Skip` row. | pass |
| P7 | `app.openapi()`: the path has `{post, delete}`. The delete has no `requestBody`, its 200 response refs `HabitOut`, and it lists a 422. `DELETE /habits/{habit_id}` still lists 204. | pass |
| P8 | `TIME-1` race detector: `app.api.habits.date` is replaced with a subclass whose `today()` returns tomorrow on the second call. Both service functions are spied on. Result: 1 call, and the service and `to_summary` received the same date. | pass |
| P9 | Archived habit: complete, archive, undo → 200, `archived` true, today absent from `completed_days`. | pass |

Mutation probes. Each was applied in place to the new route in `app/api/habits.py` by a script,
then restored with `git checkout -- app/api/habits.py`. `shasum` before was `57f600758516`, and every
restore returned `57f600758516`. After all six, `git status --short` printed 0 lines and
`git diff --quiet cc10249` exited 0.

| Mutation | Builder's 10 (`pytest -q -k uncomplete tests/test_habits_api.py`) | Full gate | My probes |
|---|---|---|---|
| M1 service gets `date(2000, 1, 1)` instead of `today` | `7 failed, 3 passed` | `7 failed, 63 passed` | `4 failed, 5 passed` |
| M2 `to_summary` gets `date(2000, 1, 1)` instead of `today` | `1 failed, 9 passed` (`..._keeps_streak_anchored_on_yesterday`) | `1 failed, 69 passed` | `3 failed, 6 passed` |
| M3 404 check dropped | `1 failed, 9 passed` (`..._unknown_habit_404s`) | `1 failed, 69 passed` | `1 failed, 8 passed` |
| M4 service call dropped | `7 failed, 3 passed` | `7 failed, 63 passed` | `4 failed, 5 passed` |
| M5 `to_summary(habit, date.today())` (second resolution) | `10 passed`: **survives the builder's tests** | `70 passed` | `1 failed, 8 passed` (P8) |
| M6 404 detail text changed to `"Not found"` | `1 failed, 9 passed` (`..._unknown_habit_404s`) | `1 failed, 69 passed` | `1 failed, 8 passed` |

Finding (test gap, not a defect): the builder's tests can't tell one `date.today()` from two (M5).
Two calls would only behave differently across midnight. The code under test resolves it once, and
P8 proves this. M2 is caught by only one builder test, so the "same `today` to both" half of `TIME-1`
rests on that single test (plus P8). Neither gap blocks this slice. The feature reviewer should know
about both.

## Verdict

green. The gate passes with exactly +10 (60 → 70), matching the Lead-adjusted expectation. The diff
touches only `app/api/habits.py` (additive, byte-identical to the design's route) and
`tests/test_habits_api.py`. `TIME-1`, `OUT-1`, `DAY-1`/D3, D5, `DB-1` and `CORS-1` hold. All ten
tests assert what the design says. Nine independent probes and six mutations found no defect.
The cross-repository contract is frozen as designed. The slice touched no unsettled decision.
Advisory: the builder's tests do not detect a second `date.today()` call in the route (M5);
probe P8 does.
