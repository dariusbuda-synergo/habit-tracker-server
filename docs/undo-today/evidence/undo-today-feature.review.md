# Verification — undo-today / feature

> Builder model: sonnet (slices 1, 2) · Verifier models: opus (slices 1, 2) · Reviewer model: fable
> Every number below is the observed output of a command named next to it. Never assumed,
> never copied from the builder.

Feature review of the whole server branch `feature/undo-today`: `git diff ceea25a..HEAD`, reviewed at
head `59fcd29` and re-checked at head `621e2a5` after the test fix-up, base main `ceea25a`. Commits on
the branch (`git log --oneline ceea25a..HEAD`): `474ddc4` contract and design, `f709e49` slice 1
(service), `f81ea81` verify 1, `cc10249` slice 2 (route), `59fcd29` verify 2, `ae3ab60` this review,
`621e2a5` slice 2 fix-up (`pin the habit filter in the two-habit test`). All commands were run from
the worktree `.claude/worktrees/undo-today` with its `.venv` (Python 3.13.14,
`.venv/bin/python --version`). `git status` before starting and before the re-check: clean.

**Re-check (`621e2a5`).** `git diff --name-only ae3ab60..621e2a5` → `tests/test_habits_api.py` only;
`git diff --stat` → `1 file changed, 3 insertions(+), 3 deletions(-)`: the tenth test now undoes
`second` and asserts `first` stays completed. No product code moved: the service file's `shasum` is
still `72d2e01ac3f2`. Sections marked "re-check" below carry the numbers observed on `621e2a5`.

Branch scope (`git diff --name-only ceea25a..HEAD`): 12 paths. Product code: `app/api/habits.py`
(+10 lines, 0 removed) and `app/services/habit_service.py` (+9, 0 removed). Tests:
`tests/test_habit_service.py` (+30) and `tests/test_habits_api.py` (+109, −1: the `datetime` import
line). The other 8 paths are `docs/undo-today/**` (`git diff --stat ceea25a..HEAD`).

## Mechanical gate

| Command | Result | Counts |
|---|---|---|
| `.venv/bin/python -m pytest -q` at `621e2a5` (branch head, re-check) | pass, exit 0 | `70 passed, 1 warning in 0.25s` |
| `.venv/bin/python -m pytest -q -k uncomplete` at `621e2a5` (re-check) | pass | `12 passed, 58 deselected` |
| `.venv/bin/python -m pytest -q` at `59fcd29` (head at first review) | pass, exit 0 | `70 passed, 1 warning in 0.26s` |
| `.venv/bin/python -m pytest --collect-only -q` at `59fcd29` | n/a | `70 tests collected` |
| same gate command on a `git archive ceea25a` export (scratch dir, same venv, `-p no:cacheprovider`) | pass, exit 0 | `58 passed, 1 warning in 0.20s` (baseline, matches `AGENTS.md § Mechanical gate`) |
| `.venv/bin/python -m pytest -q tests/test_habit_service.py` at `59fcd29` | pass | `20 passed, 1 warning` |
| `.venv/bin/python -m pytest -q -k uncomplete` at `59fcd29` | pass | `12 passed, 58 deselected` (2 service + 10 endpoint tests) |
| `grep -c "^def test_" tests/test_habits_api.py tests/test_habit_service.py` | n/a | `50` / `20` |
| linter / formatter | n/a | none configured (`AGENTS.md § Mechanical gate`) |

