"""Customer-facing conversation API (used by the Live Voice Agent page)."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import serializers as ser
from ..agent.orchestrator import T, SalesAgent
from ..agent.tools import ToolContext, execute_tool
from ..database import get_db
from ..models import AgentToolLog, Conversation, Customer, Lead, Message
from ..security import rate_limit, require_admin
from ..services.llm import get_provider
from ..services.settings_store import get_setting

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class StartIn(BaseModel):
    language: str = Field(default="en", pattern=r"^(en|hi)$")
    channel: str = Field(default="text", pattern=r"^(text|voice)$")
    customer_id: int | None = Field(default=None, gt=0)  # continue as a known customer (persistent memory)


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    channel: str | None = Field(default=None, pattern=r"^(text|voice)$")


def _embed_fn():
    p = get_provider()
    return getattr(p, "embed", None) if p else None


@router.post("", dependencies=[Depends(rate_limit)])
def start_conversation(body: StartIn, db: Session = Depends(get_db)):
    if body.customer_id:
        customer = db.get(Customer, body.customer_id)
        if not customer:
            raise HTTPException(404, "Unknown customer")
    else:
        customer = Customer(language=body.language)
        customer.lead = Lead()
        db.add(customer)
        db.flush()
    conv = Conversation(customer_id=customer.id, channel=body.channel, language=body.language, state={})
    db.add(conv)
    db.flush()
    prof = get_setting(db, "business_profile")
    greet = T["greet"][body.language].format(agent=prof["agent_name"], company=prof["company_name"])
    if customer.name:
        greet = greet.replace("!", f", {customer.name}!", 1) if body.language == "en" else greet
    db.add(Message(conversation_id=conv.id, role="assistant", content=greet, language=body.language,
                   intents=["greeting"], generated_by="demo-rules"))
    db.commit()
    db.refresh(conv)
    return ser.conversation(conv, with_messages=True)


@router.post("/{conversation_id}/messages", dependencies=[Depends(rate_limit)])
def send_message(conversation_id: str, body: MessageIn, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    if conv.status != "active":
        raise HTTPException(409, "Conversation has ended")
    if body.channel and body.channel != conv.channel and body.channel == "voice":
        conv.channel = "voice"
    agent = SalesAgent(db, conv, embed_fn=_embed_fn())
    user_msg, bot_msg, res = agent.handle(body.text.strip())
    db.refresh(conv)
    return {
        "conversation": ser.conversation(conv),
        "user_message": ser.message(user_msg),
        "assistant_message": ser.message(bot_msg),
        "tool_calls": res.tool_calls,
        "sentiment": res.sentiment,
        "lead": ser.lead(conv.customer.lead),
        "customer": ser.customer(conv.customer),
    }


@router.get("/{conversation_id}")
def get_conversation(conversation_id: str, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    d = ser.conversation(conv, with_messages=True)
    d["customer"] = ser.customer(conv.customer)
    d["lead"] = ser.lead(conv.customer.lead)
    return d


@router.post("/{conversation_id}/end")
def end_conversation(conversation_id: str, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    if conv.status == "active":
        conv.status = "ended"
        conv.ended_at = datetime.utcnow()
        db.commit()
    ctx = ToolContext(db=db, conversation=conv)
    execute_tool(ctx, "qualify_lead", {"customer_id": conv.customer_id})
    res = execute_tool(ctx, "create_conversation_summary", {"conversation_id": conv.id})
    if not res["ok"]:
        raise HTTPException(500, res["error"]["message"])
    db.refresh(conv)
    return ser.conversation(conv, with_messages=False)


# ---- admin views ----------------------------------------------------------------
admin = APIRouter(prefix="/api", tags=["admin"], dependencies=[Depends(require_admin)])


@admin.get("/conversations")
def list_conversations(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.execute(select(Conversation).order_by(Conversation.started_at.desc()).limit(min(limit, 200))).scalars()
    return [ser.conversation(c) for c in rows]


@admin.get("/conversations/{conversation_id}/tool-logs")
def tool_logs(conversation_id: str, db: Session = Depends(get_db)):
    rows = db.execute(select(AgentToolLog).where(AgentToolLog.conversation_id == conversation_id)
                      .order_by(AgentToolLog.id)).scalars()
    return [{"id": r.id, "tool": r.tool_name, "input": r.input, "output": r.output, "success": r.success,
             "error": r.error, "duration_ms": r.duration_ms, "created_at": ser.iso(r.created_at)} for r in rows]
