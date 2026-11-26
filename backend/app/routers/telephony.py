"""Twilio inbound voice webhooks that connect phone callers to the sales agent."""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

try:
    from twilio.request_validator import RequestValidator
except ImportError:  # Existing local virtualenvs need to install the newly added requirement.
    RequestValidator = None

from ..agent.orchestrator import is_goodbye
from ..config import get_settings
from ..database import get_db
from ..models import Conversation, Customer, Lead, TelephonyCall
from ..routers.conversations import close_conversation, open_conversation, process_message
from ..services.llm import provider_status
from ..services.settings_store import get_setting

log = logging.getLogger("salespilot.telephony")
router = APIRouter(prefix="/api/telephony/twilio", tags=["phone calls"])

LANGUAGE_PATH = "/api/telephony/twilio/language"
TURN_PATH = "/api/telephony/twilio/turn"
LOCALES = {"en": "en-IN", "hi": "hi-IN"}
SPEECH_MODEL = "experimental_conversations"  # Twilio supports both en-IN and hi-IN on this model.
VOICE_LLM_TIMEOUT_SECONDS = 3.0  # leave room under Twilio's 15-second voice webhook deadline
PHONE_RE = re.compile(r"^\+?[0-9]{6,20}$")


def _webhook_url(path: str) -> str:
    base = get_settings().twilio_public_base_url.rstrip("/")
    return f"{base}{path}"


def _xml_response(root: ET.Element, status_code: int = 200) -> Response:
    xml = ET.tostring(root, encoding="unicode", short_empty_elements=True)
    return Response(content=f'<?xml version="1.0" encoding="UTF-8"?>{xml}', status_code=status_code,
                    media_type="application/xml", headers={"Cache-Control": "no-store"})


def _response() -> ET.Element:
    return ET.Element("Response")


def _say(parent: ET.Element, text: str, language: str) -> None:
    node = ET.SubElement(parent, "Say", {"language": LOCALES.get(language, LOCALES["en"])})
    node.text = text.replace("\n", ". ").replace("₹", "rupees ")


def _language_menu(company_name: str = "") -> ET.Element:
    root = _response()
    welcome = f"Welcome to {company_name}. For English, press 1." if company_name else "Welcome. For English, press 1."
    _say(root, welcome, "en")
    _say(root, "हिंदी में बात करने के लिए 2 दबाएँ।", "hi")
    gather = ET.SubElement(root, "Gather", {
        "input": "dtmf", "numDigits": "1", "timeout": "8", "method": "POST",
        "action": _webhook_url(LANGUAGE_PATH), "actionOnEmptyResult": "true",
    })
    _say(gather, "Press 1 for English, or press 2 for Hindi.", "en")
    return root


def _speech_gather(language: str, prompt: str, action_path: str = TURN_PATH) -> ET.Element:
    speech_model = get_settings().twilio_speech_model
    if speech_model not in {"experimental_conversations", "experimental_utterances"}:
        speech_model = SPEECH_MODEL
    root = _response()
    gather = ET.SubElement(root, "Gather", {
        "input": "dtmf speech", "language": LOCALES.get(language, LOCALES["en"]),
        "speechModel": speech_model, "speechTimeout": "3", "timeout": "6", "numDigits": "1",
        "method": "POST", "action": _webhook_url(action_path), "actionOnEmptyResult": "true",
    })
    switch_hint = (" To switch languages during the call, press 9."
                   if language == "en" else "कॉल के दौरान भाषा बदलने के लिए 9 दबाएँ।")
    _say(gather, prompt + switch_hint, language)
    return root


def _hangup(text: str, language: str) -> ET.Element:
    root = _response()
    _say(root, text, language)
    ET.SubElement(root, "Hangup")
    return root


