# Verification — undo-today / server-1

> Builder model: sonnet · Verifier model: opus
> Every number below is the observed output of a command named next to it. Never assumed,
> never copied from the builder.

Slice under test: `f709e49` (`undo-today slice 1: service uncomplete_habit with explicit-date tests`)
on `feature/undo-today`, parent `474ddc4` (contract and design), base main `ceea25a`. All commands
were run from the worktree `.claude/worktrees/undo-today` with its `.venv`.

## Mechanical gate

| Command | Result | Counts |
|---|---|---|
| `.venv/bin/python -m pytest -q` at `f709e49` | pass (exit 0) | `60 passed, 1 warning` |
| same command on a `git archive 474ddc4` export (scratch dir, same venv) | pass | `58 passed, 1 warning` (baseline) |
| `.venv/bin/python -m pytest -q tests/test_habit_service.py` at `f709e49` | pass | `20 passed, 1 warning` |
| `.venv/bin/python -m pytest -q -k uncomplete -v` | pass | 2 tests `PASSED`: the two new service tests |
| linter / formatter | n/a | none configured (`AGENTS.md § Mechanical gate`) |

Delta 60 − 58 = **+2**, exactly what the design expects for slice 1. The one warning is the
starlette `anyio.abc.BlockingPortal` deprecation, present on the baseline as well. The gate was
run again after all mutation probes were restored: `60 passed`, exit 0, `git status --short` empty.

## Invariants

| Code | Checked how | Result |
|---|---|---|
| `DAY-1` | `awk '/^def uncomplete_habit/,/^    return habit/' app/services/habit_service.py \| grep -v '"""' \| grep -c Skip` → `0`: the only `Skip` in the function is the docstring text; the code queries only `Completion`. Builder test 2 and probes 3, 5 (below) show `Skip` rows survive. | pass |
| `STREAK-1` | Body of `compute_streak` and `compute_longest_streak` hashed at `474ddc4` and `f709e49` (awk extract + `shasum`): `61a52f757e8a` = `61a52f757e8a`, `4a94104ce493` = `4a94104ce493`. `git diff -U0 474ddc4..f709e49 -- app/services/habit_service.py` has one hunk (`@@ -149,0 +150,9 @@`) and `0` removed lines. Probe 4 shows streak re-anchors on yesterday (2 → 1). | pass |
| `WEEK-1` | Same hash check: `is_at_risk` `23634335120d` = `23634335120d`, `count_completions_in_week` `91c015c064c5` = `91c015c064c5`, `start_of_week` `5012650886b6` = `5012650886b6`. Probe 4: `completed_this_week` 1 after undo of one of two days. | pass |
| `TIME-1` | `grep -n "date.today" app/services/habit_service.py` printed nothing (exit 1). Signature is `uncomplete_habit(db: Session, habit: Habit, today: date) -> Habit`. | pass |
| `DB-1` | `git diff --quiet 474ddc4..f709e49 -- app/models/habit.py app/schemas.py requirements.txt requirements-dev.txt` → exit 0 (no change). | pass |
| `OUT-1` | Same command: `app/schemas.py` unchanged; `to_summary` not in the diff (single hunk, 0 removed lines). | pass |
| `CORS-1` | Not touchable by a service-only slice; `app/main.py` not in `git diff --name-only`. | n/a |

Scope: `git diff --name-only 474ddc4..f709e49` prints exactly `app/services/habit_service.py` and
`tests/test_habit_service.py`. No frozen file (`AGENTS.md § Branching`) touched.

## Design and contract conformance

- **Placement.** `grep -n "^def " app/services/habit_service.py`: `unskip_habit` at 142,
  `uncomplete_habit` at 150, `update_habit` at 159. Directly after `unskip_habit`, before
  `update_habit`, as the design's Interfaces section requires. No new import.
- **Signature and body.** The 7-line function extracted from the code and the first 7 lines of the
  design's `uncomplete_habit` block (`docs/undo-today/design/2026-10-15-undo-today-design.md`,
  § Interfaces → Server) compared with `diff` → exit 0: byte-identical, docstring included.
- **Tests.** Both named tests exist with the design's names, at the end of
  `tests/test_habit_service.py`, using `db_session` and explicit dates `date(2026, 1, 5)` /
  `date(2026, 1, 6)`:
  - `test_uncomplete_habit_deletes_only_the_given_days_completion`: two `Completion` rows, undo the
    6th, asserts `result is habit` and remaining days `== [date(2026, 1, 5)]`. Matches.
  - `test_uncomplete_habit_leaves_skips_and_is_a_no_op_without_a_completion`: one `Skip` on the 6th,
    two undo calls, asserts zero `Completion` rows and the `Skip` present. Matches.
