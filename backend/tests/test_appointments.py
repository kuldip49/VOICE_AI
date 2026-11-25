"""Appointment booking, duplicate prevention, cancel/reschedule, tool confirmation."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.agent.tools import ToolContext, execute_tool
from app.models import Appointment, Customer, Lead
from app.services import scheduling


def _customer(db, name="Asha"):
    c = Customer(name=name)
    c.lead = Lead()
    db.add(c)
    db.commit()
    return c


def test_slots_are_future_and_on_grid(db):
    slots = scheduling.available_slots(db)
    assert slots
    now = scheduling.now_local()
    assert all(s > now and s.minute in (0, 30) and 10 <= s.hour < 18 and s.weekday() != 6 for s in slots)


def test_book_and_slot_disappears(db):
    c = _customer(db)
    slot = scheduling.available_slots(db)[0]
    a = scheduling.book(db, customer_id=c.id, start=slot)
    assert a.id and a.status == "booked" and a.end_time - a.start_time == timedelta(minutes=30)
    assert slot not in scheduling.available_slots(db)


def test_duplicate_slot_rejected(db):
    c1, c2 = _customer(db, "A"), _customer(db, "B")
    slot = scheduling.available_slots(db)[0]
    scheduling.book(db, customer_id=c1.id, start=slot)
    with pytest.raises(scheduling.BookingError) as e:
        scheduling.book(db, customer_id=c2.id, start=slot)
    assert e.value.code == "slot_taken"


def test_database_unique_index_blocks_race(db):
    """Even if the application check is bypassed (two concurrent requests), the DB refuses."""
    c1, c2 = _customer(db, "A"), _customer(db, "B")
    slot = scheduling.available_slots(db)[0]
    db.add(Appointment(customer_id=c1.id, start_time=slot, end_time=slot + timedelta(minutes=30)))
    db.commit()
    db.add(Appointment(customer_id=c2.id, start_time=slot, end_time=slot + timedelta(minutes=30)))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_customer_cannot_double_book(db):
    c = _customer(db)
    s1, s2 = scheduling.available_slots(db)[:2]
    scheduling.book(db, customer_id=c.id, start=s1)
    with pytest.raises(scheduling.BookingError) as e:
        scheduling.book(db, customer_id=c.id, start=s2)
    assert e.value.code == "customer_has_appointment"


def test_invalid_slots_rejected(db):
    c = _customer(db)
    tomorrow = scheduling.now_local() + timedelta(days=1)
    for bad in [datetime(2020, 1, 1, 10, 0), tomorrow.replace(hour=3, minute=0), tomorrow.replace(hour=11, minute=7)]:
        with pytest.raises(scheduling.BookingError) as e:
            scheduling.book(db, customer_id=c.id, start=bad)
        assert e.value.code == "invalid_slot"


def test_cancel_frees_slot_and_reschedule(db):
    c = _customer(db)
    s1, s2 = scheduling.available_slots(db)[:2]
    a = scheduling.book(db, customer_id=c.id, start=s1)
    a = scheduling.reschedule(db, a.id, s2)
    assert a.start_time == s2 and s1 in scheduling.available_slots(db)
    scheduling.cancel(db, a.id)
    assert s2 in scheduling.available_slots(db)
    with pytest.raises(scheduling.BookingError):
        scheduling.cancel(db, a.id)  # already cancelled


def test_book_tool_requires_confirmation(db):
    c = _customer(db)
    slot = scheduling.available_slots(db)[0].isoformat()
    ctx = ToolContext(db=db)
    r = execute_tool(ctx, "book_appointment", {"customer_id": c.id, "start_time": slot})
    assert not r["ok"] and r["error"]["code"] == "confirmation_required"
    assert db.query(Appointment).count() == 0
    r = execute_tool(ctx, "book_appointment", {"customer_id": c.id, "start_time": slot, "confirmed": True})
    assert r["ok"] and r["data"]["appointment_id"]


def test_appointments_api(client, db):
    c = _customer(db)
    slots = client.get("/api/appointments/slots").json()
    r = client.post("/api/appointments", json={"customer_id": c.id, "start_time": slots[0]["start_time"]})
    assert r.status_code == 200
    r2 = client.post("/api/appointments", json={"customer_id": _customer(db, "Z").id,
                                                 "start_time": slots[0]["start_time"]})
    assert r2.status_code == 409 and r2.json()["detail"]["code"] == "slot_taken"
    up = client.get("/api/appointments?upcoming=true").json()
    assert len(up) == 1 and up[0]["customer_name"] == "Asha"
    assert client.post(f"/api/appointments/{up[0]['id']}/cancel").json()["status"] == "cancelled"