async def _verified_form(request: Request) -> dict[str, str]:
    """Parse all Twilio form fields and fail closed unless the signature is valid."""
    cfg = get_settings()
    if not cfg.twilio_auth_token or not cfg.twilio_public_base_url:
        raise HTTPException(503, "Inbound phone service is not configured")
    if RequestValidator is None:
        raise HTTPException(503, "Install backend requirements to enable Twilio signature validation")
    if not cfg.twilio_public_base_url.startswith("https://"):
        raise HTTPException(503, "Twilio callbacks require a public HTTPS URL")

    form = await request.form()
    params: dict[str, str] = {}
    for key, value in form.multi_items():
        if key in params:
            # Twilio normally sends scalar voice fields. Reject ambiguous duplicates instead of
            # silently validating one value while using another.
            raise HTTPException(400, "Duplicate webhook parameter")
        params[str(key)] = str(value)

    url = f"{cfg.twilio_public_base_url.rstrip('/')}{request.url.path}"
    if request.url.query:
        url += f"?{request.url.query}"
    signature = request.headers.get("X-Twilio-Signature", "")
    try:
        valid = RequestValidator(cfg.twilio_auth_token).validate(url, params, signature)
    except (TypeError, ValueError):
        valid = False
    if not valid:
        log.warning("Rejected Twilio webhook with invalid signature: %s", request.url.path)
        raise HTTPException(403, "Invalid Twilio signature")
    return params


def _get_call(db: Session, call_sid: str) -> TelephonyCall:
    call = db.get(TelephonyCall, call_sid)
    if not call:
        raise HTTPException(404, "Phone call was not initialized")
    return call


def _phone_number(raw: str | None) -> str | None:
    value = (raw or "").strip()
    return value if PHONE_RE.fullmatch(value) else None


def _start_call_conversation(db: Session, call: TelephonyCall, language: str) -> Conversation:
    customer = None
    if call.caller_number:
        customer = db.execute(select(Customer).where(Customer.phone == call.caller_number)
                              .order_by(Customer.id).limit(1)).scalars().first()
    if customer is None:
        customer = Customer(phone=call.caller_number, language=language)
        customer.lead = Lead()
        db.add(customer)
        db.flush()
    conv = open_conversation(db, language, "voice", customer.id)
    call.conversation_id = conv.id
    call.language = language
    call.status = "in-progress"
    call.silence_count = 0
    db.commit()
    return conv


@router.get("/status")
def phone_service_status():
    """Non-secret readiness check for the incoming-call integration."""
    cfg = get_settings()
    return {
        "provider": "twilio",
        "configured": bool(RequestValidator and cfg.twilio_account_sid and cfg.twilio_auth_token
                            and cfg.twilio_phone_number and cfg.twilio_public_base_url.startswith("https://")),
        "phone_number": cfg.twilio_phone_number or None,
        "webhook_configured": cfg.twilio_public_base_url.startswith("https://"),
        "llm": provider_status()["active"],
        "speech_languages": ["en-IN", "hi-IN"],
    }


@router.post("/voice")
def incoming_call(params: dict[str, str] = Depends(_verified_form), db: Session = Depends(get_db)):
    call_sid = params.get("CallSid", "")
    if not call_sid:
        raise HTTPException(400, "Missing CallSid")

    call = db.get(TelephonyCall, call_sid)
    if call is None:
        caller = _phone_number(params.get("From"))
        call = TelephonyCall(call_sid=call_sid, caller_number=caller, status="language-selection")
        db.add(call)
        db.commit()
    if call.conversation_id:
        conv = db.get(Conversation, call.conversation_id)
        if conv and conv.status == "active":
            latest = conv.messages[-1].content if conv.messages else "How can I help you today?"
            return _xml_response(_speech_gather(conv.language, latest))
    company = get_setting(db, "business_profile").get("company_name", "")
    return _xml_response(_language_menu(company))


