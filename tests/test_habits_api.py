from datetime import date, timedelta

from app.models.habit import Completion


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_list_habits_empty(client):
    resp = client.get("/habits")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_habit(client):
    resp = client.post("/habits", json={"name": "Drink water"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Drink water"
    assert body["category"] == "General"
    assert body["target_per_week"] == 7
    assert body["completed_this_week"] == 0
    assert body["streak"] == 0
    assert body["completed_today"] is False
    assert body["completed_days"] == []


def test_create_habit_with_explicit_target_per_week(client):
    resp = client.post("/habits", json={"name": "Run", "target_per_week": 3})
    assert resp.status_code == 201
    assert resp.json()["target_per_week"] == 3


def test_create_habit_rejects_target_per_week_out_of_range(client):
    assert client.post("/habits", json={"name": "Run", "target_per_week": 0}).status_code == 422
    assert client.post("/habits", json={"name": "Run", "target_per_week": 8}).status_code == 422


def test_complete_habit_updates_completed_this_week(client):
    created = client.post("/habits", json={"name": "Run", "target_per_week": 3}).json()
    resp = client.post(f"/habits/{created['id']}/complete")
    assert resp.json()["completed_this_week"] == 1


def test_create_habit_with_explicit_category(client):
    resp = client.post("/habits", json={"name": "Run 5k", "category": "Health"})
    assert resp.status_code == 201
    assert resp.json()["category"] == "Health"


def test_create_habit_rejects_empty_name(client):
    resp = client.post("/habits", json={"name": ""})
    assert resp.status_code == 422


def test_create_habit_rejects_empty_category(client):
    resp = client.post("/habits", json={"name": "Read", "category": ""})
    assert resp.status_code == 422


def test_complete_habit_marks_today_and_bumps_streak(client):
    created = client.post("/habits", json={"name": "Read"}).json()
    resp = client.post(f"/habits/{created['id']}/complete")
    assert resp.status_code == 200
    body = resp.json()
    assert body["completed_today"] is True
    assert body["streak"] == 1


def test_complete_habit_is_idempotent_same_day(client):
    created = client.post("/habits", json={"name": "Read"}).json()
    client.post(f"/habits/{created['id']}/complete")
    resp = client.post(f"/habits/{created['id']}/complete")
    assert resp.status_code == 200
    assert resp.json()["streak"] == 1


def test_complete_unknown_habit_404s(client):
    resp = client.post("/habits/999/complete")
    assert resp.status_code == 404


def test_list_habits_reflects_completion(client):
    created = client.post("/habits", json={"name": "Meditate"}).json()
    client.post(f"/habits/{created['id']}/complete")
    resp = client.get("/habits")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["completed_today"] is True


def test_delete_habit(client):
    created = client.post("/habits", json={"name": "Stretch"}).json()
    resp = client.delete(f"/habits/{created['id']}")
    assert resp.status_code == 204
    assert client.get("/habits").json() == []


def test_delete_unknown_habit_404s(client):
    resp = client.delete("/habits/999")
    assert resp.status_code == 404


def test_list_habits_filters_by_category(client):
    client.post("/habits", json={"name": "Run 5k", "category": "Health"})
    client.post("/habits", json={"name": "Read", "category": "Learning"})

    resp = client.get("/habits", params={"category": "Health"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["name"] == "Run 5k"


def test_list_categories_returns_distinct_sorted_categories(client):
    client.post("/habits", json={"name": "Run 5k", "category": "Health"})
    client.post("/habits", json={"name": "Stretch", "category": "Health"})
    client.post("/habits", json={"name": "Read", "category": "Learning"})

    resp = client.get("/habits/categories")
    assert resp.status_code == 200
    assert resp.json() == ["Health", "Learning"]


def test_list_categories_empty_when_no_habits(client):
    resp = client.get("/habits/categories")
    assert resp.status_code == 200
    assert resp.json() == []


def test_stats_empty_when_no_habits(client):
    resp = client.get("/habits/stats")
    assert resp.status_code == 200
    assert resp.json() == {
        "total_habits": 0,
        "completed_today": 0,
        "skipped_today": 0,
        "active_streaks": 0,
        "best_streak": 0,
        "total_completions": 0,
        "weekly_completion_rate": 0,
        "pinned_count": 0,
        "by_category": {},
        "by_priority": {},
    }


def test_stats_counts_habits_and_categories(client):
    client.post("/habits", json={"name": "Run 5k", "category": "Health"})
    client.post("/habits", json={"name": "Stretch", "category": "Health"})
    client.post("/habits", json={"name": "Read", "category": "Learning"})

    body = client.get("/habits/stats").json()

    assert body["total_habits"] == 3
    assert body["by_category"] == {"Health": 2, "Learning": 1}


def test_stats_reflects_completions_and_streaks(client):
    created = client.post("/habits", json={"name": "Run", "target_per_week": 2}).json()
    client.post(f"/habits/{created['id']}/complete")

    body = client.get("/habits/stats").json()

    assert body["completed_today"] == 1
    assert body["active_streaks"] == 1
    assert body["best_streak"] == 1
    assert body["total_completions"] == 1


def test_stats_weekly_completion_rate_is_a_percentage_of_targets(client):
    first = client.post("/habits", json={"name": "Run", "target_per_week": 2}).json()
    client.post("/habits", json={"name": "Read", "target_per_week": 2})
    client.post(f"/habits/{first['id']}/complete")

    body = client.get("/habits/stats").json()

    # 1 completion this week against a combined weekly target of 4.
    assert body["weekly_completion_rate"] == 25


def test_update_habit_renames(client):
    created = client.post("/habits", json={"name": "Run"}).json()
    resp = client.patch(f"/habits/{created['id']}", json={"name": "Run 5k"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Run 5k"


def test_update_habit_changes_category_and_target(client):
    created = client.post("/habits", json={"name": "Run"}).json()
    resp = client.patch(
        f"/habits/{created['id']}", json={"category": "Health", "target_per_week": 4}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["category"] == "Health"
    assert body["target_per_week"] == 4


def test_update_habit_partial_leaves_other_fields_unchanged(client):
    created = client.post(
        "/habits", json={"name": "Run", "category": "Health", "target_per_week": 5}
    ).json()
    resp = client.patch(f"/habits/{created['id']}", json={"name": "Run fast"})
    body = resp.json()
    assert body["name"] == "Run fast"
    assert body["category"] == "Health"
    assert body["target_per_week"] == 5


def test_update_habit_preserves_completions_and_streak(client):
    created = client.post("/habits", json={"name": "Run"}).json()
    client.post(f"/habits/{created['id']}/complete")
    resp = client.patch(f"/habits/{created['id']}", json={"name": "Run fast"})
    body = resp.json()
    assert body["completed_today"] is True
    assert body["streak"] == 1


def test_update_habit_404_when_missing(client):
    resp = client.patch("/habits/999", json={"name": "Whatever"})
    assert resp.status_code == 404


def test_update_habit_rejects_empty_name(client):
    created = client.post("/habits", json={"name": "Run"}).json()
    resp = client.patch(f"/habits/{created['id']}", json={"name": ""})
    assert resp.status_code == 422


def test_update_habit_rejects_target_per_week_out_of_range(client):
    created = client.post("/habits", json={"name": "Run"}).json()
    resp = client.patch(f"/habits/{created['id']}", json={"target_per_week": 8})
    assert resp.status_code == 422


def test_at_risk_field_is_present_on_a_freshly_created_habit(client):
    # Whether a brand-new habit is at risk depends on today's weekday (the
    # exact rule is covered deterministically in test_habit_service.py), so
    # this only checks the field is wired through, not a specific value.
    created = client.post("/habits", json={"name": "Run", "target_per_week": 1}).json()
    assert "at_risk" in created
    assert isinstance(created["at_risk"], bool)


def test_at_risk_is_false_once_completed_today_even_for_a_daily_habit(client):
    created = client.post("/habits", json={"name": "Run", "target_per_week": 7}).json()
    resp = client.post(f"/habits/{created['id']}/complete")
    assert resp.json()["at_risk"] is False


def test_skip_habit_marks_today_frozen(client):
    created = client.post("/habits", json={"name": "Run"}).json()
    resp = client.post(f"/habits/{created['id']}/skip")
    assert resp.status_code == 200
    body = resp.json()
    assert body["skipped_today"] is True
    assert body["completed_today"] is False


def test_skip_habit_is_idempotent_same_day(client):
    created = client.post("/habits", json={"name": "Run"}).json()
    client.post(f"/habits/{created['id']}/skip")
    resp = client.post(f"/habits/{created['id']}/skip")
    assert resp.status_code == 200
    assert resp.json()["skipped_days"] == [str(date.today())]


def test_skip_unknown_habit_404s(client):
    resp = client.post("/habits/999/skip")
    assert resp.status_code == 404


def test_skip_already_completed_habit_conflicts(client):
    created = client.post("/habits", json={"name": "Run"}).json()
    client.post(f"/habits/{created['id']}/complete")
    resp = client.post(f"/habits/{created['id']}/skip")
    assert resp.status_code == 409


def test_completing_a_skipped_day_overrides_the_freeze(client):
    created = client.post("/habits", json={"name": "Run"}).json()
    client.post(f"/habits/{created['id']}/skip")
    resp = client.post(f"/habits/{created['id']}/complete")
    assert resp.status_code == 200
    body = resp.json()
    assert body["completed_today"] is True
    assert body["skipped_today"] is False


def test_unskip_habit_removes_the_freeze(client):
    created = client.post("/habits", json={"name": "Run"}).json()
    client.post(f"/habits/{created['id']}/skip")
    resp = client.delete(f"/habits/{created['id']}/skip")
    assert resp.status_code == 200
    assert resp.json()["skipped_today"] is False


def test_unskip_habit_is_idempotent(client):
    created = client.post("/habits", json={"name": "Run"}).json()
    resp = client.delete(f"/habits/{created['id']}/skip")
    assert resp.status_code == 200
    assert resp.json()["skipped_today"] is False


def test_unskip_unknown_habit_404s(client):
    resp = client.delete("/habits/999/skip")
    assert resp.status_code == 404


def test_uncomplete_habit_removes_today_completion(client):
    created = client.post("/habits", json={"name": "Read"}).json()
    client.post(f"/habits/{created['id']}/complete")
    resp = client.delete(f"/habits/{created['id']}/complete")
    assert resp.status_code == 200
    body = resp.json()
    assert body["completed_today"] is False
    assert str(date.today()) not in body["completed_days"]
    assert body["streak"] == 0


def test_uncomplete_habit_is_idempotent(client):
    created = client.post("/habits", json={"name": "Read"}).json()
    before = next(h for h in client.get("/habits").json() if h["id"] == created["id"])
    resp = client.delete(f"/habits/{created['id']}/complete")
    assert resp.status_code == 200
    assert resp.json() == before


def test_uncomplete_unknown_habit_404s(client):
    resp = client.delete("/habits/999/complete")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Habit not found"}


def test_uncomplete_then_complete_again(client):
    created = client.post("/habits", json={"name": "Read"}).json()
    client.post(f"/habits/{created['id']}/complete")
    client.delete(f"/habits/{created['id']}/complete")
    resp = client.post(f"/habits/{created['id']}/complete")
    assert resp.status_code == 200
    body = resp.json()
    assert body["completed_today"] is True
    assert body["streak"] == 1


def test_uncomplete_keeps_streak_anchored_on_yesterday(client, db_session):
    created = client.post("/habits", json={"name": "Read"}).json()
    db_session.add(
        Completion(habit_id=created["id"], day=date.today() - timedelta(days=1))
    )
    db_session.commit()
    assert client.post(f"/habits/{created['id']}/complete").json()["streak"] == 2
    resp = client.delete(f"/habits/{created['id']}/complete")
    assert resp.status_code == 200
    body = resp.json()
    assert body["streak"] == 1
    assert body["longest_streak"] == 1


def test_uncomplete_decrements_completed_this_week(client):
    created = client.post("/habits", json={"name": "Read"}).json()
    done = client.post(f"/habits/{created['id']}/complete").json()
    assert done["completed_this_week"] == 1
    resp = client.delete(f"/habits/{created['id']}/complete")
    assert resp.json()["completed_this_week"] == 0


def test_uncomplete_is_reflected_in_stats(client):
    created = client.post("/habits", json={"name": "Read"}).json()
    client.post(f"/habits/{created['id']}/complete")
    stats = client.get("/habits/stats").json()
    assert stats["completed_today"] == 1
    assert stats["total_completions"] == 1
    client.delete(f"/habits/{created['id']}/complete")
    stats = client.get("/habits/stats").json()
    assert stats["completed_today"] == 0
    assert stats["total_completions"] == 0


def test_uncomplete_after_freeze_then_complete_leaves_day_neither(client):
    created = client.post("/habits", json={"name": "Read"}).json()
    client.post(f"/habits/{created['id']}/skip")
    client.post(f"/habits/{created['id']}/complete")
    resp = client.delete(f"/habits/{created['id']}/complete")
    assert resp.status_code == 200
    body = resp.json()
    assert body["completed_today"] is False
    assert body["skipped_today"] is False
    assert body["skipped_days"] == []


def test_uncomplete_archived_habit_is_allowed(client):
    created = client.post("/habits", json={"name": "Read"}).json()
    client.post(f"/habits/{created['id']}/complete")
    client.patch(f"/habits/{created['id']}", json={"archived": True})
    resp = client.delete(f"/habits/{created['id']}/complete")
    assert resp.status_code == 200
    assert resp.json()["completed_today"] is False


def test_uncomplete_only_affects_the_given_habit(client):
    first = client.post("/habits", json={"name": "Read"}).json()
    second = client.post("/habits", json={"name": "Run"}).json()
    client.post(f"/habits/{first['id']}/complete")
    client.post(f"/habits/{second['id']}/complete")
    resp = client.delete(f"/habits/{second['id']}/complete")
    assert resp.status_code == 200
    assert resp.json()["completed_today"] is False
    habits = {h["id"]: h for h in client.get("/habits").json()}
    assert habits[second["id"]]["completed_today"] is False
    assert habits[first["id"]]["completed_today"] is True
    assert client.get("/habits/stats").json()["completed_today"] == 1


def test_stats_counts_skipped_today(client):
    created = client.post("/habits", json={"name": "Run"}).json()
    client.post(f"/habits/{created['id']}/skip")
    body = client.get("/habits/stats").json()
    assert body["skipped_today"] == 1
