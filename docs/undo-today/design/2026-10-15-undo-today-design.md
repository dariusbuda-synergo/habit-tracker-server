# Design — undo-today

> Consumes the approved contract at
> `habit-tracker-server/docs/undo-today/design/2026-10-15-undo-today-contract.md` (primary) and its
> client companion `habit-tracker-client/docs/undo-today/design/2026-10-15-undo-today-contract.md`.
> Does not re-derive their facts; `path:line` citations below are the contract's (server at
> `ceea25a`, client at `d9f7527`).

Primary design. It spans two repositories: server first, then client. The client repository carries a
companion with the client interfaces and the client slices in full:
`habit-tracker-client/docs/undo-today/design/2026-10-15-undo-today-design.md`
([relative link](../../../../habit-tracker-client/docs/undo-today/design/2026-10-15-undo-today-design.md)).
For anything on the client side, the companion is the builder's brief; this file carries the shared
shape and a summary of the client slices that must stay identical to it.

Roster: `balanced` (sonnet builds, opus verifies each slice, fable reviews each branch once).

## Settled decisions

The human answered the contract's seven open questions at the Contract gate. They are decisions, not
options:

| # | Decision | Where it lands |
|---|---|---|
| D1 | Route and verb: `DELETE /habits/{habit_id}/complete`, mirroring `DELETE /habits/{habit_id}/skip` (`app/api/habits.py:73`). | server slice 2, client slice 1 |
| D2 | Response `200` with the updated `HabitOut` via `to_summary(habit, today)`. Idempotent: a habit not completed today returns 200 unchanged. Unknown habit: `404 {"detail": "Habit not found"}`. | server slice 2; client slices 1 and 3 keep replace-in-state |
| D3 | After undo the day is "neither". A freeze that completing deleted (`app/services/habit_service.py:122-124`) is not restored. | server slices 1 and 2 (tests pin it) |
| D4 | Undo appears on the habit card only. Not in complete-all (`app/page.tsx:255-270`), not in history. | client slices 2 and 3 |
| D5 | Archived habits: Undo is disabled on the card for an archived habit, same as "Mark done" (`app/components/HabitCard.tsx:238`). The server does not check `archived`, matching the complete endpoint (`app/api/habits.py:50-57`). | server slice 2 (test pins it), client slice 2 |
| D6 | No confirmation dialog. The page handler wraps the call in `try/catch`; on failure it sets the error banner and reloads the list, like `handlePinToggle` (`app/page.tsx:172-180`). | client slice 3 |
| D7 | No sound or animation counterpart. The progress-bar width transition (`app/components/HabitCard.tsx:218`) reverses on its own; nothing is added. | none |

Architect decisions (settled here so no builder has to choose):

| # | Decision | Reason |
|---|---|---|
| A1 | Naming follows the unskip twin: service `uncomplete_habit`, route function `uncomplete_habit`, client `uncompleteHabit`, card and list prop `onUncomplete`, page handler `handleUncomplete`. | `unskip_habit` / `unskipHabit` / `onUnskip` / `handleUnskip` are the existing inverse-of-X names (`app/services/habit_service.py:142`, `app/lib/api.ts:79`, `app/components/HabitCard.tsx:24`, `app/page.tsx:113`). |
| A2 | `onUncomplete` is **optional** on both `HabitCardProps` and `HabitListProps`. Without it, the card shows the Undo control **disabled**. | A required prop turns the 19 `<HabitCard` renders in `HabitCard.test.tsx`, the 3 `<HabitList` renders in `HabitList.test.tsx` and `app/archive/page.tsx:151-163` into `tsc --noEmit` errors (contract, `TEST-1` note). Precedent for optional callbacks: `app/components/HabitCard.tsx:35-36`. |
| A3 | `app/archive/page.tsx` is **not changed**. | Every card there is archived, so by D5 its Undo would always be disabled; passing a handler would be dead code. Without the prop the archived card shows a disabled Undo, which is D5's behaviour. |
| A4 | The primary card button stays **one `<button>`** that toggles on `completed_today`, like the freeze toggle (`app/components/HabitCard.tsx:243-252`). Not completed: unchanged ("Mark done", no `aria-label`, `onComplete`). Completed: visible text `Undo`, `aria-label` ``Undo today's completion of ${habit.name}``, `onClick` calls `onUncomplete`, `disabled={habit.archived \|\| !onUncomplete}`, emerald "active" palette. The disabled "Done today" label disappears. | One element keeps focus in place when the state flips. The accessible name starts with the visible text (label-in-name). It matches none of the existing queries `/mark done/i`, `/done today/i`, `/freeze/i`, `/unfreeze/i`, and no other card control's name contains "undo" (card `aria-label`s at `HabitCard.tsx:86-276` read as Edit, Pin/Unpin, Cycle priority, Freeze/Unfreeze, Duplicate, Archive/Unarchive, Delete). |
| A5 | The test `disables the button once already completed today` (`HabitCard.test.tsx:153-167`) is rewritten in place as `offers an enabled Undo instead of a disabled button once completed today`. | `TEST-1` says rewrite, not delete; the feature reverses its expectation. |
| A6 | One service-level test file change: two explicit-date tests for `uncomplete_habit` go into `tests/test_habit_service.py`, using the existing `db_session` fixture (`tests/conftest.py:13-25`). | It is the only way to test `TIME-1` with explicit dates and to prove that only `today`'s row is deleted; the API tests run on the real `date.today()`. No new test file, so the `AGENTS.md` subsystem table stays accurate. The gate's trigger functions are not touched. |
| A7 | The failure banner text is `Could not undo that completion — refreshing the list.` | Same shape as `handlePinToggle`'s message (`app/page.tsx:177`). |

