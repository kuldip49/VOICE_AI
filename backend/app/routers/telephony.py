"""Inbound Exotel AgentStream endpoint backed by the existing sales conversation agent."""
from __future__ import annotations

import asyncio
import base64
import hmac
import logging
import re
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, WebSocket
from sqlalchemy import select

from ..agent.orchestrator import is_goodbye
from ..config import get_settings
from ..database import SessionLocal
from ..models import Conversation, Customer, Lead, TelephonyCall
from ..routers.conversations import close_conversation, open_conversation, process_message
from ..services.exotel_stream import ExotelStreamSession
from ..services.llm import provider_status

log = logging.getLogger("salespilot.telephony")
router = APIRouter(prefix="/api/telephony/exotel", tags=["phone calls"])
PHONE_RE = re.compile(r"^\+?[0-9]{6,20}$")
VOICE_LLM_TIMEOUT_SECONDS = 8.0


def _valid_public_wss(value: str) -> bool:
    parsed = urlparse(value)
    return (parsed.scheme == "wss" and bool(parsed.netloc) and parsed.path == "/api/telephony/exotel/stream"
            and parsed.query == "sample-rate=16000" and not parsed.username and not parsed.password
            and not parsed.fragment and len(value) < 500)


def _authorized(socket: WebSocket) -> bool:
    """Validate Exotel's HTTP Basic Auth handshake against the configured API key/token."""
    cfg = get_settings()
    supplied = socket.headers.get("authorization", "")
    if not (cfg.exotel_api_key and cfg.exotel_api_token and supplied.startswith("Basic ")):
        return False
    try:
        decoded = base64.b64decode(supplied[6:], validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return False
    expected = f"{cfg.exotel_api_key}:{cfg.exotel_api_token}"
    return hmac.compare_digest(decoded, expected)


def _clean_phone(raw: Any) -> str | None:
    value = str(raw or "").strip()
    return value if PHONE_RE.fullmatch(value) else None


def _get_call(db, call_sid: str) -> TelephonyCall | None:
    return db.get(TelephonyCall, call_sid) if call_sid else None


def _start_call(call_sid: str, caller_number: str | None, language: str = "en") -> str:
    with SessionLocal() as db:
        call = _get_call(db, call_sid)
        if call is None:
            call = TelephonyCall(call_sid=call_sid, caller_number=caller_number, status="received")
            db.add(call)
            db.commit()
        elif caller_number and not call.caller_number:
            call.caller_number = caller_number
            db.commit()

        conv = db.get(Conversation, call.conversation_id) if call.conversation_id else None
        if conv and conv.status == "active":
            call.status = "in-progress"
            call.language = conv.language
            db.commit()
            last_reply = next((m.content for m in reversed(conv.messages) if m.role == "assistant"), "")
            return last_reply or "Hello. How can I help you today?"

        customer = None
        if caller_number:
            customer = db.execute(select(Customer).where(Customer.phone == caller_number)
                                  .order_by(Customer.id).limit(1)).scalars().first()
        if customer is None:
            customer = Customer(phone=caller_number, language=language)
            customer.lead = Lead()
            db.add(customer)
            db.flush()
        elif not customer.lead:
            customer.lead = Lead()
            db.flush()

        conv = open_conversation(db, language, "voice", customer.id)
        call.conversation_id = conv.id
        call.language = language
        call.status = "in-progress"
        call.silence_count = 0
        db.commit()
        return conv.messages[-1].content


def _process_turn(call_sid: str, text: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        call = _get_call(db, call_sid)
        conv = db.get(Conversation, call.conversation_id) if call and call.conversation_id else None
        if not call or not conv or conv.status != "active":
            return None
        result = process_message(db, conv, text[:2000], llm_timeout_seconds=VOICE_LLM_TIMEOUT_SECONDS)
        reply = result["assistant_message"]["content"]
        language = conv.language if conv.language in {"en", "hi"} else "en"
        call.language = language
        call.status = "in-progress"
        conv.customer.language = language
        goodbye = is_goodbye(text)
        if goodbye:
            close_conversation(db, conv, llm_timeout_seconds=VOICE_LLM_TIMEOUT_SECONDS)
            call.status = "completed"
        db.commit()
        return {"reply": reply, "language": language, "hangup": goodbye}


def _switch_language(call_sid: str) -> dict[str, str] | None:
    with SessionLocal() as db:
        call = _get_call(db, call_sid)
        conv = db.get(Conversation, call.conversation_id) if call and call.conversation_id else None
        if not call or not conv or conv.status != "active":
            return None
        language = "hi" if conv.language == "en" else "en"
        conv.language = language
        conv.customer.language = language
        call.language = language
        db.commit()
        if language == "hi":
            return {"reply": "भाषा हिन्दी में बदल दी गई है। मैं आपकी क्या मदद करूँ?", "language": language}
        return {"reply": "Language changed to English. How can I help you?", "language": language}


def _finish_call(call_sid: str) -> None:
    with SessionLocal() as db:
        call = _get_call(db, call_sid)
        if not call:
            return
        conv = db.get(Conversation, call.conversation_id) if call.conversation_id else None
        if conv and conv.status == "active":
            try:
                close_conversation(db, conv, llm_timeout_seconds=VOICE_LLM_TIMEOUT_SECONDS)
            except Exception:
                db.rollback()
                log.exception("Could not finalize interrupted Exotel call %s", call_sid)
                call = _get_call(db, call_sid)
        if call:
            call.status = "completed"
            db.commit()


@router.get("/status")
def phone_service_status():
    """Non-secret readiness check for the Exotel and Sarvam call path."""
    cfg = get_settings()
    account_configured = bool(cfg.exotel_account_sid and cfg.exotel_api_key and cfg.exotel_api_token)
    stream_configured = _valid_public_wss(cfg.exotel_public_wss_url) and cfg.exotel_sample_rate == 16000
    speech_configured = bool(cfg.sarvam_api_key and cfg.sarvam_stt_model and cfg.sarvam_tts_model)
    return {
        "provider": "exotel",
        "phone_number": cfg.exotel_phone_number or None,
        "account_configured": account_configured,
        "stream_configured": stream_configured,
        "speech_configured": speech_configured,
        "ready": bool(account_configured and cfg.exotel_phone_number and stream_configured and speech_configured),
        "wss_url": cfg.exotel_public_wss_url or None,
        "llm": provider_status()["active"],
        "speech_languages": ["en-IN", "hi-IN"],
    }


@router.websocket("/stream")
async def exotel_stream(socket: WebSocket):
    cfg = get_settings()
    if not _authorized(socket):
        await socket.close(code=1008, reason="Invalid Exotel credentials")
        return
    if not (_valid_public_wss(cfg.exotel_public_wss_url)
            and cfg.exotel_sample_rate == 16000 and cfg.sarvam_api_key):
        await socket.close(code=1011, reason="Voice service is not configured")
        return

    holder: dict[str, ExotelStreamSession] = {}

    async def start_call(info: dict[str, Any]) -> dict[str, str]:
        session = holder["session"]
        call_sid = session.call_sid
        caller = _clean_phone(info.get("from") or info.get("from_number"))
        greeting = await asyncio.to_thread(_start_call, call_sid, caller)
        return {"greeting": greeting, "language": "en"}

    async def handle_transcript(text: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(_process_turn, holder["session"].call_sid, text)

    async def finish_call() -> None:
        await asyncio.to_thread(_finish_call, holder["session"].call_sid)

    async def switch_language() -> dict[str, str] | None:
        return await asyncio.to_thread(_switch_language, holder["session"].call_sid)

    session = ExotelStreamSession(socket, cfg, start_call=start_call,
                                  handle_transcript=handle_transcript,
                                  finish_call=finish_call,
                                  switch_language=switch_language)
    holder["session"] = session
    await session.run()
