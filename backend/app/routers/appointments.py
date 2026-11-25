"""Appointments: list, available slots, manual booking, cancel, reschedule."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import serializers as ser
from ..database import get_db
from ..models import Appointment, Customer
from ..security import require_admin
from ..services import scheduling

router = APIRouter(prefix="/api/appointments", tags=["appointments"])


@router.get("/slots")
def slots(date: str | None = None, limit: int = 40, db: Session = Depends(get_db)):
    s = scheduling.available_slots(db, limit=min(limit, 200), date=date)
    return [{"start_time": x.isoformat(), "label": scheduling.format_slot(x)} for x in s]


@router.get("", dependencies=[Depends(require_admin)])
def list_appointments(status: str | None = None, upcoming: bool = False, db: Session = Depends(get_db)):
    q = select(Appointment)
    if status:
        q = q.where(Appointment.status == status)
    if upcoming:
        q = q.where(Appointment.start_time >= scheduling.now_local(), Appointment.status == "booked")
    q = q.order_by(Appointment.start_time.asc() if upcoming else Appointment.start_time.desc())
    return [ser.appointment(a) for a in db.execute(q.limit(500)).scalars()]


class BookBody(BaseModel):
    customer_id: int = Field(gt=0)
    start_time: datetime
    topic: str = Field(default="Course counselling session", max_length=200)
    notes: str | None = Field(default=None, max_length=1000)


class RescheduleBody(BaseModel):
    start_time: datetime


def _err(e: scheduling.BookingError):
    code = 409 if e.code in ("slot_taken", "customer_has_appointment", "not_active") else \
        404 if e.code == "not_found" else 422
    return HTTPException(code, {"code": e.code, "message": str(e)})


@router.post("", dependencies=[Depends(require_admin)])
def book(body: BookBody, db: Session = Depends(get_db)):
    if not db.get(Customer, body.customer_id):
        raise HTTPException(404, "Customer not found")
    try:
        a = scheduling.book(db, customer_id=body.customer_id, start=body.start_time.replace(tzinfo=None),
                            topic=body.topic, notes=body.notes)
    except scheduling.BookingError as e:
        raise _err(e)
    return ser.appointment(a)


@router.post("/{appointment_id}/cancel", dependencies=[Depends(require_admin)])
def cancel(appointment_id: int, db: Session = Depends(get_db)):
    try:
        return ser.appointment(scheduling.cancel(db, appointment_id))
    except scheduling.BookingError as e:
        raise _err(e)


@router.post("/{appointment_id}/reschedule", dependencies=[Depends(require_admin)])
def reschedule(appointment_id: int, body: RescheduleBody, db: Session = Depends(get_db)):
    try:
        return ser.appointment(scheduling.reschedule(db, appointment_id, body.start_time.replace(tzinfo=None)))
    except scheduling.BookingError as e:
        raise _err(e)