## Shape of the change

```
 browser                                     habit-tracker-server
 ───────                                     ────────────────────
 HabitCard  [Undo]  (completed_today)
   │ onUncomplete(id)        (optional prop)
 HabitList  ──forwards──►
   │
 app/page.tsx  handleUncomplete(id)  try { … } catch { setError; loadHabits }
   │
 app/lib/api.ts  uncompleteHabit(id) ─► request<Habit>  DELETE /habits/{id}/complete
                                                    │
                                     app/api/habits.py  uncomplete_habit(habit_id, db)
                                        get_habit → 404 │ today = date.today()   (TIME-1)
                                                    ▼
                                     habit_service.uncomplete_habit(db, habit, today)
                                        delete Completion(habit_id, day=today) if present; commit
                                                    ▼
                                     habit_service.to_summary(habit, today) → HabitOut 200  (OUT-1)
 setHabits(prev.map(h => h.id === id ? updated : h))  ◄──────────────┘
```

What changes and what does not:

- **Server.** One service function deletes at most one `completions` row, matched by
  `(habit_id, day=today)` under `uq_habit_day` (`app/models/habit.py:31`). It never reads or writes
  `skips` (`DAY-1`, D3). One route resolves the habit, 404s, resolves `today` once and returns
  `to_summary` (`app/api/habits.py:73-80` pattern). Streak, longest streak, weekly count, at-risk and
  `/habits/stats` follow from the stored rows; nothing is cached (`STREAK-1`, `WEEK-1`). No schema
  change (`DB-1`), no new `HabitOut` field (`OUT-1`), CORS already allows `DELETE` (`CORS-1`).
- **Client.** One api function through `request()` (`API-1`). The card's completed state becomes an
  Undo action; the freeze control re-enables on its own once `completed_today` is false
  (`app/components/HabitCard.tsx:245`). The home page gains one guarded handler; header counts and the
  complete-all count are derived from state and follow the returned summary (`app/page.tsx:251,253`).
  "Done today" keeps coming from the API's `completed_today` (`SSR-1`); no type changes (`TYPES-1`).
- **Not changed:** `app/models/habit.py`, `app/schemas.py`, `requirements*.txt` (server frozen);
  `app/types/HabitTypes.ts`, `package*.json`, `app/globals.css` (client frozen), `app/archive/page.tsx`
  (A3), `app/history/page.tsx`, `app/stats/page.tsx`, `app/lib/export.ts`, `test/mock-data.ts`.

## Interfaces

### The frozen cross-repository contract

This is the only thing the client depends on. It is frozen once server slice 2 is verified green.

```
DELETE /habits/{habit_id}/complete
  no request body
  200  HabitOut   (to_summary(habit, today); completed_today == false afterwards)
       – also when the habit was not completed today (idempotent, body unchanged)
       – also when the habit is archived (no archived check)
  404  {"detail": "Habit not found"}   when habit_id does not exist
  422  FastAPI's validation error when habit_id is not an int (framework default, as every route)
```

