"""Business analytics computed from real database rows (no hardcoded numbers)."""
import re
from collections import Counter
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import serializers as ser
from ..database import get_db
from ..models import Appointment, Conversation, Customer, Lead, Message, SentimentRecord
from ..security import require_admin
from ..services.scheduling import now_local

router = APIRouter(prefix="/api/analytics", tags=["analytics"], dependencies=[Depends(require_admin)])

TOPICS = {
    "Pricing & fees": r"price|fee|cost|kitna|कीमत|फीस|₹|expensive|महंगा",
    "EMI & payment": r"\bemi\b|install|payment|pay\b|किश्त",
    "Batches & schedule": r"batch|start|schedule|timing|weekend|weekday|बैच",
    "Course content": r"syllabus|curriculum|learn|topics|course|program|कोर्स",
    "Refunds": r"refund|money back|रिफंड",
    "Placement & jobs": r"placement|job|salary|नौकरी",
    "Certificates": r"certificat|सर्टिफिकेट",
    "Discounts": r"discount|offer|scholarship|छूट",
    "Duration": r"duration|how long|months|weeks|अवधि",
}


@router.get("/overview")
def overview(days: int = 14, db: Session = Depends(get_db)):
    days = max(1, min(days, 90))
    engaged_ids = set(db.execute(select(Conversation.customer_id).join(Message)
                                 .where(Message.role == "user")).scalars())
    leads = db.execute(select(Lead).where(Lead.customer_id.in_(engaged_ids))).scalars().all() if engaged_ids else []
    convs_total = db.execute(select(func.count(Conversation.id))).scalar_one()
    engaged_convs = db.execute(select(func.count(func.distinct(Message.conversation_id)))
                               .where(Message.role == "user")).scalar_one()
    appts = db.execute(select(Appointment).where(Appointment.status.in_(["booked", "completed"]))).scalars().all()
    conv_with_appt = len({a.conversation_id for a in appts if a.conversation_id})
    cats = Counter(l.category for l in leads)
    sentiments = Counter(db.execute(select(SentimentRecord.label)).scalars())
    objections = Counter(o for objs in db.execute(select(SentimentRecord.objections)).scalars() for o in (objs or []))
    interests = Counter(l.interest for l in leads if l.interest)

    user_texts = db.execute(select(Message.content).where(Message.role == "user")).scalars().all()
    topics = Counter()
    for t in user_texts:
        if "?" in t or re.search(r"\b(what|how|when|tell|price|fee|kitna|क्या|कितना)\b", t, re.I):
            for name, pat in TOPICS.items():
                if re.search(pat, t, re.I):
                    topics[name] += 1

    # daily trend
    start = (datetime.utcnow() - timedelta(days=days - 1)).date()
    daily = {(start + timedelta(days=i)).isoformat(): {"conversations": 0, "leads": 0, "appointments": 0}
             for i in range(days)}
    for (d,) in db.execute(select(Conversation.started_at).where(Conversation.id.in_(
            select(Message.conversation_id).where(Message.role == "user")))):
        k = d.date().isoformat()
        if k in daily:
            daily[k]["conversations"] += 1
    for l in leads:
        k = l.created_at.date().isoformat()
        if k in daily:
            daily[k]["leads"] += 1
    for a in appts:
        k = a.created_at.date().isoformat()
        if k in daily:
            daily[k]["appointments"] += 1
    weekly = Counter()
    for (d,) in db.execute(select(Conversation.started_at)):
        y, w, _ = d.isocalendar()
        weekly[f"{y}-W{w:02d}"] += 1

    upcoming = db.execute(select(Appointment).where(Appointment.status == "booked",
                                                    Appointment.start_time >= now_local())
                          .order_by(Appointment.start_time).limit(5)).scalars()
    recent_convs = db.execute(select(Conversation).where(Conversation.id.in_(
        select(Message.conversation_id).where(Message.role == "user")))
                              .order_by(Conversation.started_at.desc()).limit(6)).scalars()
    recent_leads = db.execute(select(Customer).join(Lead).where(Customer.id.in_(engaged_ids) if engaged_ids else False)
                              .order_by(Lead.updated_at.desc()).limit(6)).scalars()

    return {
        "totals": {
            "conversations": convs_total,
            "engaged_conversations": engaged_convs,
            "leads": len(leads),
            "hot": cats.get("HOT", 0), "warm": cats.get("WARM", 0), "cold": cats.get("COLD", 0),
            "appointments": len(appts),
            "appointment_conversion_rate": round(conv_with_appt / engaged_convs, 3) if engaged_convs else 0,
            "average_lead_score": round(sum(l.score for l in leads) / len(leads), 1) if leads else 0,
            "won": sum(1 for l in leads if l.status == "won"),
        },
        "lead_distribution": [{"category": c, "count": cats.get(c, 0)} for c in ("HOT", "WARM", "COLD")],
        "sentiment_distribution": [{"label": k, "count": v} for k, v in sentiments.most_common()],
        "top_questions": [{"topic": k, "count": v} for k, v in topics.most_common(8)],
        "top_objections": [{"objection": k, "count": v} for k, v in objections.most_common(6)],
        "popular_products": [{"product": k, "count": v} for k, v in interests.most_common(6)],
        "daily": [{"date": k, **v} for k, v in daily.items()],
        "weekly": [{"week": k, "conversations": v} for k, v in sorted(weekly.items())[-8:]],
        "upcoming_appointments": [ser.appointment(a) for a in upcoming],
        "recent_conversations": [ser.conversation(c) for c in recent_convs],
        "recent_leads": [{**ser.customer(c), "lead": ser.lead(c.lead)} for c in recent_leads],
    }
