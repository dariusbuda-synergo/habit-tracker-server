# Change contract — undo-today

> Fill every section. Cite `path:line` for every fact about existing code. Subsystem names and
> invariant codes come from the repository's `AGENTS.md`.

Feature: **Undo today's completion.** A habit marked done today can be un-marked the same day.
The API removes today's completion for that habit (idempotent; 404 for an unknown habit) and the
card's "Done today" state becomes an Undo action. Streaks and weekly counts follow from the stored
completions as they do today. Out of scope: undoing past days, undoing freezes (already exists),
bulk undo.

Primary contract. It spans two repositories: server sections first, then client sections. The client
repository carries a companion with the client sections in full:
`habit-tracker-client/docs/undo-today/design/2026-10-15-undo-today-contract.md`.

Sources. The facts come from the codegraph index (`search_symbols`, `find_callers`,
`find_references`): server at `ceea25a`, client indexed 2026-10-15T06:33Z after `d9f7527`. Both
primary checkouts were on those commits with clean working trees when this was written. Line
numbers come from repository reads of those revisions. Where the index has no answer (decorator
arguments, JSX attributes, test bodies, config files), the fact was read from the file and is cited
the same way.

---

# Server — `habit-tracker-server`

## Affected subsystems

From `AGENTS.md § Subsystems`:

