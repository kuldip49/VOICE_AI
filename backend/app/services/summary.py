"""Call summarisation: structured facts from the database + optional LLM prose."""
from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Appointment, CallSummary, Conversation, SentimentRecord
from .llm import ChatMessage, LLMError, get_provider
from .scheduling import format_slot

FOLLOW_UPS = {
    "HOT": "Call within 24 hours to complete enrollment; confirm payment option (EMI/full).",
    "WARM": "Send course brochure and fee details by email; follow up in 2-3 days.",
    "COLD": "Add to nurture list; invite to the Saturday demo class.",
}


def build_summary(db: Session, conversation: Conversation,
                  llm_timeout_seconds: float | None = None) -> CallSummary:
    customer = conversation.customer
    lead = customer.lead
    sentiments = db.execute(select(SentimentRecord).where(SentimentRecord.conversation_id == conversation.id)).scalars().all()
    labels = Counter(s.label for s in sentiments)
    objections = sorted({o for s in sentiments for o in (s.objections or [])})
    overall = labels.most_common(1)[0][0] if labels else "neutral"
    if labels.get("frustrated"):
        overall = "frustrated"
    appt = db.execute(select(Appointment).where(Appointment.conversation_id == conversation.id,
                                                Appointment.status == "booked")).scalars().first()
    user_msgs = [m.content for m in conversation.messages if m.role == "user"]
    questions = [m for m in user_msgs if "?" in m][:5]

    interests = [lead.interest] if lead and lead.interest else []
    follow_up = FOLLOW_UPS[lead.category if lead else "COLD"]
    if "price" in objections:
        follow_up += " Address price concern with EMI / early-bird options."
    if appt:
        follow_up = f"Prepare for counselling session on {format_slot(appt.start_time)}. " + follow_up

    name = customer.name or "Unknown customer"
    facts = [
        f"{name} had a {conversation.channel} conversation with {len(user_msgs)} customer messages.",
        f"Interest: {lead.interest if lead and lead.interest else 'unknown'}.",
        f"Budget: {'₹{:,}'.format(lead.budget) if lead and lead.budget else 'unknown'}.",
        f"Timeline: {lead.timeline if lead and lead.timeline else 'unknown'}.",
    ]
    if questions:
        facts.append("Asked about: " + "; ".join(q[:80] for q in questions) + ".")
    if objections:
        facts.append("Objections: " + ", ".join(objections) + ".")
    facts.append(f"Appointment: {format_slot(appt.start_time) if appt else 'none booked'}.")
    text = " ".join(facts)
    generated_by = "demo-rules"

    provider_settings = get_settings()
    if llm_timeout_seconds is not None:
        provider_settings = provider_settings.model_copy(update={"llm_timeout_seconds": llm_timeout_seconds})
    provider = get_provider(provider_settings)
    if provider and user_msgs:
        transcript = "\n".join(f"{m.role}: {m.content}" for m in conversation.messages[-30:])
        try:
            text = provider.generate(
                "Summarise this sales call in 3-4 sentences for a sales manager. Use ONLY facts in the transcript and "
                "the fact sheet. Do not invent details.",
                [ChatMessage("user", f"Fact sheet:\n{text}\n\nTranscript:\n{transcript}")])
            generated_by = provider.label
        except LLMError:
            generated_by = "demo-rules (llm-error)"

    s = conversation.summary or CallSummary(conversation_id=conversation.id, customer_id=customer.id)
    s.summary = text
    s.requirements = (lead.requirements if lead else None) or None
    s.objections = objections
    s.interests = interests
    s.budget = lead.budget if lead else None
    s.purchase_intent = lead.intent_level if lead else "unknown"
    s.sentiment = overall
    s.lead_score = lead.score if lead else 0
    s.lead_category = lead.category if lead else "COLD"
    s.follow_up_action = follow_up
    s.appointment_info = f"{format_slot(appt.start_time)} (id {appt.id})" if appt else None
    s.generated_by = generated_by
    if s.id is None:
        db.add(s)
    db.commit()
    return s
