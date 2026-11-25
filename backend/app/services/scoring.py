"""Transparent lead scoring (0-100).

score = intent + budget_fit + urgency + product_interest + readiness
Each criterion has a configurable maximum (Settings -> lead_scoring.weights) and every point
awarded comes with a human-readable reason that is stored on the lead.
"""
from __future__ import annotations

from dataclasses import dataclass

INTENT_FRACTION = {"high": 1.0, "medium": 0.6, "low": 0.3, "unknown": 0.0}
URGENCY_FRACTION = {"immediately": 1.0, "within 1 month": 0.85, "1-3 months": 0.5, "3+ months": 0.2}


@dataclass
class ScoreResult:
    score: int
    category: str
    breakdown: dict
    reasons: list[str]


def score_lead(*, intent_level: str, budget: int | None, product_price: int | None, timeline: str | None,
               interest: str | None, has_contact: bool, has_appointment: bool, config: dict) -> ScoreResult:
    w = config["weights"]
    breakdown: dict[str, int] = {}
    reasons: list[str] = []

    # 1. Purchase intent
    f = INTENT_FRACTION.get(intent_level or "unknown", 0.0)
    breakdown["intent"] = round(w["intent"] * f)
    reasons.append(f"Intent {intent_level or 'unknown'}: +{breakdown['intent']}/{w['intent']}")

    # 2. Budget fit (compares stated budget with the KB price of the product of interest)
    if budget is None:
        breakdown["budget_fit"] = 0
        reasons.append(f"Budget unknown: +0/{w['budget_fit']}")
    elif product_price is None:
        breakdown["budget_fit"] = round(w["budget_fit"] * 0.5)
        reasons.append(f"Budget ₹{budget:,} stated, product price unknown: +{breakdown['budget_fit']}/{w['budget_fit']}")
    else:
        ratio = budget / product_price
        frac = 1.0 if ratio >= 1 else 0.6 if ratio >= 0.7 else 0.3 if ratio >= 0.4 else 0.1
        breakdown["budget_fit"] = round(w["budget_fit"] * frac)
        reasons.append(f"Budget ₹{budget:,} vs price ₹{product_price:,} ({ratio:.0%}): "
                       f"+{breakdown['budget_fit']}/{w['budget_fit']}")

    # 3. Urgency
    f = URGENCY_FRACTION.get(timeline or "", 0.0)
    breakdown["urgency"] = round(w["urgency"] * f)
    reasons.append(f"Timeline {timeline or 'unknown'}: +{breakdown['urgency']}/{w['urgency']}")

    # 4. Product interest
    breakdown["product_interest"] = w["product_interest"] if interest else 0
    reasons.append(f"Interest {interest or 'unknown'}: +{breakdown['product_interest']}/{w['product_interest']}")

    # 5. Readiness: contact details shared + appointment booked
    r = (0.5 if has_contact else 0) + (0.5 if has_appointment else 0)
    breakdown["readiness"] = round(w["readiness"] * r)
    reasons.append(f"Readiness (contact {'yes' if has_contact else 'no'}, appointment "
                   f"{'yes' if has_appointment else 'no'}): +{breakdown['readiness']}/{w['readiness']}")

    total = max(0, min(100, sum(breakdown.values())))
    category = "HOT" if total >= config["hot_threshold"] else "WARM" if total >= config["warm_threshold"] else "COLD"
    return ScoreResult(total, category, breakdown, reasons)