| Subsystem | Role in this change |
|---|---|
| `app/api/habits.py` | **changes**: one new route that resolves the habit, 404s, resolves `today` and returns `to_summary` |
| `app/services/habit_service.py` | **changes**: one new service function that deletes today's `Completion` row for the habit |
| `tests/test_habits_api.py` | **changes**: endpoint tests for the new route |
| `tests/test_habit_service.py` | read only. The feature changes none of `compute_streak`, `compute_longest_streak`, `is_at_risk`, `count_completions_in_week` (the gate's trigger list, `AGENTS.md § Mechanical gate`) |
| `app/models/habit.py` | read only (frozen). `Completion` already exists with the needed shape (`app/models/habit.py:29-37`) |
| `app/schemas.py` | read only (frozen). `HabitOut` already carries `completed_today` (`app/schemas.py:54`) |
| `app/database.py`, `app/main.py`, `app/config.py` | read only |
| `tests/conftest.py` | read only. The `db_session` and `client` fixtures are reused (`tests/conftest.py:13-39`) |

## The existing pattern this change follows

**Router: the closest twin is undo-freeze, `DELETE /habits/{habit_id}/skip`** (`app/api/habits.py:73-80`):
- `@router.delete("/{habit_id}/skip", response_model=HabitOut)` (`app/api/habits.py:73`).
- It loads the habit with `habit_service.get_habit(db, habit_id)` and raises `HTTPException(status_code=404, detail="Habit not found")` on `None` (`app/api/habits.py:75-77`). Every per-habit route repeats this inline: complete `:52-54`, skip `:62-64`, patch `:85-87`, delete `:104-106`. There is no shared dependency for it.
- `today = date.today()` is resolved in the router (`app/api/habits.py:78`) and passed to the service (`:79`) and to `to_summary` (`:80`). This is how `TIME-1` is applied.
- It returns `habit_service.to_summary(habit, today)` as `HabitOut` with status 200 (`app/api/habits.py:80`).

Other related routes:
- Complete: `POST /habits/{habit_id}/complete` (`app/api/habits.py:50-57`), same shape as unskip.
- Freeze: `POST /habits/{habit_id}/skip` (`app/api/habits.py:60-70`). This is the only route that maps a service `ValueError` to 409 (`:66-69`).
- Delete habit: `DELETE /habits/{habit_id}` returns 204 with no body (`app/api/habits.py:102-107`). It is the only body-less route.

**Service: the closest twin is `unskip_habit(db, habit, today)`** (`app/services/habit_service.py:142-147`). It queries `Skip` with `filter_by(habit_id=habit.id, day=today).first()`. If a row exists it calls `db.delete(...)` and `db.commit()`. Otherwise it does nothing. It returns `habit`. That no-op branch is the whole of its idempotency.
- `complete_habit` is the inverse operation (`app/services/habit_service.py:117-127`). It checks for an existing `Completion` for `(habit.id, today)`. If there is none, it **deletes any same-day `Skip`** (`:122-124`), adds a `Completion` (`:125`) and commits (`:126`).
- `skip_habit` refuses a completed day with `ValueError` (`app/services/habit_service.py:132-134`).

**Why `to_summary` sees the deletion.** `to_summary` rebuilds every derived field from `habit.completions` and `habit.skips` (`app/services/habit_service.py:234-256`). `SessionLocal` does not override `expire_on_commit` (`app/database.py:8`), so the commit inside the service expires `habit`, and the router's `to_summary` call reloads both relationships. The unskip route already depends on this (`app/services/habit_service.py:146` followed by `app/api/habits.py:80`). The `Habit.completions` relationship has `cascade="all, delete-orphan"` (`app/models/habit.py:21-23`).

**Tests: the closest twins are the three unskip tests:**
- `test_unskip_habit_removes_the_freeze` (`tests/test_habits_api.py:293-298`)
- `test_unskip_habit_is_idempotent` (`tests/test_habits_api.py:301-305`)
- `test_unskip_unknown_habit_404s` (`tests/test_habits_api.py:308-310`)

The complete tests have the same structure: `tests/test_habits_api.py:62-81`. The API tests run against the real `date.today()` (for example `tests/test_habits_api.py:268`). The pure-function tests in `tests/test_habit_service.py` pass explicit dates. No test calls `complete_habit`, `skip_habit` or `unskip_habit` directly. They are covered only through `TestClient`, but `tests/conftest.py:13-25` provides a `db_session` fixture that a service-level test could use with an explicit `today`.

## Invariants to preserve

From `habit-tracker-server/AGENTS.md § Invariants`:

- `DAY-1`: each habit-day is completed, skipped, or neither. Undo moves a day from "completed" to "neither". It must not create a `Skip`, and it must not touch a `Skip` row. The risk is in the reverse direction: `complete_habit` deletes a same-day freeze before it inserts the completion (`app/services/habit_service.py:122-124`). After freeze, then complete, then undo, the day is "neither", not "frozen". The freeze is gone. This is consistent with `DAY-1` but may surprise the user (open question 3). The unique constraint `uq_habit_day` (`app/models/habit.py:31`) means at most one row matches, so `.first()` is sufficient.
- `STREAK-1`: skips must be treated the same in both streak functions. Undo changes only `completed_days`. Both `compute_streak` (`app/services/habit_service.py:8-31`) and `compute_longest_streak` (`:34-58`) recompute from the stored rows. If undo were implemented as anything other than deleting the `Completion` row (a flag, a tombstone row, a skip conversion), the two functions could start to disagree. Expected effect, from existing code: with today no longer done, `compute_streak` anchors on yesterday (`app/services/habit_service.py:21-22`, covered by `tests/test_habit_service.py:21`). The current streak therefore drops by one and does not reset to 0. `longest_streak` can also drop, because it is recomputed from all days (`:42-58`). Nothing is cached.
- `TIME-1`: only the router may call `date.today()`. The new service function must take `today` as a parameter, like `unskip_habit(db, habit, today)` (`app/services/habit_service.py:142`). The router resolves it once and passes the same value to `to_summary` (pattern at `app/api/habits.py:78-80`). Breaking this makes the function untestable with explicit dates. "Today" here means the server's local date. The client's "today" is the browser's. That mismatch already exists for complete and freeze.
- `WEEK-1`: weeks start on Monday. `completed_this_week` comes from `count_completions_in_week` over `start_of_week(today)` (`app/services/habit_service.py:61-68`). After undo it drops by one. `at_risk` can turn true again, because `is_at_risk` short-circuits only while `completed_today` is true (`app/services/habit_service.py:225-226`). No week math changes. This invariant could break only if the change touched `start_of_week` or `count_completions_in_week`, which it does not need to.
- `OUT-1`: every habit response must be `to_summary()` validated by `HabitOut`. If the endpoint returns a habit, it must be `to_summary(habit, today)` with `response_model=HabitOut`, like every per-habit mutation (`app/api/habits.py:50,57,73,80`). No new field is needed (see Data and interfaces), so `to_summary`, `HabitOut` and the client `HabitTypes.ts` stay untouched. If anyone adds a field anyway, `OUT-1` and the client's `TYPES-1` require all three to change in the same feature.
- `DB-1`: there are no migrations. The change needs no new column and no new table, because it deletes rows from the existing `completions` table (`app/models/habit.py:29-37`). Adding a column to `habits` or `completions` (for example an "undone" flag) would break existing database files. `create_all` never alters existing tables (`app/main.py:8`).
- `CORS-1`: unaffected. `allow_methods=["*"]` (`app/main.py:15`) already admits `DELETE`, which undo-freeze uses from the browser.

## Data and interfaces touched

- **Tables**: `completions` (`app/models/habit.py:29-37`). The change deletes at most one row per call, matched by `(habit_id, day=today)` under the unique `uq_habit_day` (`:31`). `habits` and `skips` are not written. No schema change.
- **Endpoints**: one new per-habit endpoint under the `/habits` router prefix (`app/api/habits.py:10`). The route and verb are open (open question 1). The existing precedent for "undo X" is `DELETE` on the same path as the `POST` that did X (`/skip`: `app/api/habits.py:60` and `:73`). Applied to completion, that would be `DELETE /habits/{habit_id}/complete`, the inverse of `app/api/habits.py:50`. Required behaviour, from the feature statement:
  - unknown habit returns 404 `{"detail": "Habit not found"}` (`app/api/habits.py:75-77`).
  - a habit not completed today returns 200, unchanged (idempotent, like `tests/test_habits_api.py:301-305`). There is no 409.
  - a habit completed today has its row removed.
- **Response model**: `HabitOut` (`app/schemas.py:40-58`) already exposes everything the card needs: `completed_today: bool` (`:54`), `streak` (`:52`), `longest_streak` (`:53`), `completed_this_week` (`:51`), `completed_days` (`:55`), `at_risk` (`:58`). `to_summary` fills `completed_today` as `today in completed_days` (`app/services/habit_service.py:238,251`). **No field needs to be added to `HabitOut` or `HabitStats`.**
- **Aggregates**: `GET /habits/stats` (`app/api/habits.py:32-34`) is recomputed on every request from `to_summary` (`app/services/habit_service.py:185-212`). After an undo, `completed_today` (`:199`), `total_completions` (`:203`), `active_streaks`, `best_streak` and `weekly_completion_rate` follow on their own. No change is needed.
- **Configuration, events, external contracts**: none. The only consumer is `../habit-tracker-client` (`AGENTS.md § What this is`).

## What changes

Behaviour: one new endpoint removes today's completion for one habit and returns the habit (the
response shape is open question 2). Streak, weekly count, at-risk and stats change only because
they are recomputed from the stored rows. Nothing else changes.

