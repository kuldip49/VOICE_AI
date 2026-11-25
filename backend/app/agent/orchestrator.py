"""Sales agent orchestration.

For every customer message the orchestrator runs a fixed, inspectable pipeline:

    1. save message + detect language
    2. update_customer_profile  (facts extracted from the message: name, budget, interest...)
    3. analyze_sentiment
    4. detect intents  -> decide which tools are needed (planner)
    5. run tools       (knowledge search, slots, booking with confirmation, cancel...)
    6. update_crm_record + qualify_lead (score 0-100 with reasons)
    7. compose reply:
         - transactional replies (slot lists, booking confirmations) are always built from the exact
           tool results so times/IDs can never be hallucinated;
         - knowledge answers are written by the LLM when one is configured, grounded ONLY in the
           retrieved chunks; otherwise a clearly labelled demo template quotes the knowledge base.
    8. append one natural qualifying question if information is still missing.

Why a rule-based planner + LLM writer instead of letting the LLM pick tools freely?
It is deterministic, testable without an API key, cheap, and the LLM cannot trigger a booking
on its own. The tool layer is provider-agnostic, so native LLM function-calling can be added later.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from ..models import Conversation, Message
from ..services import extraction, scheduling
from ..services.llm import ChatMessage, LLMError, get_provider
from ..services.settings_store import get_setting
from .tools import ToolContext, execute_tool

CONTEXT_MESSAGES = 8  # recent turns sent to the LLM; older turns live in conversation.memory_summary

HINGLISH = re.compile(r"\b(kya|hai|hain|mujhe|mera|meri|aap|aapka|chahiye|kitna|kitni|kaise|nahi|haan|batao|"
                      r"bataiye|karna|karni|seekhna|naam|accha|theek)\b", re.I)
GREETING = re.compile(r"^\s*(hi|hello|hey|namaste|namaskar|good (morning|afternoon|evening))\b|नमस्ते|नमस्कार|हेलो",
                      re.I)
GOODBYE = re.compile(
    r"\b(bye|goodbye|that'?s all|thank you,? bye|see you|(?:hang|hand)\s*up(?:\s+the)?(?:\s+(?:phone|call))?|"
    r"end(?:\s+the)?\s+call|finish(?:\s+the)?\s+call|disconnect)\b|"
    r"अलविदा|धन्यवाद,? बस|फोन रख|फोन काट|कॉल (?:खत्म|बंद|समाप्त)|अब बस",
    re.I,
)
BOOKING = re.compile(r"\b(appointment|book|schedule|counsel+ing|counsel+or|call ?back|meeting|slot|talk to (a|an) "
                     r"(human|person|advisor|counsellor)|demo session)\b|अपॉइंटमेंट|बुक|मीटिंग|काउंसलिंग", re.I)
CANCEL = re.compile(r"\b(cancel|call off)\b.*\b(appointment|booking|meeting|session)\b|\bcancel (it|my)\b|रद्द|कैंसिल",
                    re.I)
RESCHEDULE = re.compile(r"\b(reschedule|change (the|my) (time|slot|appointment)|another time|different time)\b", re.I)
YES = re.compile(r"^\s*(yes|yeah|yep|yup|sure|ok|okay|confirm(ed)?|correct|book it|go ahead|please do|perfect|"
                 r"haan|han|ha|ji|ji haan|theek hai|हाँ|हां|हा|जी|जी हाँ|ठीक है|कन्फर्म)(?=$|[\s,.!?।])", re.I)
NO = re.compile(r"^\s*(no|nope|not that|nah|nahi|नहीं|ना)(?=$|[\s,.!?।])", re.I)
QUESTION_HINT = re.compile(r"\?|\b(what|which|how|when|where|who|tell me|explain|details|price|fee|cost|duration|"
                           r"refund|emi|discount|batch|syllabus|certificate|placement|job|course|program|offer|"
                           r"expensive|costly|contact|phone|email|address|demo|laptop|mentor|recorded|live)\b"
                           r"|क्या|कितना|कितनी|कैसे|कब|कौन|बताइए|बताओ|कोर्स|फीस|कीमत|महंगा|रिफंड", re.I)
ORDINALS = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4,
            "पहला": 1, "पहले": 1, "दूसरा": 2, "दूसरे": 2, "तीसरा": 3, "तीसरे": 3, "चौथा": 4, "pehla": 1, "doosra": 2,
            "dusra": 2, "teesra": 3}
TIME_RE = re.compile(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?", re.I)

T = {  # response templates (en / hi)
    "greet": {"en": "Hello! I'm {agent}, the admissions assistant for {company}. How can I help you today?",
              "hi": "नमस्ते! मैं {agent} हूँ, {company} की एडमिशन असिस्टेंट। मैं आपकी क्या मदद कर सकती हूँ?"},
    "kb_intro": {"en": "Here is what our knowledge base says:", "hi": "हमारे नॉलेज बेस के अनुसार:"},
    "not_found": {"en": "I'm sorry, that information is not in our knowledge base, so I won't guess. "
                        "A counsellor can answer it in a free counselling session.",
                  "hi": "माफ़ कीजिए, यह जानकारी हमारे नॉलेज बेस में नहीं है, इसलिए मैं अनुमान नहीं लगाऊँगी। "
                        "एक काउंसलर फ्री काउंसलिंग सेशन में इसका जवाब दे सकते हैं।"},
    "empty_kb": {"en": "Our knowledge base is empty right now, so I can't answer product questions yet.",
                 "hi": "अभी हमारा नॉलेज बेस खाली है, इसलिए मैं प्रोडक्ट से जुड़े सवालों का जवाब नहीं दे सकती।"},
    "slots": {"en": "Here are the next available counselling slots (30 minutes, online):\n{slots}\n"
                    "Which one works for you? You can say the option number.",
              "hi": "ये अगले उपलब्ध काउंसलिंग स्लॉट हैं (30 मिनट, ऑनलाइन):\n{slots}\n"
                    "आपके लिए कौन सा ठीक है? आप विकल्प संख्या बता सकते हैं।"},
    "no_slots": {"en": "There are no free counselling slots in the next week. Please share your email and a "
                       "counsellor will contact you.",
                 "hi": "अगले हफ्ते कोई स्लॉट खाली नहीं है। कृपया अपना ईमेल बताइए, काउंसलर आपसे संपर्क करेंगे।"},
    "confirm": {"en": "Just to confirm: book a counselling session on {slot} for {name}? Please say yes to confirm.",
                "hi": "पुष्टि के लिए: क्या {name} के लिए {slot} को काउंसलिंग सेशन बुक कर दूँ? पुष्टि के लिए हाँ कहिए।"},
    "need_name": {"en": "Before I book {slot}, may I have your name?",
                  "hi": "{slot} बुक करने से पहले, क्या मैं आपका नाम जान सकती हूँ?"},
    "booked": {"en": "Done! Your counselling session is booked for {slot} (booking #{id}). "
                     "A counsellor will join you online.",
               "hi": "हो गया! आपका काउंसलिंग सेशन {slot} के लिए बुक है (बुकिंग #{id})। काउंसलर ऑनलाइन जुड़ेंगे।"},
    "book_failed": {"en": "I couldn't book that slot: {reason}",
                    "hi": "मैं वह स्लॉट बुक नहीं कर सकी: {reason}"},
    "declined": {"en": "No problem, I haven't booked anything. Would you like a different time?",
                 "hi": "कोई बात नहीं, मैंने कुछ बुक नहीं किया। क्या आप कोई और समय चाहेंगे?"},
    "pick_unclear": {"en": "Sorry, I didn't catch which slot you want. Please say the option number:\n{slots}",
                     "hi": "माफ़ कीजिए, समझ नहीं आया कौन सा स्लॉट। कृपया विकल्प संख्या बताइए:\n{slots}"},
    "cancel_confirm": {"en": "You have a session on {slot}. Should I cancel it? Please say yes to confirm.",
                       "hi": "आपका सेशन {slot} को है। क्या मैं इसे रद्द कर दूँ? पुष्टि के लिए हाँ कहिए।"},
    "cancelled": {"en": "Your session on {slot} has been cancelled.", "hi": "{slot} वाला आपका सेशन रद्द कर दिया गया है।"},
    "no_appt": {"en": "I don't see any upcoming appointment for you.", "hi": "आपका कोई आने वाला अपॉइंटमेंट नहीं दिख रहा।"},
    "goodbye": {"en": "Thank you for talking with {company}{name_part}. Have a great day!",
                "hi": "{company} से बात करने के लिए धन्यवाद{name_part}। आपका दिन शुभ हो!"},
    "ack": {"en": "Thanks{name_part}, noted.", "hi": "धन्यवाद{name_part}, मैंने नोट कर लिया।"},
    "price_ack": {"en": "I understand price matters.", "hi": "मैं समझती हूँ कि कीमत मायने रखती है।"},
    "fallback": {"en": "I can help with course details, fees, batches, policies, or booking a free counselling "
                       "session. What would you like to know?",
                 "hi": "मैं कोर्स की जानकारी, फीस, बैच, नीतियों या फ्री काउंसलिंग सेशन बुक करने में मदद कर सकती हूँ। "
                       "आप क्या जानना चाहेंगे?"},
}
QUAL_Q = {
    "name": {"en": "May I know your name?", "hi": "क्या मैं आपका नाम जान सकती हूँ?"},
    "interest": {"en": "Which area interests you most: AI/ML, data science, web development or cloud?",
                 "hi": "आपकी सबसे ज़्यादा रुचि किसमें है: AI/ML, डेटा साइंस, वेब डेवलपमेंट या क्लाउड?"},
    "budget": {"en": "What budget do you have in mind for the course?",
               "hi": "कोर्स के लिए आपका बजट लगभग कितना है?"},
    "timeline": {"en": "When are you hoping to start?", "hi": "आप कब तक शुरू करना चाहते हैं?"},
    "offer": {"en": "Would you like to book a free 30-minute counselling session?",
              "hi": "क्या आप एक फ्री 30 मिनट का काउंसलिंग सेशन बुक करना चाहेंगे?"},
}


def detect_language(text: str, default: str) -> str:
    if re.search(r"[ऀ-ॿ]", text):
        return "hi"
    if len(HINGLISH.findall(text)) >= 2:
        return "hi"
    if re.search(r"[A-Za-z]{3,}", text):
        return "en"
    return default  # e.g. "2" or "ok" -> keep conversation language


def is_goodbye(text: str) -> bool:
    # A request not to hang up should not be treated as a request to end the call.
    if re.search(r"\b(?:don't|do not|never)\s+(?:(?:hang|hand)\s*up|end(?:\s+the)?\s+call|"
                 r"finish(?:\s+the)?\s+call|disconnect)\b", text, re.I):
        return False
    return bool(GOODBYE.search(text))


@dataclass
class TurnResult:
    reply: str
    language: str
    intents: list[str]
    sources: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    generated_by: str = "demo-rules"
    sentiment: dict | None = None
    lead: dict | None = None


class SalesAgent:
    def __init__(self, db: Session, conversation: Conversation, embed_fn=None):
        self.db = db
        self.conv = conversation
        self.ctx = ToolContext(db=db, conversation=conversation, embed_fn=embed_fn)
        self.calls: list[dict] = []
        self.profile = get_setting(db, "business_profile")

    # -- helpers ---------------------------------------------------------
    def tool(self, _tool_name: str, /, **args) -> dict:
        res = execute_tool(self.ctx, _tool_name, args)
        self.calls.append({"tool": _tool_name, "ok": res["ok"],
                           "detail": (res.get("error") or {}).get("message") if not res["ok"]
                           else _brief(_tool_name, res)})
        return res

    def t(self, key: str, lang: str, **kw) -> str:
        kw.setdefault("agent", self.profile["agent_name"])
        kw.setdefault("company", self.profile["company_name"])
        return T[key][lang].format(**kw)

    def _state(self) -> dict:
        return dict(self.conv.state or {})

    def _save_state(self, st: dict) -> None:
        self.conv.state = st  # reassign so SQLAlchemy detects the JSON change
        self.db.commit()

    # -- main entry ------------------------------------------------------
    def handle(self, text: str) -> tuple[Message, Message, TurnResult]:
        db, conv = self.db, self.conv
        lang = detect_language(text, conv.language)
        user_msg = Message(conversation_id=conv.id, role="user", content=text, language=lang)
        db.add(user_msg)
        db.commit()
        st = self._state()
        cust_id = conv.customer_id

        # 2. profile extraction (+ contextual answers to our last question, e.g. bare "Rahul" or "20000")
        ex = extraction.extract(text, self.profile["products"])
        awaiting = st.get("awaiting")
        if awaiting == "name" and not ex.name:
            words = re.findall(r"[A-Za-zऀ-ॿ]+", text)
            if 1 <= len(words) <= 3 and not YES.match(text) and not NO.match(text) and not QUESTION_HINT.search(text):
                ex.name = " ".join(w[:1].upper() + w[1:] for w in words)
        if awaiting == "budget" and ex.budget is None:
            m = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*(k|thousand|lakh|हज़ार|हजार|लाख)?", text, re.I)
            if m:
                ex.budget = extraction._parse_amount(m.group(1), m.group(2))
        updates = {k: v for k, v in ex.as_dict().items() if k not in ("intent_signal",)}
        if updates:
            self.tool("update_customer_profile", customer_id=cust_id, source_message_id=user_msg.id, **updates)

        # 3. sentiment
        sres = self.tool("analyze_sentiment", message_id=user_msg.id, text=text)
        sent = sres.get("data")

        # 4. intents (planner)
        intents = self._intents(text, st, ex)
        user_msg.intents = intents
        db.commit()

        # 5. run tools + build transactional parts
        parts: list[str] = []
        sources: list[dict] = []
        transactional = False
        generated_by = "demo-rules"
        kb_result = None

        if "confirm" in intents and st.get("pending_slot"):
            transactional = True
            profile = self.tool("retrieve_customer_profile", customer_id=cust_id)["data"]
            name = profile["customer"]["name"]
            slot = datetime.fromisoformat(st["pending_slot"])
            if not name:
                st["awaiting"] = "name"
                parts.append(self.t("need_name", lang, slot=scheduling.format_slot(slot, lang)))
            else:
                r = self.tool("book_appointment", customer_id=cust_id, start_time=st["pending_slot"], confirmed=True)
                st.pop("pending_slot", None)
                st.pop("offered_slots", None)
                if r["ok"]:
                    parts.append(self.t("booked", lang, slot=scheduling.format_slot(slot, lang),
                                        id=r["data"]["appointment_id"]))
                else:
                    parts.append(self.t("book_failed", lang, reason=r["error"]["message"]))
                    if r["error"]["code"] == "slot_taken":
                        parts.append(self._offer_slots(st, lang))
        elif "confirm" in intents and st.get("pending_cancel"):
            transactional = True
            appt_id = st.pop("pending_cancel")
            r = self.tool("cancel_appointment", appointment_id=appt_id, customer_id=cust_id)
            parts.append(self.t("cancelled", lang, slot=scheduling.format_slot(
                datetime.fromisoformat(st.pop("pending_cancel_time")), lang)) if r["ok"]
                         else self.t("book_failed", lang, reason=r["error"]["message"]))
        elif "decline" in intents and (st.get("pending_slot") or st.get("pending_cancel")):
            transactional = True
            for k in ("pending_slot", "pending_cancel", "pending_cancel_time"):
                st.pop(k, None)
            parts.append(self.t("declined", lang))
        elif "slot_choice" in intents:
            transactional = True
            chosen = self._pick_slot(text, st.get("offered_slots", []))
            if chosen:
                st["pending_slot"] = chosen
                profile = self.tool("retrieve_customer_profile", customer_id=cust_id)["data"]
                name = profile["customer"]["name"]
                slot_txt = scheduling.format_slot(datetime.fromisoformat(chosen), lang)
                if name:
                    parts.append(self.t("confirm", lang, slot=slot_txt, name=name))
                else:
                    st["awaiting"] = "name"
                    parts.append(self.t("need_name", lang, slot=slot_txt))
            else:
                parts.append(self.t("pick_unclear", lang, slots=self._slot_lines(st.get("offered_slots", []), lang)))
        elif "cancel_request" in intents:
            transactional = True
            profile = self.tool("retrieve_customer_profile", customer_id=cust_id)["data"]
            up = profile.get("upcoming_appointment")
            if up:
                st["pending_cancel"] = up["id"]
                st["pending_cancel_time"] = up["start_time"]
                parts.append(self.t("cancel_confirm", lang,
                                    slot=scheduling.format_slot(datetime.fromisoformat(up["start_time"]), lang)))
            else:
                parts.append(self.t("no_appt", lang))
        elif "booking_request" in intents:
            transactional = True
            parts.append(self._offer_slots(st, lang))
        elif awaiting == "name" and ex.name and st.get("pending_slot"):
            # customer just told us their name while a slot is pending -> ask for confirmation
            transactional = True
            slot_txt = scheduling.format_slot(datetime.fromisoformat(st["pending_slot"]), lang)
            parts.append(self.t("confirm", lang, slot=slot_txt, name=ex.name))

        if "knowledge_question" in intents and not transactional:
            query = text
            lead_interest = self._lead_interest()
            price_objection = bool(sent and "price" in (sent.get("objections") or []))
            if price_objection:
                # price objection -> look up payment flexibility, not the course page again
                query = "payment options EMI"
            elif not ex.interest and lead_interest and _is_attribute_question(text):
                query = f"{text} {lead_interest}"  # contextual memory: "what's the price?" -> of their course
            kb_result = self.tool("search_knowledge_base", query=query, top_k=3)
            data = kb_result.get("data") or {}
            if price_objection and kb_result["ok"]:
                extra = self.tool("search_knowledge_base", query="discounts offers scholarship", top_k=1)
                if extra["ok"] and extra["data"]["found"]:
                    data["chunks"] = data["chunks"][:1] + extra["data"]["chunks"][:1]
                    data["found"] = True
            if kb_result["ok"] and not data.get("found") and lang == "hi":
                # The sample KB is English. Let Gemini translate/rephrase a Hindi question for retrieval,
                # but still require a matching KB chunk before asking it to answer.
                provider = get_provider()
                if provider:
                    search_context = f"Customer question: {text}\nKnown course interest: {lead_interest or 'unknown'}"
                    try:
                        search_query = provider.generate(
                            "Translate this Hindi or Hinglish question into concise English search terms for a "
                            "course and policy knowledge base. Keep any known course interest and the requested "
                            "attribute, such as fees, duration, schedule, or refund. Return only search terms; "
                            "do not answer the question or add facts.",
                            [ChatMessage("user", search_context)],
                        ).splitlines()[0].strip().strip("`\"' ")[:200]
                        if search_query:
                            translated = self.tool("search_knowledge_base", query=search_query, top_k=3)
                            translated_data = translated.get("data") or {}
                            if translated["ok"] and translated_data.get("found"):
                                kb_result = translated
                                data = translated_data
                    except LLMError:
                        pass  # Keep the grounded not-found response if the rewrite request fails.
            if kb_result["ok"] and data.get("found"):
                sources = [{k: c[k] for k in ("chunk_id", "document", "title", "score", "excerpt")}
                           for c in data["chunks"]]

        # 6. CRM + scoring
        level = ex.intent_signal or ("high" if "booking_request" in intents else
                                     "medium" if "knowledge_question" in intents else "low")
        self.tool("update_crm_record", customer_id=cust_id, intent_level=level)
        q = self.tool("qualify_lead", customer_id=cust_id)
        lead_data = q.get("data")

        # 7. compose
        if "goodbye" in intents and not transactional:
            name = self._customer_name()
            parts = [self.t("goodbye", lang, name_part=f", {name}" if name else "")]
        elif not transactional:
            body, generated_by = self._compose_answer(text, lang, intents, kb_result, sent, ex)
            parts.append(body)

        # 8. one natural qualifying question (not during transactions / goodbye)
        if not transactional and "goodbye" not in intents:
            nq = self._next_question(st)
            if nq:
                parts.append(QUAL_Q[nq][lang])
                st["awaiting"] = nq
            else:
                st.pop("awaiting", None)
        elif "awaiting" in st and st["awaiting"] != "name":
            st.pop("awaiting", None)
        if ex.name and st.get("awaiting") == "name" and not st.get("pending_slot"):
            st.pop("awaiting", None)

        self._save_state(st)
        reply = "\n\n".join(p for p in parts if p)
        bot_msg = Message(conversation_id=conv.id, role="assistant", content=reply, language=lang, intents=intents,
                          sources=sources, generated_by=generated_by)
        db.add(bot_msg)
        if conv.language != lang and lang in ("en", "hi"):
            conv.language = lang
        db.commit()
        self._maybe_roll_memory()
        return user_msg, bot_msg, TurnResult(reply, lang, intents, sources, self.calls, generated_by, sent, lead_data)

    # -- planner -----------------------------------------------------------
    def _intents(self, text: str, st: dict, ex) -> list[str]:
        intents: list[str] = []
        pending = st.get("pending_slot") or st.get("pending_cancel")
        if pending and YES.match(text):
            intents.append("confirm")
        elif pending and NO.match(text):
            intents.append("decline")
        if st.get("offered_slots") and not pending and self._looks_like_slot_pick(text):
            intents.append("slot_choice")
        if CANCEL.search(text):
            intents.append("cancel_request")
        elif BOOKING.search(text) or RESCHEDULE.search(text) or (
                st.get("awaiting") == "offer" and YES.match(text) and not pending):
            if "slot_choice" not in intents and "confirm" not in intents:
                intents.append("booking_request")
        if GREETING.search(text):
            intents.append("greeting")
        if is_goodbye(text):
            intents.append("goodbye")
        if QUESTION_HINT.search(text) and not {"confirm", "slot_choice"} & set(intents):
            intents.append("knowledge_question")
        if ex.as_dict() and not intents:
            intents.append("provide_info")
        return intents or ["other"]

    def _looks_like_slot_pick(self, text: str) -> bool:
        low = text.lower().strip()
        if re.fullmatch(r"(option|slot|number|no\.?|#)?\s*\d\s*(please|pls)?\.?", low):
            return True
        if any(re.search(rf"(?<![a-z]){re.escape(k)}(?![a-z])", low) for k in ORDINALS):
            return True
        return bool(re.search(r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b|\b\d{1,2}:\d{2}\b|बजे", low))

    def _pick_slot(self, text: str, offered: list[str]) -> str | None:
        if not offered:
            return None
        low = text.lower()
        m = re.search(r"(?<![\d:])([1-9])(?![\d:]|\s*(am|pm|बजे))", low)
        if m and int(m.group(1)) <= len(offered):
            return offered[int(m.group(1)) - 1]
        for k, n in ORDINALS.items():
            if re.search(rf"(?<![a-z]){re.escape(k)}(?![a-z])", low) and n <= len(offered):
                return offered[n - 1]
        tm = TIME_RE.search(low)
        if tm:
            hour = int(tm.group(1))
            minute = int(tm.group(2) or 0)
            ampm = (tm.group(3) or "").replace(".", "")
            if ampm == "pm" and hour < 12:
                hour += 12
            if not ampm and hour < 8:  # "3" or "4:30" without am/pm -> afternoon
                hour += 12
            matches = [s for s in offered if datetime.fromisoformat(s).hour == hour
                       and datetime.fromisoformat(s).minute == minute]
            if len(matches) == 1:
                return matches[0]
        return None

    def _offer_slots(self, st: dict, lang: str) -> str:
        r = self.tool("get_available_slots", limit=4)
        slots = r["data"]["slots"] if r["ok"] else []
        if not slots:
            st.pop("offered_slots", None)
            return self.t("no_slots", lang)
        st["offered_slots"] = slots
        st.pop("pending_slot", None)
        return self.t("slots", lang, slots=self._slot_lines(slots, lang))

    @staticmethod
    def _slot_lines(slots: list[str], lang: str) -> str:
        return "\n".join(f"{i}) {scheduling.format_slot(datetime.fromisoformat(s), lang)}"
                         for i, s in enumerate(slots, 1))

    def _lead_interest(self) -> str | None:
        lead = self.conv.customer.lead
        return lead.interest if lead else None

    def _customer_name(self) -> str | None:
        return self.conv.customer.name

    def _next_question(self, st: dict) -> str | None:
        c = self.conv.customer
        lead = c.lead
        asked = st.setdefault("asked", {})
        for field_name, known in (("name", c.name), ("interest", lead and lead.interest),
                                  ("budget", lead and lead.budget), ("timeline", lead and lead.timeline)):
            if not known and asked.get(field_name, 0) < 2:  # never nag more than twice
                if st.get("awaiting") == field_name and asked.get(field_name, 0) >= 1:
                    continue  # just asked this; let the customer lead
                asked[field_name] = asked.get(field_name, 0) + 1
                return field_name
        has_upcoming = any(a.status == "booked" for a in c.appointments)
        if not has_upcoming and asked.get("offer", 0) < 1 and lead and lead.interest:
            asked["offer"] = 1
            return "offer"
        return None

    # -- answer composition ----------------------------------------------------
    def _compose_answer(self, text, lang, intents, kb_result, sent, ex) -> tuple[str, str]:
        kb = (kb_result or {}).get("data") if kb_result and kb_result.get("ok") else None
        provider = get_provider()
        price_objection = bool(sent and "price" in (sent.get("objections") or []))

        if "knowledge_question" in intents:
            if kb is None:
                return self.t("not_found", lang), "demo-rules"
            if kb["method"] == "empty-knowledge-base":
                return self.t("empty_kb", lang), "demo-rules"
            if not kb["found"]:
                return self.t("not_found", lang), "demo-rules"  # grounded refusal, never sent to the LLM to guess
            if provider:
                try:
                    return self._llm_answer(provider, text, lang, kb["chunks"], sent), provider.label
                except LLMError:
                    body = self._template_answer(text, lang, kb["chunks"], price_objection)
                    return body, "demo-rules (llm-error)"
            return self._template_answer(text, lang, kb["chunks"], price_objection), "demo-rules"

        if "greeting" in intents:
            return self.t("greet", lang), "demo-rules"
        if "provide_info" in intents:
            name = ex.name or self._customer_name()
            return self.t("ack", lang, name_part=f" {name}" if name else ""), "demo-rules"
        return self.t("fallback", lang), "demo-rules"

    def _template_answer(self, text: str, lang: str, chunks: list[dict], price_objection: bool) -> str:
        """Demo mode: quote the most relevant lines of the retrieved chunks (no generation)."""
        from ..services.rag import expand_query, tokenize
        q = set(expand_query(tokenize(text)))
        out = [self.t("price_ack", lang)] if price_objection else []
        out.append(self.t("kb_intro", lang))
        for c in chunks[:2]:
            lines = [l.strip() for l in c["content"].split("\n")[1:] if l.strip()]
            is_course = c["title"].lower().startswith("course:")
            picked = []
            for l in lines:
                key = l.split(":")[0].lower()
                if is_course and key in ("duration", "price", "emi option", "upcoming batches"):
                    picked.append(l)
                elif not is_course and set(tokenize(l)) & q:
                    picked.append(l)
            picked = (picked or lines)[:4]
            title = c["title"].replace("Course: ", "").replace("FAQ: ", "")
            out.append(f"• {title}: " + " ".join(p if p.endswith(".") else p + "." for p in picked))
        return "\n".join(out)

    def _llm_answer(self, provider, text: str, lang: str, chunks: list[dict], sent: dict | None) -> str:
        instr = get_setting(self.db, "agent_instructions")["system_prompt"].format(
            agent_name=self.profile["agent_name"], company_name=self.profile["company_name"])
        c = self.conv.customer
        lead = c.lead
        context = "\n\n".join(f"[Source {i}: {ch['document']} / {ch['title']}]\n{ch['content']}"
                              for i, ch in enumerate(chunks, 1))
        system = (
            f"{instr}\n\nReply language: {'Hindi (Devanagari script)' if lang == 'hi' else 'English'}.\n"
            f"Do NOT ask qualifying questions yourself; the system appends them.\n"
            f"Known customer facts: name={c.name or 'unknown'}, interest={lead.interest if lead else 'unknown'}, "
            f"budget={lead.budget if lead and lead.budget else 'unknown'}, "
            f"timeline={lead.timeline if lead else 'unknown'}.\n"
            f"Earlier conversation summary: {self.conv.memory_summary or 'none'}\n"
            f"Customer sentiment: {sent['label'] if sent else 'unknown'}; suggested approach: "
            f"{sent['recommended_action'] if sent else '-'}\n\n"
            f"KNOWLEDGE BASE CONTEXT (the only allowed source of facts):\n{context}"
        )
        history = [ChatMessage(m.role, m.content) for m in self.conv.messages[-CONTEXT_MESSAGES:]]
        if not history or history[-1].content != text:
            history.append(ChatMessage("user", text))
        return provider.generate(system, history)

    def _maybe_roll_memory(self) -> None:
        """Context-window strategy: keep last CONTEXT_MESSAGES verbatim, compress older turns into a summary."""
        msgs = self.conv.messages
        if len(msgs) <= CONTEXT_MESSAGES + 4:
            return
        older = msgs[:-CONTEXT_MESSAGES]
        topics = sorted({i for m in older if m.role == "user" for i in (m.intents or [])})
        c = self.conv.customer
        lead = c.lead
        self.conv.memory_summary = (
            f"{len(older)} earlier messages. Topics: {', '.join(topics) or 'general'}. "
            f"Customer: {c.name or 'unknown'}; interest {lead.interest if lead else 'unknown'}; "
            f"budget {lead.budget if lead and lead.budget else 'unknown'}; timeline "
            f"{lead.timeline if lead and lead.timeline else 'unknown'}.")
        self.db.commit()


ATTRIBUTE_TERMS = {"price", "fee", "fees", "cost", "duration", "long", "batch", "batches", "start", "starts", "emi",
                   "budget", "कितना", "कितनी", "कितने", "बजट", "लगेगा", "खर्च", "रुपये", "रुपया",
                   "syllabus", "prerequisite", "prerequisites", "certificate", "timing", "schedule", "when", "much",
                   "कीमत", "फीस", "बैच", "अवधि", "kitna", "kitni", "it", "that", "this"}


def _is_attribute_question(text: str) -> bool:
    """True for follow-ups like "what's the price?" that refer to the product already discussed."""
    from ..services.rag import GENERIC, tokenize
    toks = set(tokenize(text)) | set(re.findall(r"\b(it|that|this|much|when)\b", text.lower()))
    content = {t for t in toks if t not in GENERIC}
    return bool(content) and content <= ATTRIBUTE_TERMS


def _brief(name: str, res: dict) -> str:
    d = res.get("data") or {}
    if name == "search_knowledge_base":
        return f"found={d.get('found')} via {d.get('method')} ({len(d.get('chunks', []))} chunks)"
    if name == "qualify_lead":
        return f"score {d.get('score')} {d.get('category')}"
    if name == "analyze_sentiment":
        return f"{d.get('label')} ({d.get('confidence')})"
    if name == "get_available_slots":
        return f"{d.get('count')} slots"
    if name == "book_appointment":
        return f"appointment #{d.get('appointment_id')} booked"
    if name == "update_customer_profile":
        return "changed: " + (", ".join(d.get("changed", {}).keys()) or "nothing")
    if name == "update_crm_record":
        return "changed: " + (", ".join(d.get("changed", {}).keys()) or "nothing")
    return "ok"
