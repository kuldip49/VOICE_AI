"""Customer-facing conversation API (used by the Live Voice Agent page)."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import serializers as ser
from ..agent.orchestrator import T, SalesAgent
from ..agent.tools import ToolContext, execute_tool
from ..config import get_settings
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


def open_conversation(db: Session, language: str, channel: str = "text", customer_id: int | None = None) -> Conversation:
    """Create a conversation and its stored greeting; shared by web and phone channels."""
    if customer_id:
        customer = db.get(Customer, customer_id)
        if not customer:
            raise HTTPException(404, "Unknown customer")
    else:
        customer = Customer(language=language)
        customer.lead = Lead()
        db.add(customer)
        db.flush()
    if not customer.lead:
        customer.lead = Lead()
        db.flush()
    conv = Conversation(customer_id=customer.id, channel=channel, language=language, state={})
    db.add(conv)
    db.flush()
    prof = get_setting(db, "business_profile")
    greet = T["greet"][language].format(agent=prof["agent_name"], company=prof["company_name"])
    if customer.name:
        greet = greet.replace("!", f", {customer.name}!", 1) if language == "en" else greet
    db.add(Message(conversation_id=conv.id, role="assistant", content=greet, language=language,
                   intents=["greeting"], generated_by="demo-rules"))
    db.commit()
    db.refresh(conv)
    return conv


@router.post("", dependencies=[Depends(rate_limit)])
def start_conversation(body: StartIn, db: Session = Depends(get_db)):
    conv = open_conversation(db, body.language, body.channel, body.customer_id)
    return ser.conversation(conv, with_messages=True)


def process_message(db: Session, conv: Conversation, text: str, llm_timeout_seconds: float | None = None):
    """Run the existing sales agent for one typed or transcribed caller turn."""
    if conv.status != "active":
        raise HTTPException(409, "Conversation has ended")
    provider_settings = get_settings()
    if llm_timeout_seconds is not None:
        provider_settings = provider_settings.model_copy(update={"llm_timeout_seconds": llm_timeout_seconds})
    provider = get_provider(provider_settings)
    agent = SalesAgent(db, conv, embed_fn=getattr(provider, "embed", None) if provider else None, provider=provider)
    user_msg, bot_msg, res = agent.handle(text.strip())
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


@router.post("/{conversation_id}/messages", dependencies=[Depends(rate_limit)])
def send_message(conversation_id: str, body: MessageIn, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    if body.channel and body.channel != conv.channel and body.channel == "voice":
        conv.channel = "voice"
    return process_message(db, conv, body.text)


@router.get("/{conversation_id}")
def get_conversation(conversation_id: str, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    d = ser.conversation(conv, with_messages=True)
    d["customer"] = ser.customer(conv.customer)
    d["lead"] = ser.lead(conv.customer.lead)
    return d


def close_conversation(db: Session, conv: Conversation, llm_timeout_seconds: float | None = None) -> Conversation:
    """Finalize a conversation once, qualify the lead and save its summary."""
    if conv.status == "active":
        conv.status = "ended"
        conv.ended_at = datetime.utcnow()
        db.commit()
    ctx = ToolContext(db=db, conversation=conv, llm_timeout_seconds=llm_timeout_seconds)
    execute_tool(ctx, "qualify_lead", {"customer_id": conv.customer_id})
    res = execute_tool(ctx, "create_conversation_summary", {"conversation_id": conv.id})
    if not res["ok"]:
        raise HTTPException(500, res["error"]["message"])
    db.refresh(conv)
    return conv


@router.post("/{conversation_id}/end")
def end_conversation(conversation_id: str, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return ser.conversation(close_conversation(db, conv), with_messages=False)


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