Files:
- `app/api/habits.py`: one new route function with the 404 check and `today = date.today()` (pattern at `:73-80`).
- `app/services/habit_service.py`: one new function `(db, habit, today) -> Habit` that deletes the matching `Completion` if one exists and commits (pattern at `:142-147`). It imports nothing new, because `Completion` is already imported (`:5`).
- `tests/test_habits_api.py`: new tests, modelled on `:293-310` and `:62-81`:
  - undo removes today's completion (`completed_today` false, `completed_days` without today).
  - undo on a habit not completed today returns 200 and leaves it unchanged.
  - undo on an unknown habit returns 404.
  - undo leaves a streak built on earlier days anchored on yesterday.
  - undo decrements `completed_this_week`.
  - undo is reflected in `/habits/stats` `completed_today`.
  - the habit can be completed again after undo.
- Optional: a service-level test with an explicit `today` through the `db_session` fixture (`tests/conftest.py:13-25`). It would cover `TIME-1` directly. No such test exists for the sibling functions.

Frozen files (`AGENTS.md § Branching`: `app/models/habit.py`, `app/schemas.py`, `requirements.txt`,
`requirements-dev.txt`): **the feature needs to touch none of them.**

Mechanical gate: `.venv/bin/python -m pytest -q` (`AGENTS.md § Mechanical gate`). Because the
streak and week functions do not change, the gate does not require new `tests/test_habit_service.py`
cases.

---

# Client — `habit-tracker-client`

## Affected subsystems

From `habit-tracker-client/AGENTS.md § Subsystems`:

| Subsystem | Role in this change |
|---|---|
| `app/lib/api.ts` | **changes (frozen file)**: one new function for the new endpoint |
| `app/components/` (`HabitCard`, likely `HabitList`) | **changes**: the "Done today" state becomes an Undo action. `HabitList` forwards card callbacks (`app/components/HabitList.tsx:48-60`) |
| `app/page.tsx` | **changes**: one new handler that calls the API and replaces the habit in state |
| `app/archive/page.tsx` | **affected**: it renders the same `HabitList` with its own handler set (`app/archive/page.tsx:151-163`). It must change if `HabitList` gains a required prop |
| `app/types/HabitTypes.ts` | read only (frozen). `Habit.completed_today` already exists (`app/types/HabitTypes.ts:13`) |
| `app/history/page.tsx`, `app/stats/page.tsx` | read only. Both fetch once on mount (`app/history/page.tsx:16-21`, `app/stats/page.tsx:16-21`) and so reflect an undo on the next visit |
| `app/lib/export.ts` | read only. It exports `completed_today` as a column (`app/lib/export.ts:12`). No change |
| `test/mock-data.ts` | read only. `makeMockHabit` accepts `completed_today` overrides (`test/mock-data.ts:3-23`) |

