"""Local appointment calendar (MVP) with a provider-adapter seam for Google Calendar later.

Double-booking protection happens at TWO levels:
  1. Application check inside the transaction (friendly error message).
  2. Database partial UNIQUE index on appointments(start_time) WHERE status='booked'
     -> even two simultaneous requests cannot both commit the same slot.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Appointment
from .settings_store import get_setting


class BookingError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def now_local() -> datetime:
    return datetime.now(ZoneInfo(get_settings().timezone)).replace(tzinfo=None, second=0, microsecond=0)


def format_slot(dt: datetime, lang: str = "en") -> str:
    if lang == "hi":
        days = ["सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"]
        return f"{days[dt.weekday()]}, {dt.day} {dt.strftime('%b')}, {dt.strftime('%I:%M %p').lstrip('0')}"
    return dt.strftime("%a %d %b, ") + dt.strftime("%I:%M %p").lstrip("0")


def _grid(db: Session, start_from: datetime | None = None) -> list[datetime]:
    cfg = get_setting(db, "scheduling")
    now = start_from or now_local()
    earliest = now + timedelta(minutes=cfg["min_notice_minutes"])
    out = []
    for d in range(cfg["days_ahead"] + 1):
        day = (now + timedelta(days=d)).date()
        if day.weekday() not in cfg["working_days"]:
            continue
        t = datetime(day.year, day.month, day.day, cfg["start_hour"], 0)
        end = datetime(day.year, day.month, day.day, cfg["end_hour"], 0)
        while t + timedelta(minutes=cfg["slot_minutes"]) <= end:
            if t >= earliest:
                out.append(t)
            t += timedelta(minutes=cfg["slot_minutes"])
    return out


def available_slots(db: Session, limit: int | None = None, date: str | None = None) -> list[datetime]:
    booked = set(db.execute(select(Appointment.start_time).where(Appointment.status == "booked",
                                                                  Appointment.start_time >= now_local())).scalars())
    slots = [s for s in _grid(db) if s not in booked]
    if date:
        slots = [s for s in slots if s.date().isoformat() == date]
    return slots[:limit] if limit else slots


def _validate_slot(db: Session, start: datetime) -> None:
    if start not in set(_grid(db)):
        raise BookingError("invalid_slot", "That time is not a valid appointment slot (outside working hours, "
                                           "in the past, or not on the slot grid).")


def book(db: Session, *, customer_id: int, start: datetime, conversation_id: str | None = None,
         topic: str = "Course counselling session", notes: str | None = None) -> Appointment:
    cfg = get_setting(db, "scheduling")
    start = start.replace(second=0, microsecond=0)
    _validate_slot(db, start)
    existing = db.execute(select(Appointment).where(Appointment.customer_id == customer_id,
                                                    Appointment.status == "booked",
                                                    Appointment.start_time >= now_local())).scalar_one_or_none()
    if existing:
        raise BookingError("customer_has_appointment",
                           f"Customer already has an upcoming appointment on {format_slot(existing.start_time)} "
                           f"(id {existing.id}). Reschedule or cancel it instead.")
    if db.execute(select(Appointment.id).where(Appointment.start_time == start,
                                               Appointment.status == "booked")).first():
        raise BookingError("slot_taken", "That slot was just booked by someone else.")
    appt = Appointment(customer_id=customer_id, conversation_id=conversation_id, start_time=start,
                       end_time=start + timedelta(minutes=cfg["slot_minutes"]), topic=topic, notes=notes)
    db.add(appt)
    try:
        db.commit()  # transaction boundary; unique index enforces no double booking
    except IntegrityError:
        db.rollback()
        raise BookingError("slot_taken", "That slot was just booked by someone else.")
    calendar_adapter().on_booked(appt)
    return appt


def cancel(db: Session, appointment_id: int) -> Appointment:
    appt = db.get(Appointment, appointment_id)
    if not appt:
        raise BookingError("not_found", "Appointment not found.")
    if appt.status != "booked":
        raise BookingError("not_active", f"Appointment is already {appt.status}.")
    appt.status = "cancelled"
    db.commit()
    calendar_adapter().on_cancelled(appt)
    return appt


def reschedule(db: Session, appointment_id: int, new_start: datetime) -> Appointment:
    cfg = get_setting(db, "scheduling")
    appt = db.get(Appointment, appointment_id)
    if not appt:
        raise BookingError("not_found", "Appointment not found.")
    if appt.status != "booked":
        raise BookingError("not_active", f"Appointment is {appt.status}; only booked appointments can move.")
    new_start = new_start.replace(second=0, microsecond=0)
    _validate_slot(db, new_start)
    clash = db.execute(select(Appointment.id).where(Appointment.start_time == new_start, Appointment.status == "booked",
                                                    Appointment.id != appt.id)).first()
    if clash:
        raise BookingError("slot_taken", "That slot is already booked.")
    appt.start_time = new_start
    appt.end_time = new_start + timedelta(minutes=cfg["slot_minutes"])
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise BookingError("slot_taken", "That slot is already booked.")
    return appt


# ---------------------------------------------------------------- calendar provider adapter
class CalendarAdapter(Protocol):
    name: str

    def on_booked(self, appt: Appointment) -> None: ...

    def on_cancelled(self, appt: Appointment) -> None: ...


class LocalCalendarAdapter:
    """MVP: the application database IS the calendar. A GoogleCalendarAdapter would implement the same
    two methods using the Google Calendar API (NOT implemented / NOT claimed)."""
    name = "local-database"

    def on_booked(self, appt: Appointment) -> None:
        return None

    def on_cancelled(self, appt: Appointment) -> None:
        return None


def calendar_adapter() -> CalendarAdapter:
    return LocalCalendarAdapter()
