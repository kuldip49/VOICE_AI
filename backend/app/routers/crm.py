"""Built-in CRM: leads, customer profiles, memory inspection/deletion, CSV export."""
import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import serializers as ser
from ..database import get_db
from ..models import Customer, CustomerMemory, Lead, SentimentRecord
from ..security import require_admin
from ..services.lead_rescue import build_lead_rescue_brief

router = APIRouter(prefix="/api", tags=["crm"], dependencies=[Depends(require_admin)])


def _lead_row(c: Customer) -> dict:
    last_sent = None
    return {**ser.customer(c), "lead": ser.lead(c.lead), "conversation_count": len(c.conversations),
            "last_contact": ser.iso(max((cv.started_at for cv in c.conversations), default=None)),
            "upcoming_appointment": next((ser.appointment(a) for a in sorted(c.appointments, key=lambda a: a.start_time)
                                          if a.status == "booked"), None),
            "last_sentiment": last_sent}


@router.get("/leads")
def list_leads(q: str | None = None, category: str | None = None, status: str | None = None,
               sort: str = "recent", db: Session = Depends(get_db)):
    stmt = select(Customer).join(Lead)
    if q:
        like = f"%{q.strip()[:100]}%"
        stmt = stmt.where(or_(Customer.name.ilike(like), Customer.email.ilike(like), Customer.phone.ilike(like),
                              Lead.interest.ilike(like)))
    if category in ("HOT", "WARM", "COLD"):
        stmt = stmt.where(Lead.category == category)
    if status:
        stmt = stmt.where(Lead.status == status)
    stmt = stmt.order_by(Lead.score.desc() if sort == "score" else Lead.updated_at.desc())
    rows = db.execute(stmt.limit(500)).scalars().all()
    out = []
    for c in rows:
        if not c.conversations or all(len(cv.messages) <= 1 for cv in c.conversations):
            if not (c.name or c.email or c.phone):
                continue  # skip empty sessions (visitor opened the agent and said nothing)
        row = _lead_row(c)
        s = db.execute(select(SentimentRecord.label).where(SentimentRecord.customer_id == c.id)
                       .order_by(SentimentRecord.id.desc())).first()
        row["last_sentiment"] = s[0] if s else None
        out.append(row)
    return out


@router.get("/leads/export.csv")
def export_csv(db: Session = Depends(get_db)):
    rows = db.execute(select(Customer).join(Lead).order_by(Lead.score.desc())).scalars().all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["customer_id", "name", "email", "phone", "interest", "budget", "timeline", "score", "category",
                "status", "intent_level", "created_at"])
    for c in rows:
        l = c.lead
        w.writerow([c.id, c.name or "", c.email or "", c.phone or "", l.interest or "", l.budget or "",
                    l.timeline or "", l.score, l.category, l.status, l.intent_level, ser.iso(c.created_at)])
    return StreamingResponse(iter([buf.getvalue().encode("utf-8-sig")]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=salespilot-leads.csv"})


@router.get("/leads/{customer_id}")
def lead_detail(customer_id: int, db: Session = Depends(get_db)):
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(404, "Customer not found")
    sentiments = db.execute(select(SentimentRecord).where(SentimentRecord.customer_id == c.id)
                            .order_by(SentimentRecord.id.desc()).limit(50)).scalars()
    return {
        **_lead_row(c),
        "memories": [{"key": m.key, "value": m.value, "updated_at": ser.iso(m.updated_at)} for m in c.memories],
        "conversations": [ser.conversation(cv, with_messages=True)
                          for cv in sorted(c.conversations, key=lambda x: x.started_at, reverse=True)],
        "appointments": [ser.appointment(a) for a in sorted(c.appointments, key=lambda a: a.start_time, reverse=True)],
        "sentiments": [{"label": s.label, "confidence": s.confidence, "explanation": s.explanation,
                        "recommended_action": s.recommended_action, "objections": s.objections,
                        "created_at": ser.iso(s.created_at)} for s in sentiments],
    }


@router.post("/leads/{customer_id}/rescue-brief")
def lead_rescue_brief(customer_id: int, db: Session = Depends(get_db)):
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(404, "Customer not found")
    if not customer.lead:
        raise HTTPException(404, "Lead not found")
    return build_lead_rescue_brief(db, customer)


class LeadPatch(BaseModel):
    status: str | None = Field(default=None, pattern=r"^(new|contacted|qualified|won|lost)$")
    name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=30)


@router.patch("/leads/{customer_id}")
def update_lead(customer_id: int, body: LeadPatch, db: Session = Depends(get_db)):
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(404, "Customer not found")
    if body.status:
        c.lead.status = body.status
    for f in ("name", "email", "phone"):
        v = getattr(body, f)
        if v is not None:
            setattr(c, f, v or None)
    db.commit()
    return _lead_row(c)


@router.delete("/leads/{customer_id}")
def delete_lead(customer_id: int, db: Session = Depends(get_db)):
    """Right-to-erasure: deletes the customer and ALL related data (cascade)."""
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(404, "Customer not found")
    db.delete(c)
    db.commit()
    return {"deleted": customer_id}


@router.delete("/customers/{customer_id}/memories")
def delete_memories(customer_id: int, key: str | None = None, db: Session = Depends(get_db)):
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(404, "Customer not found")
    q = select(CustomerMemory).where(CustomerMemory.customer_id == customer_id)
    if key:
        q = q.where(CustomerMemory.key == key)
    n = 0
    for m in db.execute(q).scalars():
        db.delete(m)
        n += 1
    db.commit()
    return {"deleted": n}