## The existing pattern this change follows

**API function: the twin is `unskipHabit`** (`app/lib/api.ts:79-81`): `request<Habit>(\`/habits/${id}/skip\`, { method: "DELETE" })`.
- `completeHabit` is the inverse (`app/lib/api.ts:71-73`, `POST /habits/${id}/complete`).
- Every call goes through `request<T>()` (`app/lib/api.ts:5-17`). It throws on non-2xx (`:10-12`) and returns `undefined` on 204 (`:13-15`).
- `deleteHabit` is the only `Promise<void>` function (`app/lib/api.ts:83-85`).
- The test sibling is `app/lib/__tests__/api.test.ts`. The twin test is `unskipHabit issues a DELETE to the skip endpoint` (`:168-184`), which stubs `fetch`, asserts the URL substring and `method`, and asserts the parsed result.

**Card: the "Done today" button and the freeze/undo-freeze toggle** (`app/components/HabitCard.tsx:236-252`):
- The primary button calls `onComplete(habit.id)` (`:237`), is `disabled={habit.completed_today || habit.archived}` (`:238`), and has the label `{habit.completed_today ? "Done today" : "Mark done"}` (`:241`). Today "Done today" is a **disabled** label, not an action.
- The freeze control is the precedent for a state-dependent toggle on one button:
  - `onClick={() => (habit.skipped_today ? onUnskip(habit.id) : onSkip(habit.id))}` (`:244`).
  - its `aria-label` switches between `Unfreeze ${name}` and `Freeze ${name} for today` (`:246-248`).
  - its classes switch to the sky "active" palette while frozen (`:249`), and its text is `Unfreeze` / `🧊 Freeze` (`:251`).
  - it is disabled while `completed_today` (`:245`). After an undo, the freeze control becomes available again with no extra code.
- Callbacks are props typed `(id: number) => void` (`app/components/HabitCard.tsx:22-24`). Two later additions are optional (`onPinToggle?`, `onPriorityChange?`, `:35-36`) and render their control only when passed (`:141`, `:157`).
- `HabitList` declares the same callbacks (`app/components/HabitList.tsx:4-22`) and passes them through (`:48-60`).

**Page refresh after a mutation** (`app/page.tsx`):
- `handleComplete`, `handleSkip` and `handleUnskip` (`app/page.tsx:103-116`) all `await` the API function and then replace the one habit in state with the returned summary: `setHabits((prev) => prev.map((h) => (h.id === id ? updated : h)))`. There is no list refetch and no `try/catch`.
- The newer handlers `handlePinToggle` and `handlePriorityChange` wrap the same update in `try/catch`. On failure they `setError(...)` and fall back to `loadHabits(...)` (`app/page.tsx:172-190`).
- Header counts and the complete-all button are derived from state on each render. `pendingToday` is `!h.completed_today && !h.archived` (`app/page.tsx:251`) and `doneToday` counts `completed_today` (`:253`). They follow an updated summary without extra code.
- `app/archive/page.tsx:37-50` duplicates the same three handlers.

**Tests (`TEST-1` siblings)**:
- `app/components/__tests__/HabitCard.test.tsx`:
  - `calls onComplete with the habit id when marking done` (`:135-151`)
  - **`disables the button once already completed today`** (`:153-167`), which asserts that the `/done today/i` button is disabled. This feature intentionally reverses that test's expectation.
  - the freeze and unfreeze tests (`:282-316`)
  - `disables the freeze button once already completed today` (`:318-332`)
- `app/components/__tests__/HabitList.test.tsx` renders `HabitList` with only the required callbacks (`:8`, `:14`, `:22-29`).
- `app/lib/__tests__/api.test.ts:132-184`.
- There is no test for `app/page.tsx` or `app/archive/page.tsx`. The only page test is `app/login/__tests__/page.test.tsx`.

