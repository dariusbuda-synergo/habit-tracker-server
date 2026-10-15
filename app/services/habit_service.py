from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.habit import Completion, Habit, Skip


def compute_streak(
    completed_days: list[date], today: date, skipped_days: list[date] | None = None
) -> int:
    """Consecutive days ending today or yesterday. A gap of 2+ uncovered
    days breaks it. A skipped (frozen/rest) day neither adds to the streak
    nor breaks it -- the count just pauses across it."""
    days = set(completed_days)
    skipped = set(skipped_days or ())
    if not days:
        return 0

    if today in days or today in skipped:
        cursor = today
    elif today - timedelta(days=1) in days or today - timedelta(days=1) in skipped:
        cursor = today - timedelta(days=1)
    else:
        return 0

    streak = 0
    while cursor in days or cursor in skipped:
        if cursor in days:
            streak += 1
        cursor -= timedelta(days=1)
    return streak


def compute_longest_streak(
    completed_days: list[date], skipped_days: list[date] | None = None
) -> int:
    """Longest run of consecutive completed days ever, not just the current
    run ending today/yesterday that compute_streak tracks. A skipped/frozen
    day bridges a run exactly like it does for the current streak -- it
    neither extends nor breaks it, consistent with compute_streak's own
    treatment of skips."""
    days = set(completed_days)
    skipped = set(skipped_days or ())
    if not days:
        return 0

    all_days = sorted(days | skipped)
    longest = 0
    current = 0
    prev_day: date | None = None
    for day in all_days:
        if prev_day is not None and (day - prev_day).days > 1:
            current = 0
        if day in days:
            current += 1
            longest = max(longest, current)
        prev_day = day
    return longest


def start_of_week(day: date) -> date:
    """Monday of the week containing `day`."""
    return day - timedelta(days=day.weekday())


def count_completions_in_week(completed_days: list[date], today: date) -> int:
    week_start = start_of_week(today)
    return sum(1 for day in completed_days if week_start <= day <= today)


def create_habit(
    db: Session,
    name: str,
    category: str = "General",
    target_per_week: int = 7,
    notes: str | None = None,
    priority: str = "Medium",
) -> Habit:
    habit = Habit(
        name=name,
        category=category,
        target_per_week=target_per_week,
        notes=notes,
        priority=priority,
    )
    db.add(habit)
    db.commit()
    db.refresh(habit)
    return habit


def list_habits(
    db: Session,
    category: str | None = None,
    include_archived: bool = False,
    priority: str | None = None,
) -> list[Habit]:
    query = db.query(Habit)
    if category:
        query = query.filter(Habit.category == category)
    if priority:
        query = query.filter(Habit.priority == priority)
    if not include_archived:
        query = query.filter(Habit.archived.is_(False))
    return query.order_by(Habit.id).all()


def list_categories(db: Session) -> list[str]:
    rows = db.query(Habit.category).distinct().order_by(Habit.category).all()
    return [row[0] for row in rows]


def get_habit(db: Session, habit_id: int) -> Habit | None:
    return db.get(Habit, habit_id)


def complete_habit(db: Session, habit: Habit, today: date) -> Habit:
    already_done = db.query(Completion).filter_by(habit_id=habit.id, day=today).first()
    if not already_done:
        # Completing today always wins over an existing freeze on it --
        # a real completion is strictly better than a rest day.
        existing_skip = db.query(Skip).filter_by(habit_id=habit.id, day=today).first()
        if existing_skip:
            db.delete(existing_skip)
        db.add(Completion(habit_id=habit.id, day=today))
        db.commit()
    return habit


def skip_habit(db: Session, habit: Habit, today: date) -> Habit:
    """Freeze today: preserves the streak without counting as a completion."""
    already_done = db.query(Completion).filter_by(habit_id=habit.id, day=today).first()
    if already_done:
        raise ValueError("Habit is already completed today -- nothing to freeze.")
    already_skipped = db.query(Skip).filter_by(habit_id=habit.id, day=today).first()
    if not already_skipped:
        db.add(Skip(habit_id=habit.id, day=today))
        db.commit()
    return habit


