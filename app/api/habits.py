from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import HabitCreate, HabitOut, HabitStats, HabitUpdate
from app.services import habit_service

router = APIRouter(prefix="/habits", tags=["habits"])


@router.get("", response_model=list[HabitOut])
def list_habits(
    category: str | None = None,
    include_archived: bool = False,
    priority: str | None = None,
    db: Session = Depends(get_db),
):
    today = date.today()
    habits = habit_service.list_habits(
        db, category=category, include_archived=include_archived, priority=priority
    )
    return [habit_service.to_summary(h, today) for h in habits]


@router.get("/categories", response_model=list[str])
def list_categories(db: Session = Depends(get_db)):
    return habit_service.list_categories(db)


@router.get("/stats", response_model=HabitStats)
def get_stats(db: Session = Depends(get_db)):
    return habit_service.get_stats(db, date.today())


@router.post("", response_model=HabitOut, status_code=201)
def create_habit(payload: HabitCreate, db: Session = Depends(get_db)):
    habit = habit_service.create_habit(
        db,
        payload.name,
        payload.category,
        payload.target_per_week,
        payload.notes,
        payload.priority,
    )
    return habit_service.to_summary(habit, date.today())


@router.post("/{habit_id}/complete", response_model=HabitOut)
def complete_habit(habit_id: int, db: Session = Depends(get_db)):
    habit = habit_service.get_habit(db, habit_id)
    if habit is None:
        raise HTTPException(status_code=404, detail="Habit not found")
    today = date.today()
    habit_service.complete_habit(db, habit, today)
    return habit_service.to_summary(habit, today)


@router.delete("/{habit_id}/complete", response_model=HabitOut)
def uncomplete_habit(habit_id: int, db: Session = Depends(get_db)):
    habit = habit_service.get_habit(db, habit_id)
    if habit is None:
        raise HTTPException(status_code=404, detail="Habit not found")
    today = date.today()
    habit_service.uncomplete_habit(db, habit, today)
    return habit_service.to_summary(habit, today)


@router.post("/{habit_id}/skip", response_model=HabitOut)
def skip_habit(habit_id: int, db: Session = Depends(get_db)):
    habit = habit_service.get_habit(db, habit_id)
    if habit is None:
        raise HTTPException(status_code=404, detail="Habit not found")
    today = date.today()
    try:
        habit_service.skip_habit(db, habit, today)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return habit_service.to_summary(habit, today)


@router.delete("/{habit_id}/skip", response_model=HabitOut)
def unskip_habit(habit_id: int, db: Session = Depends(get_db)):
    habit = habit_service.get_habit(db, habit_id)
    if habit is None:
        raise HTTPException(status_code=404, detail="Habit not found")
    today = date.today()
    habit_service.unskip_habit(db, habit, today)
    return habit_service.to_summary(habit, today)


@router.patch("/{habit_id}", response_model=HabitOut)
def update_habit(habit_id: int, payload: HabitUpdate, db: Session = Depends(get_db)):
    habit = habit_service.get_habit(db, habit_id)
    if habit is None:
        raise HTTPException(status_code=404, detail="Habit not found")
    habit_service.update_habit(
        db,
        habit,
        payload.name,
        payload.category,
        payload.target_per_week,
        payload.notes,
        payload.archived,
        payload.priority,
        payload.pinned,
    )
    return habit_service.to_summary(habit, date.today())


@router.delete("/{habit_id}", status_code=204)
def delete_habit(habit_id: int, db: Session = Depends(get_db)):
    habit = habit_service.get_habit(db, habit_id)
    if habit is None:
        raise HTTPException(status_code=404, detail="Habit not found")
    habit_service.delete_habit(db, habit)