**Completion sound and animation**: none exists to mirror. The settings page stores
`habit-sound-enabled` (`app/settings/page.tsx:34`, `:38-41`, `:160-175`), but nothing else in
`app/` reads it (`habit-tracker-client/docs/settings/README.md` agrees: stored, not acted on). The
only completion "animation" is the progress-bar width transition (`app/components/HabitCard.tsx:218`).
That transition animates in reverse when `completed_this_week` drops.

## Invariants to preserve

From `habit-tracker-client/AGENTS.md § Invariants`:

- `TYPES-1`: `HabitTypes.ts` must mirror `HabitOut` field for field. No field is needed: `Habit.completed_today` (`app/types/HabitTypes.ts:13`) already mirrors `HabitOut.completed_today` (`app/schemas.py:54`). The risk is adding a client-only or server-only field (for example `can_undo`) on one side, which breaks the mirror. A new field must be added to both repositories in this feature, or not at all.
- `API-1`: all network access goes through `request()` in `app/lib/api.ts`. The new call must be a function in `app/lib/api.ts` that uses `request()` (`app/lib/api.ts:5-17`). It must not be an inline `fetch` in the page or the card. Note that if the server answers 204, `request` returns `undefined` (`:13-15`). The page's replace-in-state pattern (`app/page.tsx:103-116`) would then have nothing to put in state, so the response shape (open question 2) decides which page pattern applies.
- `SSR-1`: browser-only state is read only after mount. Whether a habit is done today must keep coming from the API's `completed_today`. If the client derived it (for example by comparing `completed_days` with `new Date()` in the browser), it would add browser-only `Date` logic in render, which `SSR-1` forbids outside a `useEffect` (precedent: `app/page.tsx:61-74`). It would also disagree with the server's `date.today()` (server `TIME-1`).
- `TEST-1`: every new or changed module under `app/lib` or `app/components` needs a `__tests__` sibling.
  - Changing `api.ts` requires `app/lib/__tests__/api.test.ts`.
  - Changing `HabitCard.tsx` requires `app/components/__tests__/HabitCard.test.tsx`, where `:153-167` must be rewritten, not deleted.
  - Changing `HabitList.tsx` requires `app/components/__tests__/HabitList.test.tsx`.
  - Also note: `tsconfig.json` includes `**/*.tsx`, so `npx tsc --noEmit` type-checks the tests. A new **required** callback prop on `HabitCard` or `HabitList` turns every existing render in those two test files into a type error. There are 19 `<HabitCard` renders in `HabitCard.test.tsx` and three `<HabitList` renders in `HabitList.test.tsx`. The same applies to `app/archive/page.tsx:151-163`. The optional-prop precedent is `app/components/HabitCard.tsx:35-36`.
  - A Testing Library side note: the current tests use `getByRole("button", { name: /done today/i })` (`:166`) and `/mark done/i` (`:149`). `getByRole` throws on multiple matches, so the accessible names of the new control and any remaining "done" label must not both match the same pattern.
- `PREFS-1`: preferences stay in localStorage and are never sent to the API. This is only at risk if the design wires the sound preference. A completion or undo sound would read `habit-sound-enabled` client-side only.
- `AUTH-1`: unaffected. No new route or page.
- Mechanical gate, lint: the baseline has 9 errors (`AGENTS.md § Mechanical gate`). A slice must not add to that count. The relevant rule is `react-hooks/set-state-in-effect`, which applies only if the change adds state in an effect. The existing mutation handlers do not use effects (`app/page.tsx:103-116`).

## Data and interfaces touched

- **Endpoint consumed**: the new server endpoint (see the server section above). Today the client
  consumes `POST /habits/{id}/complete` (`app/lib/api.ts:71-73`), `POST /habits/{id}/skip`
  (`:75-77`) and `DELETE /habits/{id}/skip` (`:79-81`).
- **Types**: `Habit` (`app/types/HabitTypes.ts:1-18`), unchanged. `HabitStats` (`:20-31`), unchanged.
- **Component props**: `HabitCardProps` (`app/components/HabitCard.tsx:20-37`) and `HabitListProps`
  (`app/components/HabitList.tsx:4-22`) gain whatever callback the design chooses.
- **localStorage, cookies, configuration**: none.

## What changes