`HabitOut` is unchanged (`app/schemas.py:40-58`). The client `Habit` type is unchanged
(`app/types/HabitTypes.ts:1-18`).

### Server — `habit-tracker-server`

`app/services/habit_service.py`, placed directly after `unskip_habit` (`:142-147`), before
`update_habit` (`:150`). No new import (`Completion` is imported at `:5`).

```python
def uncomplete_habit(db: Session, habit: Habit, today: date) -> Habit:
    """Undo today's completion. Leaves any Skip untouched: the day becomes "neither" (DAY-1)."""
    existing_completion = db.query(Completion).filter_by(habit_id=habit.id, day=today).first()
    if existing_completion:
        db.delete(existing_completion)
        db.commit()
    return habit
```

`app/api/habits.py`, placed directly after `complete_habit` (`:50-57`), before `skip_habit` (`:60`):

```python
@router.delete("/{habit_id}/complete", response_model=HabitOut)
def uncomplete_habit(habit_id: int, db: Session = Depends(get_db)):
    habit = habit_service.get_habit(db, habit_id)
    if habit is None:
        raise HTTPException(status_code=404, detail="Habit not found")
    today = date.today()
    habit_service.uncomplete_habit(db, habit, today)
    return habit_service.to_summary(habit, today)
```

No `try/except`: the service raises nothing (unlike `skip_habit`, `:66-69`). `to_summary` sees the
deletion because the commit expires `habit` (`app/database.py:8`), the same mechanism the unskip route
relies on (`app/services/habit_service.py:146` then `app/api/habits.py:80`).

### Client — `habit-tracker-client` (summary; full text in the companion)

- `app/lib/api.ts` (frozen; edit granted to client slice 1 by the Lead), directly after
  `completeHabit` (`:71-73`):
  `export function uncompleteHabit(id: number): Promise<Habit>` →
  `request<Habit>(`/habits/${id}/complete`, { method: "DELETE" })`.
- `HabitCardProps` and `HabitListProps` gain `onUncomplete?: (id: number) => void`, listed after
  `onPriorityChange?`. Optional (A2). `HabitList` forwards it to every card.
- Card primary button (A4): when `completed_today`, text `Undo`, `aria-label`
  ``Undo today's completion of ${habit.name}``, `onClick` → `onUncomplete?.(habit.id)`,
  `disabled={habit.archived || !onUncomplete}`. Otherwise exactly as today ("Mark done", no
  `aria-label`, `disabled={habit.archived}`).
- `app/page.tsx`: `async function handleUncomplete(id: number)` after `handleUnskip` (`:113-116`),
  shaped like `handlePinToggle` (`:172-180`), passed as `onUncomplete={handleUncomplete}` to
  `HabitList` (`:441-459`).

Public: the route above and `uncompleteHabit`. Frozen: everything listed under "Not changed".

## Slices, in order

Five slices: two on the server, three on the client. Each is one commit
`undo-today slice N: <what>` on its repository's `feature/undo-today` branch, in that repository's
worktree `.claude/worktrees/undo-today`, with N numbered per repository. None is helper-eligible:
every slice touches product code.

**Cross-repository edge.** `build-client-undo-today-1` ⊣ `verify-server-undo-today-2` (green).
The client's api slice codes against the route and the `HabitOut` response; that frozen contract
exists only once server slice 2 is verified. Client slices 2 and 3 follow client slice 1 on the
normal chain.

Board order: `build-server-undo-today-1` → `verify-server-undo-today-1` →
`build-server-undo-today-2` → `verify-server-undo-today-2` → `build-client-undo-today-1` → … →
`verify-client-undo-today-3`, then `review-server-undo-today` and `review-client-undo-today`.

Server gate for every server slice: `.venv/bin/python -m pytest -q` (all pass; no linter configured).
Client gate for every client slice: `npm test`, `npx tsc --noEmit` (clean), `npm run lint` (at most 9
errors, the baseline, and none in a file the slice touched), `npm run build`. Expected test-count
deltas are relative to the count the verifier observes on the previous slice's head (or the base for
slice 1).

