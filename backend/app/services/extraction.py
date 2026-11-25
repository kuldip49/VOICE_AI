"""Lead information extraction from customer messages (English + Hindi/Hinglish).

Rule-based on purpose: deterministic, testable, free, and it never invents data.
Anything not explicitly said stays None ("unknown").
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")

NOT_NAMES = {"interested", "looking", "a", "an", "from", "working", "student", "planning", "trying", "here", "not",
             "very", "just", "currently", "also", "so", "fine", "good", "ok", "okay", "sure", "ready", "thinking",
             "learning", "new", "confused", "available", "free", "busy", "unable", "able", "going", "calling",
             "the", "in", "on", "at", "graduate", "fresher", "beginner", "engineer", "developer", "software"}

NAME_PATTERNS = [
    re.compile(r"\bmy name is\s+([A-Za-z][A-Za-z'-]{1,30}(?:\s+[A-Za-z][A-Za-z'-]{1,30})?)", re.I),
    re.compile(r"\b(?i:i am|i'm|im|this is)\s+([A-Z][a-z'-]{1,30}(?:\s+[A-Z][a-z'-]{1,30})?)\b"),
    re.compile(r"\b(?:call me)\s+([A-Za-z][A-Za-z'-]{1,30})", re.I),
    re.compile(r"\bmera naam\s+([A-Za-z][A-Za-z'-]{1,30})", re.I),
    re.compile(r"मेरा नाम\s+([ऀ-ॿ]+(?:\s+[ऀ-ॿ]+)?)\s*(?:है|हैं)?"),
]

BUDGET_CONTEXT = re.compile(r"budget|afford|spend|invest|pay|₹|\brs\.?|rupees|inr|बजट|खर्च|रुपये|रुपए|paise|kharch",
                            re.I)
AMOUNT_RE = re.compile(
    r"(?:₹|rs\.?|inr)?\s*(\d{1,3}(?:,\d{2,3})+|\d+(?:\.\d+)?)\s*"
    r"(k\b|thousand|hazaar|hazar|हज़ार|हजार|lakh|lac|लाख)?", re.I)

TIMELINE_RULES = [
    (re.compile(r"\b(immediately|asap|right away|right now|this week|today|tomorrow)\b|तुरंत|अभी|इस हफ्ते|abhi", re.I),
     "immediately"),
    (re.compile(r"\b(this month|within (a|one|1) month|in (a|one|1) month|next week|next batch|upcoming batch)\b"
                r"|इस महीने|is mahine", re.I), "within 1 month"),
    (re.compile(r"\b(next month|in (2|3|two|three) months|1-3 months|couple of months|january|december)\b"
                r"|अगले महीने|agle mahine", re.I), "1-3 months"),
    (re.compile(r"\b(next year|in (6|six) months|later|not sure when|someday|after my exams)\b|अगले साल", re.I),
     "3+ months"),
]

AUTHORITY_RULES = [
    (re.compile(r"\b(parents?|father|mother|dad|mom)\b.*\b(decide|pay|approve|ask|permission)|"
                r"\b(ask|discuss with|check with) my (parents?|father|mother|dad|mom)|माता|पिता|papa", re.I),
     "parents decide"),
    (re.compile(r"\b(company|employer|manager|office)\b.*\b(sponsor|pay|approve|reimburse)", re.I),
     "employer sponsored / approval needed"),
    (re.compile(r"\b(i (will|can) (decide|pay)|my (own )?decision|i'll pay|self[- ]funded)\b", re.I),
     "self (decision maker)"),
]

REQUIREMENT_RULES = {
    "weekend batch": re.compile(r"weekend|saturday|sunday|शनिवार|रविवार", re.I),
    "weekday evening batch": re.compile(r"weekday|evening|after office|after work|शाम", re.I),
    "beginner friendly": re.compile(r"beginner|no experience|from scratch|non[- ]tech|शुरुआत", re.I),
    "career switch / job": re.compile(r"\bjob\b|career|placement|switch|नौकरी|naukri", re.I),
    "EMI / installments": re.compile(r"\bemi\b|installment|instalment|किश्त", re.I),
    "certificate": re.compile(r"certificat|सर्टिफिकेट", re.I),
    "hindi support": re.compile(r"in hindi|हिंदी में|hindi me", re.I),
}

INTENT_HIGH = re.compile(r"\b(enrol+|join|sign ?up|register|buy|purchase|admission|pay now|ready to start|book|"
                         r"appointment|counsel+ing|call me|demo class)\b|दाखिला|एडमिशन|जुड़ना|बुक", re.I)
INTENT_MED = re.compile(r"\b(price|fee|fees|cost|emi|batch|start date|when does|discount|duration|syllabus|"
                        r"refund)\b|कीमत|फीस|बैच|kitna|kitni", re.I)


@dataclass
class Extracted:
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    budget: int | None = None
    interest: str | None = None
    timeline: str | None = None
    authority: str | None = None
    requirements: list[str] = field(default_factory=list)
    intent_signal: str | None = None  # high|medium|low

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v not in (None, [], "")}


def _parse_amount(num: str, unit: str | None) -> int | None:
    try:
        value = float(num.replace(",", ""))
    except ValueError:
        return None
    unit = (unit or "").lower()
    if unit in ("k", "thousand", "hazaar", "hazar", "हज़ार", "हजार"):
        value *= 1_000
    elif unit in ("lakh", "lac", "लाख"):
        value *= 100_000
    if value < 500 or value > 10_000_000:  # ignore years, ages, "6 months" etc.
        return None
    return int(value)


def extract_budget(text: str) -> int | None:
    if not BUDGET_CONTEXT.search(text):
        return None
    for m in AMOUNT_RE.finditer(text):
        amt = _parse_amount(m.group(1), m.group(2))
        if amt:
            return amt
    return None


def extract_interest(text: str, products: dict[str, list[str]]) -> str | None:
    """Pick the product whose matched keyword is longest (most specific)."""
    low = text.lower()
    best: tuple[int, str] | None = None
    for product, keywords in products.items():
        for kw in keywords:
            pattern = rf"(?<![a-z]){re.escape(kw.lower())}(?![a-z])"
            if re.search(pattern, low):
                if best is None or len(kw) > best[0]:
                    best = (len(kw), product)
    return best[1] if best else None


def extract(text: str, products: dict[str, list[str]]) -> Extracted:
    e = Extracted()
    for pat in NAME_PATTERNS:
        m = pat.search(text)
        if m:
            candidate = m.group(1).strip()
            words = candidate.split()
            while words and words[-1].lower() in NOT_NAMES | {"and", "i", "want", "from", "hai", "है", "हैं", "हूँ", "हूं"}:
                words.pop()
            if words and words[0].lower() not in NOT_NAMES:
                e.name = " ".join(w[:1].upper() + w[1:] for w in words)
                break
    if m := EMAIL_RE.search(text):
        e.email = m.group(0).lower()
    if m := PHONE_RE.search(text):
        e.phone = re.sub(r"[\s-]", "", m.group(0))
    e.budget = extract_budget(text)
    e.interest = extract_interest(text, products)
    for pat, label in TIMELINE_RULES:
        if pat.search(text):
            e.timeline = label
            break
    for pat, label in AUTHORITY_RULES:
        if pat.search(text):
            e.authority = label
            break
    e.requirements = [label for label, pat in REQUIREMENT_RULES.items() if pat.search(text)]
    if INTENT_HIGH.search(text):
        e.intent_signal = "high"
    elif INTENT_MED.search(text):
        e.intent_signal = "medium"
    return e