- **Imports.** `from app.models.habit import Completion, Skip` added; the service import tuple gains
  `create_habit` and `uncomplete_habit`, alphabetical. Matches slice 1's file list.
- **Settled decisions.** D3 (day becomes "neither", freeze not restored) holds at service level
  (probe 3). A1 naming `uncomplete_habit` holds. A6 (service tests in the existing file, no new test
  file, trigger functions untouched) holds.
- **Contract pattern.** Follows the `unskip_habit` twin (`filter_by(habit_id, day).first()`,
  delete, commit, return habit), not the `complete_habit` twin, as the contract and the design's
  "wrong twin" risk require.
- **Deviations:** none. The slice touched no decision outside the design's settled list
  (§ Decisions left to implementation: "None").

## Adversarial probes

Probes 1–7 were a throwaway pytest file in the session scratch directory, outside the repository,
run with `PYTHONPATH=. .venv/bin/python -m pytest -q -p no:cacheprovider -p tests.conftest <scratch>/probe_uncomplete.py`
so the repository's own `db_session` fixture applied. Unmutated result: `7 passed`. None of these
tests was committed.

| # | Probe | Result |
|---|---|---|
| 1 | Habits A and B both completed on the 6th; undo A on the 6th. Only `(B, 6th)` remains. | pass |
| 2 | A completed on the 5th; undo A on the 6th (no row) leaves `(A, 5th)`; add the 6th, undo the 5th, only `(A, 6th)` remains. | pass |
| 3 | Freeze A on the 6th, `complete_habit`, `uncomplete_habit`: 0 completions, 0 skips, `to_summary` has `completed_today` and `skipped_today` both false (D3). | pass |
| 4 | A completed on the 5th, `complete_habit` on the 6th → `streak` 2; undo the 6th, then `to_summary` on the **same object without refresh** → `completed_today` false, `streak` 1, `longest_streak` 1, `completed_this_week` 1; `get_stats` → `completed_today` 0, `total_completions` 1. This shows that `expire_on_commit` refreshes the object, which the slice 2 route relies on. | pass |
| 5 | A completed on the 6th with a `Skip` on the 5th; B has a `Skip` on the 6th. Undo A on the 6th: both skips remain, both habits remain. | pass |
| 6 | B's completion on the 6th inserted **before** A's (lower row id); undo A on the 6th. Only `(B, 6th)` remains. | pass |
| 7 | A has no completion; B has one on the 6th; undo A on the 6th. B's row remains. | pass |

Mutation probes. Each was applied in place to `app/services/habit_service.py`, then
`git checkout -- app/services/habit_service.py`. After each restore, `shasum` returned
`72d2e01ac3f2`, the pre-mutation value. After all of them, `git status --short` printed 0 lines and
`git diff --quiet f709e49` succeeded.

| Mutation | Builder's 2 tests (`pytest -q -k uncomplete tests/test_habit_service.py`) | My probes |
|---|---|---|
| M1 `filter_by(habit_id=habit.id)` (day dropped) | `1 failed, 1 passed`: test 1 fails, as the design's probe requires | `2 failed, 3 passed` (5-probe set at the time) |
| M2 `filter_by(day=today)` (habit dropped) | `2 passed`: **survives the builder's tests** | `2 failed, 5 passed`: probes 6 and 7 fail |
| M3 extra `Skip` delete inside the `if existing_completion` branch | `2 passed` | `7 passed`. Undetectable while `DAY-1` holds: a habit-day with a completion cannot also have a skip. Not a real defect. |
| M4 unconditional same-day `Skip` delete before the `if` | `1 failed, 1 passed`: test 2 fails | not run |

Finding (test gap, not a defect): the builder's tests are single-habit, so they do not pin the
`habit_id` half of the filter. M2, which would delete another habit's completion for the same day,
passes them. The code under test is correct: the body is byte-identical to the design, and probes
1, 6 and 7 pass against it. The design's slice 2 API tests are also single-habit. The feature
reviewer should know this; a two-habit assertion would close the gap if the human wants it pinned.

## Verdict

green. The gate passes with exactly +2 (58 → 60). The diff touches only the two named files.
`DAY-1`, `STREAK-1`, `WEEK-1`, `TIME-1`, `DB-1` and `OUT-1` hold. The function is byte-identical to
the design's Interfaces text, and both named tests match. The independent probes found no defect.
The slice touched no unsettled decision. Advisory: the builder's tests do not pin habit scoping
(mutation M2 survives them).
