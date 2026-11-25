"""Unit tests: extraction, lead scoring, sentiment, chunking."""
from app.services import extraction, rag, scoring, sentiment
from app.services.settings_store import DEFAULTS

PRODUCTS = DEFAULTS["business_profile"]["products"]
CFG = DEFAULTS["lead_scoring"]


# ---------------- extraction
def test_extract_name_budget_interest_english():
    e = extraction.extract("My name is Rahul and I want to learn AI. My budget is around 20,000", PRODUCTS)
    assert e.name == "Rahul"
    assert e.budget == 20000
    assert e.interest == "AI & Machine Learning Professional Program"


def test_extract_does_not_invent():
    e = extraction.extract("I am interested in your courses", PRODUCTS)
    assert e.name is None and e.budget is None and e.email is None and e.phone is None


def test_extract_contacts_and_timeline():
    e = extraction.extract("Reach me at rahul.k@example.com or +91 98765 43210, I want to start this month", PRODUCTS)
    assert e.email == "rahul.k@example.com"
    assert e.phone == "+919876543210"
    assert e.timeline == "within 1 month"


def test_extract_budget_units_and_hindi():
    assert extraction.extract_budget("my budget is 20k") == 20000
    assert extraction.extract_budget("budget 1.5 lakh") == 150000
    assert extraction.extract_budget("मेरा बजट 20 हज़ार है") == 20000
    assert extraction.extract_budget("the course is 6 months") is None  # no budget context


def test_extract_hindi_name_strips_verb():
    assert extraction.extract("मेरा नाम राहुल है", PRODUCTS).name == "राहुल"


def test_interest_prefers_most_specific_keyword():
    assert extraction.extract_interest("I want generative ai and llm skills", PRODUCTS) == \
        "Generative AI & LLM Engineering"
    assert extraction.extract_interest("I said hi to my friend", PRODUCTS) is None  # 'ai' inside words ignored


# ---------------- scoring
def test_score_hot_lead():
    r = scoring.score_lead(intent_level="high", budget=50000, product_price=45000, timeline="immediately",
                           interest="X", has_contact=True, has_appointment=True, config=CFG)
    assert r.score == 100 and r.category == "HOT"
    assert len(r.reasons) == 5


def test_score_unknowns_are_zero():
    r = scoring.score_lead(intent_level="unknown", budget=None, product_price=None, timeline=None, interest=None,
                           has_contact=False, has_appointment=False, config=CFG)
    assert r.score == 0 and r.category == "COLD"
    assert all("+0" in x for x in r.reasons)


def test_score_budget_mismatch_is_explained():
    r = scoring.score_lead(intent_level="medium", budget=20000, product_price=45000, timeline="1-3 months",
                           interest="AI", has_contact=False, has_appointment=False, config=CFG)
    assert r.breakdown["budget_fit"] == 6  # 44% of price -> 0.3 * 20
    assert any("₹20,000 vs price ₹45,000" in x for x in r.reasons)
    assert r.category == "WARM"  # 18 + 6 + 10 + 15 = 49


def test_score_weights_configurable():
    cfg = {**CFG, "weights": {"intent": 100, "budget_fit": 0, "urgency": 0, "product_interest": 0, "readiness": 0}}
    r = scoring.score_lead(intent_level="high", budget=None, product_price=None, timeline=None, interest=None,
                           has_contact=False, has_appointment=False, config=cfg)
    assert r.score == 100


# ---------------- sentiment
def test_sentiment_price_hesitation():
    r = sentiment.analyze("Your course is too expensive.")
    assert r.label == "hesitant"
    assert "price" in r.objections
    assert "EMI" in r.recommended_action


def test_sentiment_frustrated_and_interested_and_neutral():
    assert sentiment.analyze("This is useless, waste of time!!").label == "frustrated"
    assert sentiment.analyze("I'm interested, tell me more").label == "interested"
    assert sentiment.analyze("My name is Rahul").label == "neutral"


def test_sentiment_hindi():
    r = sentiment.analyze("यह कोर्स बहुत महंगा है")
    assert r.label == "hesitant" and "price" in r.objections


def test_sentiment_is_not_intent():
    # polite but explicitly not buying -> negative sentiment, no interest
    assert sentiment.analyze("Thanks, but I'm not interested").label == "negative"


# ---------------- chunking
def test_chunking_by_section_and_size():
    text = "## A\nline one\n\n## B\n" + ("word " * 400)
    chunks = rag.chunk_text(text)
    assert chunks[0][0] == "A"
    assert all(len(c) <= rag.MAX_CHUNK_CHARS + 50 for _, c in chunks)
    assert len(chunks) >= 3
