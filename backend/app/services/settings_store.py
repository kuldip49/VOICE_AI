"""Editable business settings stored in the app_settings table, with sensible defaults.

Another company can re-use the platform by editing these values in the Settings page
and replacing the knowledge-base documents.
"""
from copy import deepcopy

from sqlalchemy.orm import Session

from ..models import AppSetting

DEFAULTS: dict[str, dict] = {
    "business_profile": {
        "company_name": "TechNova Academy",
        "description": "Online live training in software development, data science, cloud and AI/ML.",
        "agent_name": "Nova",
        "product_noun": "course",
        "contact_email": "admissions@technova-academy.example",
        "contact_phone": "+91 80 4000 1234",
        # Keywords used to recognise product interest in customer messages -> canonical product name.
        "products": {
            "AI & Machine Learning Professional Program": ["ai", "artificial intelligence", "machine learning", "ml",
                                                           "deep learning", "एआई", "मशीन लर्निंग", "आर्टिफिशियल"],
            "Generative AI & LLM Engineering": ["generative ai", "genai", "gen ai", "llm", "chatgpt", "rag",
                                                "ai agents", "prompt engineering"],
            "Data Science with Python": ["data science", "data analytics", "data analyst", "डेटा साइंस", "analytics"],
            "Full-Stack Web Development (MERN)": ["web development", "full stack", "full-stack", "mern", "react",
                                                  "frontend", "backend", "वेब डेवलपमेंट"],
            "Python Programming Foundations": ["python basics", "python foundations", "learn python", "beginner",
                                               "पायथन"],
            "Cloud & DevOps Engineering": ["cloud", "devops", "aws", "kubernetes", "docker", "क्लाउड"],
        },
    },
    "agent_instructions": {
        "system_prompt": (
            "You are {agent_name}, a friendly, concise sales advisor for {company_name}. "
            "Answer ONLY from the knowledge-base context provided. Never invent prices, dates, discounts or policies. "
            "If the context does not contain the answer, say it is not in the knowledge base and offer a counselling call. "
            "Ask at most one qualifying question per reply. Keep replies under 90 words because they are spoken aloud. "
            "Never promise job guarantees."
        ),
    },
    "scheduling": {
        "working_days": [0, 1, 2, 3, 4, 5],  # Monday=0 ... Saturday=5
        "start_hour": 10,
        "end_hour": 18,
        "slot_minutes": 30,
        "days_ahead": 7,
        "min_notice_minutes": 60,
    },
    "lead_scoring": {
        # Max points per criterion; total = 100. Edit to change the formula.
        "weights": {"intent": 30, "budget_fit": 20, "urgency": 20, "product_interest": 15, "readiness": 15},
        "hot_threshold": 70,
        "warm_threshold": 40,
    },
    "voice": {"default_language": "en-IN", "speech_rate": 1.0, "auto_speak": True},
}


def get_setting(db: Session, key: str) -> dict:
    row = db.get(AppSetting, key)
    base = deepcopy(DEFAULTS.get(key, {}))
    if row:
        base.update(row.value)
    return base


def set_setting(db: Session, key: str, value: dict) -> dict:
    if key not in DEFAULTS:
        raise KeyError(key)
    merged = get_setting(db, key)
    merged.update(value)
    row = db.get(AppSetting, key)
    if row:
        row.value = merged
    else:
        db.add(AppSetting(key=key, value=merged))
    db.commit()
    return merged


def all_settings(db: Session) -> dict:
    return {k: get_setting(db, k) for k in DEFAULTS}
