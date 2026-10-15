from datetime import date, timedelta

from app.models.habit import Completion, Skip
from app.services.habit_service import (
    compute_streak,
    count_completions_in_week,
    create_habit,
    is_at_risk,
    start_of_week,
    uncomplete_habit,
)


def test_streak_zero_when_no_completions():
    assert compute_streak([], date(2026, 1, 10)) == 0


def test_streak_counts_consecutive_days_including_today():
    today = date(2026, 1, 10)
    days = [today, today - timedelta(days=1), today - timedelta(days=2)]
    assert compute_streak(days, today) == 3


def test_streak_still_counts_if_yesterday_done_but_not_today_yet():
    today = date(2026, 1, 10)
    days = [today - timedelta(days=1), today - timedelta(days=2)]
    assert compute_streak(days, today) == 2


def test_streak_breaks_on_gap():
    today = date(2026, 1, 10)
    days = [today, today - timedelta(days=3)]
    assert compute_streak(days, today) == 1


def test_streak_zero_if_last_completion_older_than_yesterday():
    today = date(2026, 1, 10)
    days = [today - timedelta(days=2)]
    assert compute_streak(days, today) == 0


def test_skipped_day_pauses_the_streak_without_breaking_it():
    today = date(2026, 1, 10)
    days = [today, today - timedelta(days=2)]  # yesterday missing
    skipped = [today - timedelta(days=1)]  # yesterday frozen instead
    assert compute_streak(days, today, skipped) == 2


def test_skipped_day_does_not_itself_add_to_the_streak():
    today = date(2026, 1, 10)
    days = [today - timedelta(days=1)]
    skipped = [today]  # today frozen, not completed
    assert compute_streak(days, today, skipped) == 1


def test_a_gap_still_breaks_the_streak_even_with_skips_elsewhere():
    today = date(2026, 1, 10)
    days = [today, today - timedelta(days=3)]
    skipped = [today - timedelta(days=5)]  # too far back to bridge the gap
    assert compute_streak(days, today, skipped) == 1


def test_only_skips_with_no_completions_ever_is_zero_streak():
    today = date(2026, 1, 10)
    assert compute_streak([], today, [today, today - timedelta(days=1)]) == 0


def test_start_of_week_returns_monday():
    # 2026-01-10 is a Saturday.
    assert start_of_week(date(2026, 1, 10)) == date(2026, 1, 5)


def test_start_of_week_is_idempotent_on_monday():
    monday = date(2026, 1, 5)
    assert start_of_week(monday) == monday


def test_count_completions_in_week_only_counts_current_week():
    today = date(2026, 1, 10)  # Saturday, week starts Monday 2026-01-05
    days = [
        date(2026, 1, 5),
        date(2026, 1, 7),
        today,
        date(2026, 1, 4),  # last week, excluded
    ]
    assert count_completions_in_week(days, today) == 3


def test_count_completions_in_week_zero_when_no_completions_this_week():
    assert count_completions_in_week([date(2026, 1, 1)], date(2026, 1, 10)) == 0


def test_never_at_risk_once_completed_today():
    today = date(2026, 1, 10)  # Saturday
    assert is_at_risk(7, 0, True, today) is False


def test_not_at_risk_once_the_weekly_target_is_already_met():
    today = date(2026, 1, 10)  # Saturday
    assert is_at_risk(3, 3, False, today) is False


def test_at_risk_when_every_remaining_day_is_needed():
    today = date(2026, 1, 10)  # Saturday, 2 days left (Sat + Sun)
    # target 7, 5 done: needs both remaining days.
    assert is_at_risk(7, 5, False, today) is True


def test_not_at_risk_with_slack_left_in_the_week():
    today = date(2026, 1, 10)  # Saturday, 2 days left
    # target 7, 6 done: only needs 1 of the 2 remaining days.
    assert is_at_risk(7, 6, False, today) is False


def test_not_at_risk_early_in_the_week_even_if_behind():
    today = date(2026, 1, 5)  # Monday, 7 days left
    assert is_at_risk(3, 0, False, today) is False


def test_uncomplete_habit_deletes_only_the_given_days_completion(db_session):
    habit = create_habit(db_session, "Run")
    db_session.add(Completion(habit_id=habit.id, day=date(2026, 1, 5)))
    db_session.add(Completion(habit_id=habit.id, day=date(2026, 1, 6)))
    db_session.commit()

    result = uncomplete_habit(db_session, habit, date(2026, 1, 6))

    assert result is habit
    assert [c.day for c in habit.completions] == [date(2026, 1, 5)]


def test_uncomplete_habit_leaves_skips_and_is_a_no_op_without_a_completion(db_session):
    habit = create_habit(db_session, "Run")
    db_session.add(Skip(habit_id=habit.id, day=date(2026, 1, 6)))
    db_session.commit()

    uncomplete_habit(db_session, habit, date(2026, 1, 6))
    uncomplete_habit(db_session, habit, date(2026, 1, 6))

    assert db_session.query(Completion).filter_by(habit_id=habit.id).count() == 0
    assert (
        db_session.query(Skip).filter_by(habit_id=habit.id, day=date(2026, 1, 6)).first()
        is not None
    )
