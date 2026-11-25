"""Lexicon-based sentiment + objection detection (English, Hindi, Hinglish).

Labels: positive, neutral, negative, frustrated, interested, hesitant.
Sentiment describes HOW the customer feels; it is deliberately separate from purchase intent
(a customer can be frustrated but still want to buy, or polite but not interested).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

LEXICON: dict[str, list[str]] = {
    "frustrated": [r"waste of time", r"useless", r"ridiculous", r"not helpful", r"again and again", r"annoy",
                   r"frustrat", r"fed up", r"worst", r"stop calling", r"bakwas", r"बकवास", r"परेशान", r"!!+"],
    "negative": [r"\bbad\b", r"not good", r"disappoint", r"don'?t like", r"not interested", r"poor", r"scam",
                 r"fake", r"unhappy", r"बुरा", r"पसंद नहीं", r"नहीं चाहिए"],
    "hesitant": [r"too (expensive|costly|much)", r"expensive", r"costly", r"can'?t afford", r"not sure", r"maybe",
                 r"think about it", r"let me think", r"later", r"confused", r"worried", r"hesita", r"महंगा",
                 r"mehenga", r"mehnga", r"सोच", r"पता नहीं", r"शायद"],
    "interested": [r"interested", r"want to (learn|join|enrol|know)", r"tell me more", r"sounds (good|great|interesting)",
                   r"\benrol", r"\bjoin\b", r"\bbook\b", r"how (do|can) i (join|start|register)", r"excited",
                   r"सीखना", r"जानना", r"दिलचस्पी", r"seekhna", r"chahta", r"chahti", r"चाहता", r"चाहती"],
    "positive": [r"\bgreat\b", r"\bthanks?\b", r"thank you", r"awesome", r"perfect", r"\bnice\b", r"helpful",
                 r"excellent", r"\blove\b", r"धन्यवाद", r"शुक्रिया", r"बढ़िया", r"अच्छा", r"dhanyavad", r"badhiya"],
}

OBJECTIONS: dict[str, list[str]] = {
    "price": [r"expensive", r"costly", r"too (much|high)", r"can'?t afford", r"cheaper", r"budget is (low|less|tight)",
              r"महंगा", r"mehenga", r"mehnga", r"discount"],
    "time": [r"no time", r"busy", r"working (full|long)", r"time commitment", r"समय नहीं"],
    "uncertainty": [r"not sure", r"think about it", r"let me think", r"confused", r"सोच", r"पता नहीं"],
    "trust": [r"scam", r"fake", r"guarantee", r"legit", r"reviews?"],
    "authority": [r"ask my (parents|father|mother|manager|boss)", r"parents? will decide", r"discuss with"],
}

ACTIONS = {
    "price": "Explain EMI options, early-bird and group discounts, or suggest a lower-priced starter course.",
    "time": "Highlight weekend batches and 12-month access to recordings.",
    "uncertainty": "Offer a free counselling session or the Saturday demo class to reduce uncertainty.",
    "trust": "Share verifiable facts (certificate, mentor experience) and the no-job-guarantee policy honestly.",
    "authority": "Offer a joint counselling call that includes the decision maker.",
    "frustrated": "Apologise, answer directly and briefly, and offer a human counsellor callback.",
    "negative": "Acknowledge the concern, ask what is missing, avoid pushing.",
    "interested": "Answer clearly, then ask one qualifying question and offer a counselling appointment.",
    "positive": "Keep momentum: confirm needs and propose a next step (counselling slot).",
    "hesitant": "Address the concern with facts from the knowledge base and offer a low-commitment next step.",
    "neutral": "Continue discovery: ask about goals, background or timeline.",
}

PRIORITY = ["frustrated", "negative", "hesitant", "interested", "positive"]


@dataclass
class SentimentResult:
    label: str
    confidence: float
    explanation: str
    recommended_action: str
    objections: list[str] = field(default_factory=list)


def analyze(text: str) -> SentimentResult:
    low = text.lower()
    hits: dict[str, list[str]] = {}
    for label, pats in LEXICON.items():
        found = [p for p in pats if re.search(p, low)]
        if found:
            hits[label] = found
    objections = [o for o, pats in OBJECTIONS.items() if any(re.search(p, low) for p in pats)]

    if not hits:
        label = "neutral"
        conf = 0.6
        explanation = "No clear emotional or intent cues detected."
    else:
        label = next(l for l in PRIORITY if l in hits)
        n = len(hits[label])
        # mixed signals reduce confidence
        conf = min(0.95, 0.6 + 0.12 * n - 0.08 * (len(hits) - 1))
        cues = ", ".join(f'"{re.sub(r"[()?|^$+*]", "", p.replace(chr(92) + "b", "")).replace(chr(39), "")}"'
                         for p in hits[label][:3])
        explanation = f"Detected {label} cues: {cues}."
        if len(hits) > 1:
            others = ", ".join(l for l in hits if l != label)
            explanation += f" Mixed signals also present ({others})."
    if objections:
        explanation += f" Objection(s): {', '.join(objections)}."
        action = ACTIONS[objections[0]]
    else:
        action = ACTIONS[label]
    return SentimentResult(label, round(max(conf, 0.5), 2), explanation, action, objections)
