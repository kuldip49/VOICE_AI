"""Convert ORM objects into JSON-friendly dicts for API responses."""
from .models import Appointment, CallSummary, Conversation, Customer, Lead, Message
from .services.scheduling import format_slot


def iso(dt):
    return dt.isoformat() if dt else None


def message(m: Message) -> dict:
    return {"id": m.id, "role": m.role, "content": m.content, "language": m.language, "intents": m.intents or [],
            "sources": m.sources or [], "generated_by": m.generated_by, "created_at": iso(m.created_at)}


def lead(l: Lead | None) -> dict | None:
    if not l:
        return None
    return {"id": l.id, "interest": l.interest, "budget": l.budget, "timeline": l.timeline, "authority": l.authority,
            "requirements": l.requirements, "intent_level": l.intent_level, "score": l.score, "category": l.category,
            "status": l.status, "score_breakdown": l.score_breakdown or {}, "score_reasons": l.score_reasons or [],
            "updated_at": iso(l.updated_at)}


def customer(c: Customer) -> dict:
    return {"id": c.id, "name": c.name, "email": c.email, "phone": c.phone, "language": c.language,
            "created_at": iso(c.created_at)}


def appointment(a: Appointment) -> dict:
    return {"id": a.id, "customer_id": a.customer_id, "customer_name": a.customer.name if a.customer else None,
            "conversation_id": a.conversation_id, "start_time": iso(a.start_time), "end_time": iso(a.end_time),
            "label": format_slot(a.start_time), "status": a.status, "topic": a.topic, "notes": a.notes,
            "created_at": iso(a.created_at)}


def summary(s: CallSummary | None) -> dict | None:
    if not s:
        return None
    return {"id": s.id, "conversation_id": s.conversation_id, "summary": s.summary, "requirements": s.requirements,
            "objections": s.objections, "interests": s.interests, "budget": s.budget,
            "purchase_intent": s.purchase_intent, "sentiment": s.sentiment, "lead_score": s.lead_score,
            "lead_category": s.lead_category, "follow_up_action": s.follow_up_action,
            "appointment_info": s.appointment_info, "generated_by": s.generated_by, "created_at": iso(s.created_at)}


def conversation(c: Conversation, with_messages: bool = False) -> dict:
    d = {"id": c.id, "customer_id": c.customer_id, "customer_name": c.customer.name if c.customer else None,
         "channel": c.channel, "language": c.language, "status": c.status, "started_at": iso(c.started_at),
         "ended_at": iso(c.ended_at), "message_count": len(c.messages),
         "lead_category": c.customer.lead.category if c.customer and c.customer.lead else None,
         "lead_score": c.customer.lead.score if c.customer and c.customer.lead else None,
         "state": {k: v for k, v in (c.state or {}).items() if k in ("offered_slots", "pending_slot", "awaiting")},
         "summary": summary(c.summary)}
    if with_messages:
        d["messages"] = [message(m) for m in c.messages]
    return d