1. **`build-server-undo-today-1` — service `uncomplete_habit` with explicit-date tests.**
   - Files: `app/services/habit_service.py` (new function, Interfaces above), `tests/test_habit_service.py`
     (extend the `from app.services.habit_service import (...)` tuple with `create_habit` and
     `uncomplete_habit`; add `from app.models.habit import Completion, Skip`; two new tests at the end).
   - Tests added, both taking the `db_session` fixture and explicit dates:
     - `test_uncomplete_habit_deletes_only_the_given_days_completion`: create a habit with
       `create_habit(db_session, "Run")`; add `Completion` rows for `date(2026, 1, 5)` and
       `date(2026, 1, 6)`; commit; call `uncomplete_habit(db_session, habit, date(2026, 1, 6))`;
       assert it returns the same habit and the habit's remaining completion days are exactly
       `[date(2026, 1, 5)]`.
     - `test_uncomplete_habit_leaves_skips_and_is_a_no_op_without_a_completion`: create a habit; add a
       `Skip` for `date(2026, 1, 6)`; commit; call `uncomplete_habit(..., date(2026, 1, 6))` twice;
       assert no exception, zero `Completion` rows for the habit, and the `Skip` for `date(2026, 1, 6)`
       still present.
   - Verifier knows it is done when: the server gate passes with exactly +2 tests; `git diff` touches
     only those two files; `grep -n "date.today" app/services/habit_service.py` returns nothing
     (`TIME-1`); the function never references `Skip`; `app/models/habit.py` and `app/schemas.py`
     are unchanged. Probe: the first test fails if the builder filters by `habit_id` alone.

2. **`build-server-undo-today-2` — route `DELETE /habits/{habit_id}/complete` with endpoint tests.**
   - Files: `app/api/habits.py` (new route, Interfaces above), `tests/test_habits_api.py` (import line
     becomes `from datetime import date, timedelta`; add `from app.models.habit import Completion`;
     nine new tests after `test_unskip_unknown_habit_404s`, `:308-310`).
   - Tests added (all through `client`; the fifth also takes `db_session`, which is the same session
     the client uses, `tests/conftest.py:28-39`):
     1. `test_uncomplete_habit_removes_today_completion`: complete, then `DELETE`; 200,
        `completed_today` false, `str(date.today())` not in `completed_days`, `streak` 0.
     2. `test_uncomplete_habit_is_idempotent`: never completed; take the habit's entry from
        `GET /habits`; `DELETE` → 200 and the body equals that entry.
     3. `test_uncomplete_unknown_habit_404s`: `DELETE /habits/999/complete` → 404 and
        `resp.json() == {"detail": "Habit not found"}`.
     4. `test_uncomplete_then_complete_again`: complete, undo, complete → 200, `completed_today` true,
        `streak` 1.
     5. `test_uncomplete_keeps_streak_anchored_on_yesterday`: seed
        `Completion(habit_id=…, day=date.today() - timedelta(days=1))` through `db_session` and commit;
        complete today → `streak` 2; undo → `streak` 1 and `longest_streak` 1 (`STREAK-1`;
        `app/services/habit_service.py:21-22`).
     6. `test_uncomplete_decrements_completed_this_week`: complete → `completed_this_week` 1; undo → 0
        (`WEEK-1`).
     7. `test_uncomplete_is_reflected_in_stats`: complete → `GET /habits/stats` has `completed_today` 1
        and `total_completions` 1; undo → both 0.
     8. `test_uncomplete_after_freeze_then_complete_leaves_day_neither`: skip, complete, undo →
        `completed_today` false, `skipped_today` false, `skipped_days == []` (D3, `DAY-1`).
     9. `test_uncomplete_archived_habit_is_allowed`: complete, `PATCH {"archived": true}`, undo → 200,
        `completed_today` false (D5: no server-side archived check).
   - Verifier knows it is done when: the server gate passes with exactly +9 tests; `git diff` touches
     only those two files; `grep -n "date.today" app/api/habits.py` shows the new route resolves it
     once and passes the same `today` to the service and `to_summary`; the route has
     `response_model=HabitOut` (`OUT-1`). Probe: `DELETE /habits/{id}` (204, `:102-107`) still deletes
     the whole habit and is not shadowed by the new path.
   - On green, the cross-repository contract is frozen and `build-client-undo-today-1` may start.