Behaviour: on a habit completed today, the card's "Done today" state is an Undo action instead of a
disabled label. Activating it calls the new endpoint and replaces the habit with the returned summary.
The card then shows "Mark done" again and the freeze control becomes available again (`:245`). The
streak line (`app/components/HabitCard.tsx:200-207`), the weekly progress (`:208-231`), the "Due today"
badge (`:181-189`), the header "x/y done today" (`app/page.tsx:253`, `:290-294`) and the complete-all
count (`:251`, `:405`) all update from the returned summary.

Files:
- `app/lib/api.ts` (**frozen**): one new function modelled on `unskipHabit` (`:79-81`).
- `app/components/HabitCard.tsx`: the primary button's `disabled` / `onClick` / label for the `completed_today` case (`:236-242`), plus a new callback prop.
- `app/components/HabitList.tsx`: forward the new callback (`:4-22`, `:48-60`).
- `app/page.tsx`: one new handler next to `handleUnskip` (`:113-116`), passed to `HabitList` (`:441-459`).
- `app/archive/page.tsx`: pass a handler too, or not. This depends on whether the prop is required and on open question 5. Archived cards keep the complete button disabled (`app/components/HabitCard.tsx:238`).
- Tests:
  - `app/lib/__tests__/api.test.ts`: a new case modelled on `:168-184`.
  - `app/components/__tests__/HabitCard.test.tsx`: rewrite `:153-167`; add "calls the undo callback with the habit id when done today"; keep `:318-332`.
  - `app/components/__tests__/HabitList.test.tsx`: if its props change.

Frozen files (`AGENTS.md § Branching`: `package.json`, `package-lock.json`,
`app/types/HabitTypes.ts`, `app/lib/api.ts`, `app/globals.css`):
- **The feature must touch `app/lib/api.ts`**. This is a Lead-owned change during fan-out.
- It does not need `app/types/HabitTypes.ts`, `app/globals.css` or the package files.

Mechanical gate (`AGENTS.md § Mechanical gate`): `npm test`, `npx tsc --noEmit`, `npm run lint`
(no new errors over the 9-error baseline), `npm run build`.

---

## Summary of frozen-file impact

| Repository | Frozen file | Touched? |
|---|---|---|
| server | `app/models/habit.py` | no: `Completion` exists (`app/models/habit.py:29-37`) |
| server | `app/schemas.py` | no: `HabitOut.completed_today` exists (`app/schemas.py:54`) |
| server | `requirements*.txt` | no |
| client | `app/lib/api.ts` | **yes**: one new endpoint function |
| client | `app/types/HabitTypes.ts` | no: `Habit.completed_today` exists (`app/types/HabitTypes.ts:13`) |
| client | `package*.json`, `app/globals.css` | no |

## Open questions

1. **Route and verb.** Should it be `DELETE /habits/{id}/complete`, mirroring undo-freeze's `DELETE /habits/{id}/skip` (`app/api/habits.py:73`)? Or a distinct path such as `POST /habits/{id}/uncomplete`?
2. **Response body.** Should it return `200` with the updated `HabitOut`, like complete, skip and unskip (`app/api/habits.py:57,70,80`), which lets the page keep its replace-in-state pattern? Or `204`, like `DELETE /habits/{id}` (`:102`), which forces a refetch on the client (`app/lib/api.ts:13-15`)?
3. **Freeze after undo.** Completing a frozen day deletes the freeze (`app/services/habit_service.py:122-124`). Should undo leave the day "neither" (the simplest option, consistent with `DAY-1`), or restore the freeze that the completion replaced? Restoring it would need a record of the prior state that does not exist today.
4. **Complete-all and other views.** Should undo appear only on the card? It could also appear as an undo for the complete-all action (`app/page.tsx:255-270`), which looks like bulk undo and is out of scope as stated, or in the history strip (`app/history/page.tsx`), which is read-only today.
5. **Archived habits.** Archived cards disable "Mark done" (`app/components/HabitCard.tsx:238`) and appear on `/archive` (`app/archive/page.tsx:151-163`). Should Undo also be disabled for an archived habit that was completed today? Should the server refuse it? The complete endpoint does not check `archived` (`app/api/habits.py:50-57`).
6. **Confirmation and feedback.** Should Undo act immediately, like Unfreeze (`app/components/HabitCard.tsx:244`), or ask first, like Remove (`:272`)? Should a failed undo show an error and reload (`app/page.tsx:172-190`), or follow the unguarded complete and freeze handlers (`:103-116`)?
7. **Sound or animation counterpart.** The completion-sound preference is stored but never played (`app/settings/page.tsx:160-175`), so no completion feedback exists to mirror. Is "no counterpart" acceptable for this feature?