@router.post("/language")
def select_call_language(params: dict[str, str] = Depends(_verified_form), db: Session = Depends(get_db)):
    call = _get_call(db, params.get("CallSid", ""))
    if call.conversation_id:
        conv = db.get(Conversation, call.conversation_id)
        if conv and conv.status == "active":
            latest = conv.messages[-1].content if conv.messages else "How can I help you today?"
            return _xml_response(_speech_gather(conv.language, latest))

    language = {"1": "en", "2": "hi"}.get(params.get("Digits", ""))
    if not language:
        call.language_attempts += 1
        db.commit()
        if call.language_attempts >= 2:
            call.status = "ended"
            db.commit()
            return _xml_response(_hangup("I could not get your language choice. Please call again. धन्यवाद।", "en"))
        company = get_setting(db, "business_profile").get("company_name", "")
        return _xml_response(_language_menu(company))

    conv = _start_call_conversation(db, call, language)
    greeting = conv.messages[-1].content
    return _xml_response(_speech_gather(language, greeting))


@router.post("/turn")
def call_turn(params: dict[str, str] = Depends(_verified_form), db: Session = Depends(get_db)):
    call = _get_call(db, params.get("CallSid", ""))
    conv = db.get(Conversation, call.conversation_id) if call.conversation_id else None
    if not conv or conv.status != "active":
        return _xml_response(_hangup("This conversation has ended. Goodbye.", call.language or "en"))

    digits = (params.get("Digits") or "").strip()
    if digits == "9":
        language = "hi" if conv.language == "en" else "en"
        conv.language = language
        conv.customer.language = language
        call.language = language
        db.commit()
        prompt = ("Language changed to English. How can I help you?" if language == "en"
                  else "भाषा हिन्दी में बदल दी गई है। मैं आपकी क्या मदद करूँ?")
        return _xml_response(_speech_gather(language, prompt))

    transcript = (params.get("SpeechResult") or "").strip()
    caller_text = (transcript or digits)[:2000]
    if not caller_text:
        call.silence_count += 1
        db.commit()
        if call.silence_count >= 2:
            close_conversation(db, conv, llm_timeout_seconds=VOICE_LLM_TIMEOUT_SECONDS)
            call.status = "completed"
            db.commit()
            return _xml_response(_hangup("I could not hear you, so I have ended the call. Please call again when you are ready.",
                                         conv.language))
        prompt = ("Sorry, I did not catch that. Please say that again." if conv.language == "en"
                  else "माफ़ कीजिए, मैं सुन नहीं पाई। कृपया फिर से कहिए।")
        return _xml_response(_speech_gather(conv.language, prompt))

    call.silence_count = 0
    result = process_message(db, conv, caller_text, llm_timeout_seconds=VOICE_LLM_TIMEOUT_SECONDS)
    reply = result["assistant_message"]["content"]
    language = conv.language
    conv.customer.language = language
    call.language = language
    if is_goodbye(caller_text):
        close_conversation(db, conv, llm_timeout_seconds=VOICE_LLM_TIMEOUT_SECONDS)
        call.status = "completed"
        db.commit()
        return _xml_response(_hangup(reply, language))
    call.status = "in-progress"
    db.commit()
    return _xml_response(_speech_gather(language, reply))


@router.post("/status")
def call_status(params: dict[str, str] = Depends(_verified_form), db: Session = Depends(get_db)):
    """Optional IncomingPhoneNumber status callback; close abandoned calls and save summaries."""
    call = db.get(TelephonyCall, params.get("CallSid", ""))
    if not call:
        return Response(status_code=204)
    status = (params.get("CallStatus") or "").lower()
    terminal = {"completed", "busy", "failed", "no-answer", "canceled"}
    if status in terminal and call.conversation_id:
        conv = db.get(Conversation, call.conversation_id)
        if conv and conv.status == "active":
            try:
                close_conversation(db, conv, llm_timeout_seconds=VOICE_LLM_TIMEOUT_SECONDS)
            except Exception:
                db.rollback()
                log.exception("Could not finalize an interrupted phone conversation")
    if status and (status in terminal or call.status not in terminal):
        call.status = status
    db.commit()
    return Response(status_code=204)