3. **`build-client-undo-today-1` — `uncompleteHabit` in `app/lib/api.ts`.** Depends on
   `verify-server-undo-today-2` green. **The Lead grants this slice an edit to the frozen
   `app/lib/api.ts`** (one new function, nothing else in that file changes).
   - Files: `app/lib/api.ts`, `app/lib/__tests__/api.test.ts`.
   - Test added: `uncompleteHabit issues a DELETE to the complete endpoint`, after the unskip test
     (`:168-184`) and modelled on it; `uncompleteHabit` added to the import list in alphabetical order.
   - Verifier knows it is done when: the client gate passes with +1 test; the URL substring is
     `/habits/2/complete` and `method` is `DELETE`; `git diff app/lib/api.ts` is a single added
     function using `request<Habit>` (`API-1`); `app/types/HabitTypes.ts` and `package*.json` unchanged.

4. **`build-client-undo-today-2` — the card's Undo control and its forwarding through `HabitList`.**
   - Files: `app/components/HabitCard.tsx`, `app/components/HabitList.tsx`,
     `app/components/__tests__/HabitCard.test.tsx`, `app/components/__tests__/HabitList.test.tsx`.
   - Tests: rewrite `HabitCard.test.tsx:153-167` in place (A5); add three card tests (Undo calls
     `onUncomplete` with the id; Undo disabled when archived; Undo disabled without a handler) and one
     list test (forwards `onUncomplete`). Exact bodies in the companion.
   - Verifier knows it is done when: the client gate passes with +4 tests (the rewrite keeps the count);
     `npx tsc --noEmit` is clean without editing any existing render (proves A2); the untouched tests
     `calls onComplete with the habit id when marking done` (`:135-151`) and
     `disables the freeze button once already completed today` (`:318-332`) still pass;
     `app/archive/page.tsx` and `app/globals.css` unchanged.

5. **`build-client-undo-today-3` — `handleUncomplete` on the home page.**
   - Files: `app/page.tsx` only.
   - Tests: none added; `app/page.tsx` is outside `TEST-1`'s scope and has no test sibling today.
   - Verifier knows it is done when: the full client gate passes with the same test count as slice 2;
     the diff is the import, the handler (shape of `handlePinToggle`, message A7) and one
     `onUncomplete={handleUncomplete}` prop on `HabitList`; complete-all (`:255-270`) is untouched (D4);
     no `window.confirm` (D6). Optional live probe: run both feature branches, complete a habit, press
     Undo, and observe "Mark done", the freeze control enabled, and the header count drop.

## Decisions left to implementation

None.

## Risks

- **The error banner may never show.** `loadHabits` calls `setError(null)` synchronously
  (`app/page.tsx:52`, read to confirm the D6 pattern), so in the `catch` the banner set just before it
  is likely overwritten in the same render batch; the user then sees a reload, not a message. This is
  true of `handlePinToggle` today. D6 mandates that pattern, so slice 5 copies it exactly; fixing it
  would change existing handlers and is out of scope. Flagged for the Design gate; a verifier probing
  failure in the live app will see it.
- **Freeze lost after freeze → complete → undo** (D3). Intended; server slice 2 test 8 pins it so a later
  "restore the freeze" change is a visible decision.
- **Date edge at midnight.** The client's "today" is the browser's, the server's is the server's local
  date (`TIME-1` note in the contract). An undo pressed just after the server's midnight deletes
  nothing and returns 200 with `completed_today` false. Same exposure as complete and freeze today;
  no slice changes it.
- **Undo is not visible as "Done today" any more.** A4 replaces the disabled "Done today" text with
  `Undo` in the emerald palette. If the human wants the word "done" kept on the card, it is a label
  change in slice 4 only and must not reuse "done today" in the accessible name (Testing Library
  ambiguity).
- **Builders reusing the wrong twin.** Copying `complete_habit` instead of `unskip_habit` would touch
  `Skip`; slice 1's second test and the verifier's grep catch it. Making `onUncomplete` required would
  show as `tsc` errors in the two component test files and `app/archive/page.tsx`.
- **Lint baseline drift.** Nothing here adds an effect; any new error in a touched file fails the slice
  even if the total stays at 9.