def unskip_habit(db: Session, habit: Habit, today: date) -> Habit:
    existing_skip = db.query(Skip).filter_by(habit_id=habit.id, day=today).first()
    if existing_skip:
        db.delete(existing_skip)
        db.commit()
    return habit


def uncomplete_habit(db: Session, habit: Habit, today: date) -> Habit:
    """Undo today's completion. Leaves any Skip untouched: the day becomes "neither" (DAY-1)."""
    existing_completion = db.query(Completion).filter_by(habit_id=habit.id, day=today).first()
    if existing_completion:
        db.delete(existing_completion)
        db.commit()
    return habit


def update_habit(
    db: Session,
    habit: Habit,
    name: str | None = None,
    category: str | None = None,
    target_per_week: int | None = None,
    notes: str | None = None,
    archived: bool | None = None,
    priority: str | None = None,
    pinned: bool | None = None,
) -> Habit:
    if name is not None:
        habit.name = name
    if category is not None:
        habit.category = category
    if target_per_week is not None:
        habit.target_per_week = target_per_week
    if notes is not None:
        habit.notes = notes
    if archived is not None:
        habit.archived = archived
    if priority is not None:
        habit.priority = priority
    if pinned is not None:
        habit.pinned = pinned
    db.commit()
    db.refresh(habit)
    return habit


def delete_habit(db: Session, habit: Habit) -> None:
    db.delete(habit)
    db.commit()


def get_stats(db: Session, today: date) -> dict:
    summaries = [to_summary(habit, today) for habit in list_habits(db)]

    weekly_target_total = sum(s["target_per_week"] for s in summaries)
    weekly_completed_total = sum(s["completed_this_week"] for s in summaries)

    by_category: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    for summary in summaries:
        by_category[summary["category"]] = by_category.get(summary["category"], 0) + 1
        by_priority[summary["priority"]] = by_priority.get(summary["priority"], 0) + 1

    return {
        "total_habits": len(summaries),
        "completed_today": sum(1 for s in summaries if s["completed_today"]),
        "skipped_today": sum(1 for s in summaries if s["skipped_today"]),
        "active_streaks": sum(1 for s in summaries if s["streak"] > 0),
        "best_streak": max((s["streak"] for s in summaries), default=0),
        "total_completions": sum(len(s["completed_days"]) for s in summaries),
        "weekly_completion_rate": (
            round(weekly_completed_total / weekly_target_total * 100)
            if weekly_target_total
            else 0
        ),
        "pinned_count": sum(1 for s in summaries if s["pinned"]),
        "by_category": by_category,
        "by_priority": by_priority,
    }


def is_at_risk(
    target_per_week: int, completed_this_week: int, completed_today: bool, today: date
) -> bool:
    """True if hitting the weekly target now requires completing every
    remaining day of the week, including today.

    Not just "behind" -- there is still enough of the week left to recover
    unless every remaining day counts. Never at risk once today is already
    done, since today's own opportunity is spent either way.
    """
    if completed_today:
        return False
    remaining_needed = target_per_week - completed_this_week
    if remaining_needed <= 0:
        return False
    days_left_in_week = 7 - today.weekday()
    return remaining_needed >= days_left_in_week


def to_summary(habit: Habit, today: date) -> dict:
    completed_days = [c.day for c in habit.completions]
    skipped_days = [s.day for s in habit.skips]
    completed_this_week = count_completions_in_week(completed_days, today)
    completed_today = today in completed_days
    return {
        "id": habit.id,
        "name": habit.name,
        "category": habit.category,
        "priority": habit.priority,
        "target_per_week": habit.target_per_week,
        "notes": habit.notes,
        "archived": habit.archived,
        "pinned": habit.pinned,
        "completed_this_week": completed_this_week,
        "streak": compute_streak(completed_days, today, skipped_days),
        "longest_streak": compute_longest_streak(completed_days, skipped_days),
        "completed_today": completed_today,
        "completed_days": sorted(completed_days),
        "skipped_today": today in skipped_days,
        "skipped_days": sorted(skipped_days),
        "at_risk": is_at_risk(habit.target_per_week, completed_this_week, completed_today, today),
    }