Delta 70 − 58 = **+12** for the whole branch: +2 (slice 1) and +10 (slice 2, the design's nine plus
the Lead's tenth); the fix-up changes the count by 0. The one warning is the starlette
`anyio.abc.BlockingPortal` deprecation, present on the baseline export too. The gate was run once
more after every mutation below was restored: `70 passed, 1 warning in 0.26s` at `59fcd29` and
`70 passed, 1 warning in 0.24s` at `621e2a5` (re-check), exit 0 both times; `git status --short`
printed 0 lines and `git diff --quiet HEAD` exited 0 after each.

Frozen files (`AGENTS.md § Branching`): `git diff --quiet ceea25a..HEAD -- app/models/habit.py
app/schemas.py requirements.txt requirements-dev.txt` → exit 0. Blob ids at base and head
(`git rev-parse ceea25a:<f>` / `HEAD:<f>`) are identical: `1742bed…`, `d9770d2…`, `9f9c33c…`,
`a575cbd…`. `app/main.py`, `app/config.py`, `app/database.py`: `git diff --stat ceea25a..HEAD`
prints nothing for them.

## Invariants

| Code | Checked how, across the whole branch | Result |
|---|---|---|
| `DAY-1` | `app/services/habit_service.py:150-156` (read): the function queries only `Completion`; `Skip` appears only in the docstring. Endpoint chain probe F6: freeze → complete (freeze deleted by `complete_habit`, as before) → freeze again 409 → undo → `completed_today` false, `skipped_today` false → unskip 200 → freeze 200 → undo on the frozen day is a no-op, `Skip` count 1, `Completion` count 0. Service-level F16 with an explicit date: after undo, `skip_habit` no longer raises. F3: a bridging `Skip` survives undo (count 1). | pass |
| `STREAK-1` | `git diff --stat ceea25a..HEAD`: `habit_service.py` is `9 +`, 0 removed; the only added hunk is `uncomplete_habit` at `:150-156`, so `compute_streak` and `compute_longest_streak` are untouched. Probes F2 (undo splits the longest run 4 → 2, `streak` re-anchors on yesterday 2), F3 (skip-bridged run 3 → 2 in both functions), F4 (earlier 5-day run keeps `longest_streak` 5 while `streak` 2 → 1). | pass |
| `TIME-1` | `grep -n "date.today" app/services/habit_service.py` → no match (exit 1). `grep -n "date.today" app/api/habits.py` → 8 matches; the new route has one at `:65`, and `:66-67` pass that `today` to both `uncomplete_habit` and `to_summary`. Probe F13 replaces `app.api.habits.date` with a subclass whose second `today()` returns tomorrow and spies on both service calls: `calls == 1`, both received the same date. Mutation M-B (second `date.today()`) is caught by F13 only. | pass |
| `WEEK-1` | `start_of_week`, `count_completions_in_week`, `is_at_risk` untouched (same `git diff --stat` fact). Probe F14 with explicit dates: Sunday 2026-01-04 completed, Monday 2026-01-05 completed then undone → `completed_this_week` 1 → 0, the Sunday row kept, `streak` 2 → 1, `at_risk` false → true (7 needed, 7 days left); a Sunday undo with target 7 also flips `at_risk` to true. | pass |
| `OUT-1` | `app/api/habits.py:60` `response_model=HabitOut`, `:67` `return habit_service.to_summary(habit, today)`. Probe F10: the DELETE body has exactly the 16 `HabitOut` keys, the same key set and JSON types as the `POST /complete` body, `content-type: application/json`. F11: `app.openapi()` delete 200 schema `$ref` ends in `/HabitOut`. `app/schemas.py` unchanged (above). No new field anywhere in the branch. | pass |
| `DB-1` | No new table or column: the frozen model file is unchanged (above); the branch only deletes rows from `completions`. `git log --oneline -S uq_habit_day -- app/models/habit.py` → `15e6a2f Initial commit`, so every database file this app ever created has the unique constraint that makes `.first()` sufficient. | pass |
| `CORS-1` | Probe F12 through the real middleware: preflight `OPTIONS` with `Origin: http://localhost:3000` and `Access-Control-Request-Method: DELETE` → 200, `access-control-allow-origin` echoes the origin, `DELETE` in `access-control-allow-methods`; the same preflight from `http://evil.example` → 400 and no `access-control-allow-origin`; a plain `DELETE` with the foreign origin carries no `access-control-allow-origin`. `app/main.py` unchanged. | pass |

## Design and contract conformance

- **Code is the design's text.** `awk` extracts of `uncomplete_habit` in the service (7 lines) and
  lines `60-67` of the router (8 lines) compared with the design's § Interfaces → Server blocks using
  `diff` → exit 0 for both: byte-identical, docstring included. Placement as specified: service after
  `unskip_habit` (`:142`), before `update_habit` (`:159`); route after `complete_habit` (`:50-57`),
  before `skip_habit` (`:70`). No new import in either file (`git diff ceea25a..HEAD` shows none).
- **Service and route agree on semantics across the slice boundary.** The route resolves `today`
  once and passes the same value to the delete and to the summary (F13); the service deletes at
  most the `(habit_id, today)` row and commits; `to_summary` sees the deletion through
  `expire_on_commit` (default, `app/database.py:8`), which F15 checks on the same object with no
  refresh: `habit.completions == []` right after `uncomplete_habit`, and after the no-op branch
  (no commit) the summary is still consistent. Mutation M-F (commit removed) fails 8 of the branch's
  12 tests and 12 of 16 probes, so the commit is pinned.
- **Settled decisions that touch the server:**
  - D1 route and verb: `app/api/habits.py:60` `@router.delete("/{habit_id}/complete", ...)`. Holds.
  - D2 response: 200 `HabitOut`; idempotent (builder test 2; F7 three undos in a row all 200,
    0 rows); unknown habit 404 `{"detail": "Habit not found"}` (builder test 3; F9 after a
    whole-habit delete). Holds.
  - D3 day becomes "neither", freeze not restored: builder test 8, F6, F16. Holds.
  - D4 undo on the card only: the branch adds exactly one route (the `git diff` has one new
    `@router` decorator); nothing server-side for complete-all or history. Nothing to check beyond that.
  - D5 no server-side `archived` check: lines `60-67` contain no `archived`; builder test 9; F5
    (archived habit undo → 200, `archived` true, `completed_today` false, and `/habits/stats` never
    counted it before or after, as `list_habits` excludes archived). Holds.
  - D6, D7, A7: client-only; the server adds no confirmation, sound or banner text. Nothing added.
  - A1 naming: `uncomplete_habit` at `habit_service.py:150` and `api/habits.py:61`. Holds.
  - A6 service tests: two explicit-date tests at the end of `tests/test_habit_service.py` using
    `db_session`; no new test file (`git diff --name-only` lists none); the gate's trigger functions
    are untouched (above). Holds.
- **Contract pattern.** The service is the `unskip_habit` twin (`filter_by(habit_id, day).first()`,
  delete, commit, return), not the `complete_habit` twin; the route is the `DELETE /skip` twin with
  no `try/except`. Mutation M-C (route calling `unskip_habit` instead) fails 7 builder tests and 9
  probes.
- **Deviations:** one, sanctioned by the Lead: +10 endpoint tests instead of the design's +9. No
  unsettled decision was touched (design § Decisions left to implementation: "None").

## Adversarial probes

Probes F1–F16 were one throwaway pytest file in the session scratch directory, outside the
repository, run as
`PYTHONPATH=. .venv/bin/python -m pytest -q -p no:cacheprovider -p tests.conftest --rootdir=. <scratch>/probe_feature.py`
so the repository's own `client` and `db_session` fixtures applied. Nothing was committed. Final
result on `59fcd29`: `16 passed in 0.15s`. Two probe-side corrections on the way, neither a change
to the code: a 20-digit habit id raised `OverflowError` (pre-existing, see below), so the probe uses
`2**62` → 404; and the `Allow` header on a 405 lists only `POST` (pre-existing Starlette behaviour,
identical on `/skip`), so the probe records it instead of requiring `DELETE`.

| # | Probe | Result |
|---|---|---|
| F1 | Nine seeded days (1, 2, 3, 5, 8, 13, 21, 40, 100 days ago) plus today; undo. Body `completed_days` is exactly the nine, DB rows are exactly the nine, body equals the `GET /habits` entry. | pass |
| F2 | Completions 2 and 1 days ago, today, and tomorrow (seeded): `longest_streak` 4; undo today → `longest_streak` 2, `streak` 2. Undo of a day in the middle of the longest run splits it correctly. | pass |
| F3 | Completions 3 and 2 days ago, `Skip` yesterday, complete today: `(streak, longest)` `(3, 3)`; undo → `(2, 2)`, the skip row still there. | pass |
| F4 | Earlier 5-day run plus yesterday and today: `(2, 5)`; undo → `(1, 5)`. | pass |
| F5 | Three habits completed; stats `(completed_today, total_completions, active_streaks, best_streak)` = `(3, 3, 3, 1)`; undo two → `(1, 1, 1, 1)`, `weekly_completion_rate` `round(1/21*100)`. Archive the third, undo it → 200, `archived` true; stats `completed_today` 0 before and after; `include_archived=true` list shows it undone. | pass |
| F6 | The freeze/complete/undo chain described under `DAY-1`. | pass |
| F7 | Five complete/undo cycles → 0 rows; complete → `streak` 1, 1 row; three undos → all 200, 0 rows. | pass |
| F8 | Habit A completed first (lower rowid), then B; undo **B**. A keeps today, B loses it. This is the ordering the Lead's tenth test does not exercise. | pass |
| F9 | `DELETE /habits/complete` → 422; ids `0`, `-1`, `2**62` → 404; `GET` on the path → 405; `DELETE …/complete/` → 307 to the slash-less path; none of these deleted the row (count 1). `DELETE /habits/{id}` → 204, then undo → `{"detail": "Habit not found"}`, 0 rows (cascade). No shadowing in either direction. | pass |
| F10 | Body shape for the client (`request<Habit>` then replace in state): same 16 keys and JSON types as the `POST /complete` body; `id` matches; a stray request body is ignored (200). | pass |
| F11 | `app.openapi()`: all `operationId`s unique; the delete has no `requestBody`, its 200 refs `HabitOut`; `DELETE /habits/{habit_id}` still lists 204. | pass |
| F12 | `CORS-1` preflight and plain-request checks (table above). | pass |
| F13 | `TIME-1` single-resolution detector (table above). | pass |
| F14 | `WEEK-1` Monday boundary and `at_risk` with explicit dates (table above). | pass |
| F15 | `to_summary` on the same object after the no-op branch and after the delete+commit, no refresh. | pass |
| F16 | Service-level `DAY-1` sequence with an explicit date. | pass |

**Concurrency** (`<scratch>/probe_concurrency.py`, two independent sessions on a scratch SQLite
file, as two uvicorn requests would be; the app was not run as a server):

| # | Interleaving | Observed |
|---|---|---|
| C1 | Both sessions load today's row; A runs `uncomplete_habit`; B deletes its stale copy and commits. | B's commit succeeds with the SQLAlchemy warning `DELETE statement on table 'completions' expected to delete 1 row(s); 0 were matched`; rows left 0; `completed_today` false. No exception, no 500. |
| C2 | A and B each run the full `uncomplete_habit`. | rows 0 (B's fresh query finds nothing, no-op). |
| C3 | B checks `already_done`, A undoes, B runs `complete_habit`. | rows 1 (B re-queries inside the call and inserts). The `SAWarning: Identity map already had an identity` printed here comes from my probe holding B's stale deleted row while SQLite reused rowid 1; a per-request session never holds such a row. |
| C4 | B completes, A undoes with a stale habit object. | rows 0: last writer wins, the same semantics `skip`/`unskip` already have. |

**Pre-existing findings, not introduced by the branch** (recorded for the Lead, outside this
feature's scope):

- A habit id that does not fit a SQLite integer (`99999999999999999999`) raises `OverflowError`
  inside `db.get` and would be a 500. `<scratch>/probe_overflow.py` on the head: 4 of 4 per-habit
  routes fail this way (`POST …/complete`, `DELETE …/skip`, `DELETE /habits/{id}`, `DELETE …/complete`);
  on the `ceea25a` export: 3 of 3 existing routes fail the same way. Same `get_habit` call everywhere.
- `GET /habits/{id}/complete` → `405 Allow: POST` and `GET /habits/{id}/skip` → `405 Allow: POST`
  (`<scratch>/probe_allow.py`): Starlette reports only the first matching route object's methods.

**Mutations** (`<scratch>/mutate.py`): each applied to the named file, then the full gate, the
branch's 12 tests (`-k uncomplete`) and my 16 probes were run, then `git checkout -- <file>`.
`shasum` before: service `72d2e01ac3f2`, router `57f600758516`; after every restore the same values.
`git status --short` after all seven: 0 lines.

| Mutation | Full gate | `-k uncomplete` (12) | My probes (16) |
|---|---|---|---|
| M-A service: habit half dropped, `filter_by(day=today)` — at `59fcd29` | **`70 passed`** | `12 passed` | `3 failed, 13 passed` (F5, F8, F14) |
| M-A again at `621e2a5` (re-check, after the test fix-up) | `1 failed, 69 passed` (`test_uncomplete_only_affects_the_given_habit`) | `1 failed, 11 passed` (same test); `-k only_affects` → `1 failed, 69 deselected` | not re-run (product code unchanged since `59fcd29`); the clean run after restore: `16 passed` |
| M-B route: `to_summary(habit, date.today())` (second resolution) | **`70 passed`** | `12 passed` | `1 failed, 15 passed` (F13) |
| M-C route: calls `unskip_habit` (wrong twin) | `7 failed, 63 passed` | `7 failed, 5 passed` | `9 failed, 7 passed` |
| M-D service: day half dropped, `filter_by(habit_id=habit.id)` | `1 failed, 69 passed` | `1 failed, 11 passed` (service test 1) | `4 failed, 12 passed` |
| M-E route: `response_model=HabitOut` removed | **`70 passed`** | `12 passed` | `1 failed, 15 passed` (F11) |
| M-F service: `db.commit()` removed | `8 failed, 62 passed` | `8 failed, 4 passed` | `12 failed, 4 passed` |
| M-G route: service call dropped | `7 failed, 63 passed` | `7 failed, 5 passed` | `9 failed, 7 passed` |

**Finding on the slice 1 advisory (test gap, not a defect).** The Lead's tenth test
`test_uncomplete_only_affects_the_given_habit` (`tests/test_habits_api.py:406-417`) completes
`first` then `second` and undoes `first`. Under M-A, `.first()` of all of today's rows returns the
lowest rowid, which is `first`'s own row, so the test passes (`70 passed` above): **it does not pin
the habit half of the filter.** With the service mutated and the test edited in scratch to undo
`second` instead (and the two `completed_today` assertions swapped), `pytest -q -k only_affects` →
`1 failed, 69 deselected`; both files were then restored (`shasum` of the test file `c405237b0f03`
before and after). That one-token change closes the gap. **Re-check:** the slice 2 builder applied
exactly that change as `621e2a5`. With M-A re-applied on that head, the full gate reports
`1 failed, 69 passed` and the failing test is `test_uncomplete_only_affects_the_given_habit`; after
`git checkout -- app/services/habit_service.py` the file's `shasum` is `72d2e01ac3f2` again, the
pre-mutation value. The habit half of the filter is now pinned by the branch's own tests, and the
slice 1 advisory is closed. For scale: at the baseline no
`complete`/`skip`/`unskip` test creates two habits (`git show ceea25a:tests/test_habits_api.py`
scanned with `awk`; the only two-habit test that calls `/complete` is
`test_stats_weekly_completion_rate_is_a_percentage_of_targets`, which asserts a rate, not scoping),
so the branch adds the first scoping test for a per-habit mutation even if it is weaker than intended.

**On the slice 2 advisory.** M-B confirms the branch's tests cannot tell one `date.today()` from
two; F13 can. M-E shows the same for `response_model` (`OUT-1`): dropping it still serialises the
same JSON, so only an OpenAPI assertion sees it. Both are true of every sibling route on `main`.

**Should the advisories block the Ship gate?** No. After the re-check only the slice 2 advisory
(single `date.today()`) remains open, and it stays advisory; the reasoning below was written for
both and still applies to it:

1. Neither is a product defect. The service and the route are byte-identical to the approved
   design, and habit scoping, single `today` resolution and the response model were each proven on
   the real code by three independent probe sets (slice 1 probes 1, 6, 7; slice 2 P4, P8, P7; here
   F5, F8, F13, F14, F11).
2. What is missing is a regression pin for a seven-line function and an eight-line route whose
   text the design fixes, in a repository where no sibling route has such pins either. The branch
   leaves the test suite stronger than the baseline it joins, not weaker.
3. The fix for advisory 1 is a one-token edit in a test file, shown above; advisory 2 would need a
   monkeypatch-style test the repository has no precedent for. Either can be a follow-up commit on
   this branch or a later chore; neither changes the frozen cross-repository contract the client
   slices are built on.

At `59fcd29` the tenth test was not evidence for habit scoping; since `621e2a5` it is.

## Verdict

green. The whole branch (`ceea25a..621e2a5`, re-checked after the test fix-up) passes the
mechanical gate at `70 passed`, +12 over the `58` baseline I measured on an export of the base. The
four frozen files are unchanged; the fix-up touched only `tests/test_habits_api.py`. All seven
invariants (`DAY-1`, `STREAK-1`, `TIME-1`, `WEEK-1`, `OUT-1`, `DB-1`, `CORS-1`) hold on the branch
head, checked by command and by probe, including `CORS-1` through the real middleware. Every settled
decision that touches the server (D1, D2, D3, D5, A1, A6; D4, D6, D7, A7 add nothing server-side)
holds, and the product code is byte-identical to the design. Sixteen cross-slice probes, four
two-session concurrency interleavings and seven mutations found no defect. The habit-scoping mutation
(M-A) that survived the tests at `59fcd29` now fails the branch's own tenth test at `621e2a5`, so the
slice 1 advisory is closed; the remaining survivors (M-B, M-E) are test gaps the probes cover and
stay advisory for the reasons above. Two pre-existing, out-of-scope behaviours are recorded for the
Lead (integer overflow on absurd ids, `Allow` header on 405). Nothing in the response would trip the
client's `request<Habit>` replace-in-state pattern: the body is a full `HabitOut` with the same keys
and types as the complete endpoint's.
