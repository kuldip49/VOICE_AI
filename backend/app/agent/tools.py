"""Agent tools: the ONLY operations the AI agent can perform.

Security model:
  * Each tool has a Pydantic input schema -> arguments are validated on the backend.
  * Tools call ORM functions only. No raw SQL, shell or code execution is reachable.
  * Every call is logged to agent_tool_logs (input, output, success, duration).
  * book_appointment refuses to commit unless confirmed=True (customer confirmation).
  * Tools only return what actually happened in the database; failures are returned as errors.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from pydantic import BaseModel, EmailStr, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (AgentToolLog, Appointment, Conversation, Customer, CustomerMemory, Lead, SentimentRecord)
from ..services import rag, scheduling, scoring, sentiment, summary
from ..services.settings_store import get_setting


@dataclass
class ToolContext:
    db: Session
    conversation: Conversation | None = None
    embed_fn: Callable | None = None


class ToolError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------- input schemas
class SearchKBIn(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=3, ge=1, le=5)


class CustomerIn(BaseModel):
    customer_id: int = Field(gt=0)


class UpdateProfileIn(BaseModel):
    customer_id: int = Field(gt=0)
    name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, pattern=r"^\+?\d{10,13}$")
    budget: int | None = Field(default=None, ge=0, le=10_000_000)
    interest: str | None = Field(default=None, max_length=200)
    timeline: str | None = Field(default=None, max_length=100)
    authority: str | None = Field(default=None, max_length=100)
    requirements: list[str] = Field(default_factory=list, max_length=20)
    source_message_id: int | None = None


class SentimentIn(BaseModel):
    message_id: int = Field(gt=0)
    text: str = Field(min_length=1, max_length=4000)


class SlotsIn(BaseModel):
    limit: int = Field(default=4, ge=1, le=20)
    date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class BookIn(BaseModel):
    customer_id: int = Field(gt=0)
    start_time: datetime
    confirmed: bool = False
    topic: str = Field(default="Course counselling session", max_length=200)

    @field_validator("start_time")
    @classmethod
    def strip_tz(cls, v: datetime) -> datetime:
        return v.replace(tzinfo=None)


class CancelIn(BaseModel):
    appointment_id: int = Field(gt=0)
    customer_id: int = Field(gt=0)


class SummaryIn(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=36)


class CrmIn(BaseModel):
    customer_id: int = Field(gt=0)
    status: str | None = Field(default=None, pattern=r"^(new|contacted|qualified|won|lost)$")
    intent_level: str | None = Field(default=None, pattern=r"^(low|medium|high|unknown)$")


# ---------------------------------------------------------------- implementations
def _lead(db: Session, customer_id: int) -> Lead:
    customer = db.get(Customer, customer_id)
    if not customer:
        raise ToolError("unknown_customer", f"Customer {customer_id} does not exist")
    if not customer.lead:
        customer.lead = Lead()
        db.flush()
    return customer.lead


def t_search_knowledge_base(ctx: ToolContext, a: SearchKBIn) -> dict:
    res = rag.retrieve(ctx.db, a.query, a.top_k, embed_fn=ctx.embed_fn)
    return {"found": res["found"], "method": res["method"], "top_score": res.get("top_score"),
            "chunks": [c.as_source() | {"content": c.content} for c in res["chunks"]]}


def t_retrieve_customer_profile(ctx: ToolContext, a: CustomerIn) -> dict:
    c = ctx.db.get(Customer, a.customer_id)
    if not c:
        raise ToolError("unknown_customer", f"Customer {a.customer_id} does not exist")
    lead = c.lead
    return {
        "customer": {"id": c.id, "name": c.name, "email": c.email, "phone": c.phone, "language": c.language},
        "lead": None if not lead else {"interest": lead.interest, "budget": lead.budget, "timeline": lead.timeline,
                                       "authority": lead.authority, "requirements": lead.requirements,
                                       "score": lead.score, "category": lead.category,
                                       "intent_level": lead.intent_level, "status": lead.status},
        "memories": {m.key: m.value for m in c.memories},
        "upcoming_appointment": next(({"id": ap.id, "start_time": ap.start_time.isoformat()}
                                      for ap in c.appointments if ap.status == "booked"
                                      and ap.start_time >= scheduling.now_local()), None),
    }


def t_update_customer_profile(ctx: ToolContext, a: UpdateProfileIn) -> dict:
    db = ctx.db
    c = db.get(Customer, a.customer_id)
    if not c:
        raise ToolError("unknown_customer", f"Customer {a.customer_id} does not exist")
    lead = _lead(db, c.id)
    changed: dict[str, Any] = {}
    for f in ("name", "email", "phone"):
        v = getattr(a, f)
        if v and getattr(c, f) != v:
            setattr(c, f, str(v))
            changed[f] = str(v)
    for f in ("budget", "interest", "timeline", "authority"):
        v = getattr(a, f)
        if v and getattr(lead, f) != v:
            setattr(lead, f, v)
            changed[f] = v
    if a.requirements:
        existing = [r for r in (lead.requirements or "").split("; ") if r]
        merged = existing + [r for r in a.requirements if r not in existing]
        if merged != existing:
            lead.requirements = "; ".join(merged)
            changed["requirements"] = lead.requirements
    # persistent memory (key/value) for cross-conversation recall
    for k, v in changed.items():
        mem = db.execute(select(CustomerMemory).where(CustomerMemory.customer_id == c.id,
                                                      CustomerMemory.key == k)).scalar_one_or_none()
        if mem:
            mem.value = str(v)
            mem.source_message_id = a.source_message_id
        else:
            db.add(CustomerMemory(customer_id=c.id, key=k, value=str(v), source_message_id=a.source_message_id))
    db.commit()
    return {"changed": changed}


def t_qualify_lead(ctx: ToolContext, a: CustomerIn) -> dict:
    db = ctx.db
    lead = _lead(db, a.customer_id)
    c = lead.customer
    price = rag.find_product_price(db, lead.interest) if lead.interest else None
    has_appt = db.execute(select(Appointment.id).where(Appointment.customer_id == c.id,
                                                       Appointment.status == "booked")).first() is not None
    res = scoring.score_lead(intent_level=lead.intent_level, budget=lead.budget, product_price=price,
                             timeline=lead.timeline, interest=lead.interest, has_contact=bool(c.email or c.phone),
                             has_appointment=has_appt, config=get_setting(db, "lead_scoring"))
    lead.score, lead.category, lead.score_breakdown, lead.score_reasons = (res.score, res.category,
                                                                           res.breakdown, res.reasons)
    if lead.status == "new" and res.category in ("HOT", "WARM") and has_appt:
        lead.status = "qualified"
    db.commit()
    return {"score": res.score, "category": res.category, "breakdown": res.breakdown, "reasons": res.reasons,
            "product_price": price}


def t_analyze_sentiment(ctx: ToolContext, a: SentimentIn) -> dict:
    r = sentiment.analyze(a.text)
    if ctx.conversation is not None:
        ctx.db.add(SentimentRecord(message_id=a.message_id, conversation_id=ctx.conversation.id,
                                   customer_id=ctx.conversation.customer_id, label=r.label, confidence=r.confidence,
                                   explanation=r.explanation, recommended_action=r.recommended_action,
                                   objections=r.objections))
        ctx.db.commit()
    return {"label": r.label, "confidence": r.confidence, "explanation": r.explanation,
            "recommended_action": r.recommended_action, "objections": r.objections, "method": "lexicon-rules"}


def t_get_available_slots(ctx: ToolContext, a: SlotsIn) -> dict:
    slots = scheduling.available_slots(ctx.db, limit=a.limit, date=a.date)
    return {"slots": [s.isoformat() for s in slots], "count": len(slots)}


def t_book_appointment(ctx: ToolContext, a: BookIn) -> dict:
    if not a.confirmed:
        raise ToolError("confirmation_required", "Customer confirmation is required before booking.")
    if not ctx.db.get(Customer, a.customer_id):
        raise ToolError("unknown_customer", f"Customer {a.customer_id} does not exist")
    try:
        appt = scheduling.book(ctx.db, customer_id=a.customer_id, start=a.start_time, topic=a.topic,
                               conversation_id=ctx.conversation.id if ctx.conversation else None)
    except scheduling.BookingError as e:
        raise ToolError(e.code, str(e))
    return {"appointment_id": appt.id, "start_time": appt.start_time.isoformat(),
            "end_time": appt.end_time.isoformat(), "status": appt.status}


def t_cancel_appointment(ctx: ToolContext, a: CancelIn) -> dict:
    appt = ctx.db.get(Appointment, a.appointment_id)
    if not appt or appt.customer_id != a.customer_id:  # permission: only own appointments
        raise ToolError("not_found", "Appointment not found for this customer.")
    try:
        appt = scheduling.cancel(ctx.db, a.appointment_id)
    except scheduling.BookingError as e:
        raise ToolError(e.code, str(e))
    return {"appointment_id": appt.id, "status": appt.status}


def t_create_conversation_summary(ctx: ToolContext, a: SummaryIn) -> dict:
    conv = ctx.db.get(Conversation, a.conversation_id)
    if not conv:
        raise ToolError("not_found", "Conversation not found")
    s = summary.build_summary(ctx.db, conv)
    return {"summary_id": s.id, "summary": s.summary, "follow_up_action": s.follow_up_action,
            "sentiment": s.sentiment, "lead_score": s.lead_score, "generated_by": s.generated_by}


INTENT_RANK = {"unknown": 0, "low": 1, "medium": 2, "high": 3}


def t_update_crm_record(ctx: ToolContext, a: CrmIn) -> dict:
    lead = _lead(ctx.db, a.customer_id)
    changed = {}
    if a.status and a.status != lead.status:
        lead.status = a.status
        changed["status"] = a.status
    # intent only ratchets upwards within the agent (a later small-talk message does not lower intent)
    if a.intent_level and INTENT_RANK[a.intent_level] > INTENT_RANK.get(lead.intent_level, 0):
        lead.intent_level = a.intent_level
        changed["intent_level"] = a.intent_level
    ctx.db.commit()
    return {"changed": changed, "lead_id": lead.id}


TOOLS: dict[str, tuple[type[BaseModel], Callable]] = {
    "search_knowledge_base": (SearchKBIn, t_search_knowledge_base),
    "retrieve_customer_profile": (CustomerIn, t_retrieve_customer_profile),
    "update_customer_profile": (UpdateProfileIn, t_update_customer_profile),
    "qualify_lead": (CustomerIn, t_qualify_lead),
    "analyze_sentiment": (SentimentIn, t_analyze_sentiment),
    "get_available_slots": (SlotsIn, t_get_available_slots),
    "book_appointment": (BookIn, t_book_appointment),
    "cancel_appointment": (CancelIn, t_cancel_appointment),
    "create_conversation_summary": (SummaryIn, t_create_conversation_summary),
    "update_crm_record": (CrmIn, t_update_crm_record),
}

# Controlled permissions: which tools the live sales agent may call.
AGENT_ALLOWED = set(TOOLS)


def execute_tool(ctx: ToolContext, name: str, args: dict, allowed: set[str] = AGENT_ALLOWED) -> dict:
    """Validate + run + log a tool call. Returns {"ok": bool, "data"| "error": ...}."""
    started = time.perf_counter()
    result: dict
    if name not in TOOLS or name not in allowed:
        result = {"ok": False, "error": {"code": "tool_not_allowed", "message": f"Tool '{name}' is not permitted"}}
    else:
        schema, fn = TOOLS[name]
        try:
            parsed = schema.model_validate(args)
            result = {"ok": True, "data": fn(ctx, parsed)}
        except ValidationError as e:
            result = {"ok": False, "error": {"code": "invalid_arguments",
                                             "message": "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}"
                                                                  for x in e.errors())}}
        except ToolError as e:
            ctx.db.rollback()
            result = {"ok": False, "error": {"code": e.code, "message": str(e)}}
    duration = int((time.perf_counter() - started) * 1000)
    log_output = result.get("data") if result["ok"] else result["error"]
    if name == "search_knowledge_base" and result["ok"]:  # keep logs small
        log_output = {k: v for k, v in result["data"].items() if k != "chunks"} | {
            "sources": [c["document"] + "#" + c["title"] for c in result["data"]["chunks"]]}
    ctx.db.add(AgentToolLog(conversation_id=ctx.conversation.id if ctx.conversation else None, tool_name=name,
                            input=_jsonable(args), output=_jsonable(log_output), success=result["ok"],
                            error=None if result["ok"] else result["error"]["message"], duration_ms=duration))
    ctx.db.commit()
    return result


def _jsonable(v):
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_jsonable(x) for x in v]
    if isinstance(v, datetime):
        return v.isoformat()
    return v
