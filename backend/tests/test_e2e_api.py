"""End-to-end business workflow (primary acceptance test) + CRM/analytics/security APIs."""
import csv
import io

from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.database import make_engine
from app.models import Appointment, CallSummary, Customer, SentimentRecord
from app.security import reset_rate_limits
from tests.conftest import say, start


def test_full_sales_workflow(client):
    # STEP 1-2: customer starts a voice conversation, agent greets
    conv = start(client, "en")
    cid = conv["id"]
    assert conv["messages"][0]["role"] == "assistant" and "Nova" in conv["messages"][0]["content"]

    # STEP 3-8: question -> RAG -> grounded answer + qualifying question
    d = say(client, cid, "Hello, I want to learn AI and machine learning. Can you tell me about your courses?")
    msg = d["assistant_message"]
    assert "knowledge_question" in msg["intents"]
    assert msg["sources"] and msg["sources"][0]["document"] == "course_catalog.txt"
    assert "₹45,000" in msg["content"]
    assert "May I know your name?" in msg["content"]
    assert d["sentiment"]["label"] == "interested"

    # STEP 9-10: name, budget, requirements -> profile + score
    say(client, cid, "My name is Rahul")
    say(client, cid, "My budget is around 20,000 and I prefer weekend batches")
    d = say(client, cid, "I want to start next month")
    lead = d["lead"]
    assert d["customer"]["name"] == "Rahul"
    assert lead["budget"] == 20000 and lead["timeline"] == "1-3 months"
    assert "weekend batch" in lead["requirements"]
    score_before = lead["score"]
    assert score_before > 0 and lead["score_reasons"]

    # price objection handled with grounded payment options
    d = say(client, cid, "Honestly that's too expensive for me")
    assert d["sentiment"]["label"] == "hesitant" and "price" in d["sentiment"]["objections"]
    assert "EMI" in d["assistant_message"]["content"]

    # STEP 11-12: appointment request -> real slots offered
    d = say(client, cid, "Can I book a counselling appointment?")
    offered = d["conversation"]["state"]["offered_slots"]
    assert len(offered) == 4 and "1)" in d["assistant_message"]["content"]

    # STEP 13: select + confirm (nothing booked before confirmation)
    d = say(client, cid, "Option 2")
    assert "confirm" in d["assistant_message"]["content"].lower()
    assert client.get("/api/appointments?upcoming=true").json() == []
    d = say(client, cid, "Yes please")
    assert "booked" in d["assistant_message"]["content"]

    # STEP 14: appointment in DB, linked to the lead and conversation
    appts = client.get("/api/appointments?upcoming=true").json()
    assert len(appts) == 1 and appts[0]["start_time"] == offered[1]
    assert appts[0]["customer_name"] == "Rahul" and appts[0]["conversation_id"] == cid
    assert d["lead"]["score"] > score_before  # readiness increased

    # STEP 15-16: end -> summary saved
    say(client, cid, "Thanks, bye")
    ended = client.post(f"/api/conversations/{cid}/end").json()
    s = ended["summary"]
    assert ended["status"] == "ended"
    assert "Rahul" in s["summary"] and s["budget"] == 20000 and "price" in s["objections"]
    assert s["appointment_info"] and s["follow_up_action"]
    assert s["generated_by"] == "demo-rules"

    # STEP 17: CRM + analytics reflect real records
    leads = client.get("/api/leads").json()
    assert len(leads) == 1 and leads[0]["name"] == "Rahul" and leads[0]["upcoming_appointment"]
    a = client.get("/api/analytics/overview").json()
    assert a["totals"]["leads"] == 1 and a["totals"]["appointments"] == 1
    assert a["totals"]["appointment_conversion_rate"] == 1.0
    assert a["popular_products"][0]["product"] == "AI & Machine Learning Professional Program"
    assert any(o["objection"] == "price" for o in a["top_objections"])


def test_hindi_workflow(client):
    conv = start(client, "hi")
    cid = conv["id"]
    assert "नमस्ते" in conv["messages"][0]["content"]
    d = say(client, cid, "मुझे मशीन लर्निंग सीखना है। कोर्स की फीस कितनी है?")
    assert d["assistant_message"]["language"] == "hi" and "₹45,000" in d["assistant_message"]["content"]
    say(client, cid, "मेरा नाम राहुल है")
    d = say(client, cid, "मुझे काउंसलिंग अपॉइंटमेंट बुक करना है")
    assert d["conversation"]["state"]["offered_slots"]
    say(client, cid, "दूसरा")
    d = say(client, cid, "हाँ")
    assert "बुक" in d["assistant_message"]["content"]
    assert len(client.get("/api/appointments?upcoming=true").json()) == 1


def test_decline_does_not_book(client):
    conv = start(client)
    say(client, conv["id"], "My name is Neha. I want to book a counselling session")
    say(client, conv["id"], "1")
    d = say(client, conv["id"], "No")
    assert "haven't booked" in d["assistant_message"]["content"]
    assert client.get("/api/appointments").json() == []


def test_cancel_via_agent(client):
    conv = start(client)
    say(client, conv["id"], "I'm Vikram, please book an appointment")
    say(client, conv["id"], "first")
    say(client, conv["id"], "yes")
    d = say(client, conv["id"], "Please cancel my appointment")
    assert "cancel" in d["assistant_message"]["content"].lower()
    d = say(client, conv["id"], "yes")
    assert "cancelled" in d["assistant_message"]["content"]
    assert client.get("/api/appointments").json()[0]["status"] == "cancelled"


def test_crm_search_filter_update_export_delete(client):
    for name, text in [("Rahul", "I want to learn AI"), ("Meera", "I want to learn cloud devops")]:
        conv = start(client)
        say(client, conv["id"], f"My name is {name}. {text}")
    assert len(client.get("/api/leads").json()) == 2
    assert [l["name"] for l in client.get("/api/leads?q=meer").json()] == ["Meera"]
    assert client.get("/api/leads?category=HOT").json() == []
    lead = client.get("/api/leads?q=rahul").json()[0]
    assert client.patch(f"/api/leads/{lead['id']}", json={"status": "contacted"}).json()["lead"]["status"] == "contacted"
    assert client.patch(f"/api/leads/{lead['id']}", json={"status": "bogus"}).status_code == 422
    rows = list(csv.reader(io.StringIO(client.get("/api/leads/export.csv").content.decode("utf-8-sig"))))
    assert rows[0][1] == "name" and {r[1] for r in rows[1:]} == {"Rahul", "Meera"}
    assert client.delete(f"/api/leads/{lead['id']}").status_code == 200
    assert [l["name"] for l in client.get("/api/leads").json()] == ["Meera"]


def test_delete_lead_cascades(client, db):
    conv = start(client)
    say(client, conv["id"], "My name is Rahul, book an appointment")
    say(client, conv["id"], "1")
    say(client, conv["id"], "yes")
    client.post(f"/api/conversations/{conv['id']}/end")
    cust = conv["customer_id"]
    client.delete(f"/api/leads/{cust}")
    db.expire_all()
    assert db.get(Customer, cust) is None
    assert db.query(Appointment).count() == 0 and db.query(CallSummary).count() == 0
    assert db.query(SentimentRecord).count() == 0


def test_empty_analytics(client):
    a = client.get("/api/analytics/overview").json()
    assert a["totals"]["leads"] == 0 and a["totals"]["average_lead_score"] == 0
    assert a["sentiment_distribution"] == []


def test_invalid_requests(client):
    assert client.post("/api/conversations", json={"language": "fr"}).status_code == 422
    assert client.post("/api/conversations/nope/messages", json={"text": "hi"}).status_code == 404
    conv = start(client)
    assert client.post(f"/api/conversations/{conv['id']}/messages", json={"text": ""}).status_code == 422
    assert client.post(f"/api/conversations/{conv['id']}/messages", json={"text": "x" * 2001}).status_code == 422
    client.post(f"/api/conversations/{conv['id']}/end")
    assert client.post(f"/api/conversations/{conv['id']}/messages", json={"text": "hi"}).status_code == 409
    assert client.post("/api/conversations", json={"customer_id": 9999}).status_code == 404


def test_admin_key_protects_crm(client, monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "s3cret")
    get_settings.cache_clear()
    assert client.get("/api/leads").status_code == 401
    assert client.get("/api/leads", headers={"X-Admin-Key": "wrong"}).status_code == 401
    assert client.get("/api/leads", headers={"X-Admin-Key": "s3cret"}).status_code == 200
    assert client.post("/api/conversations", json={}).status_code == 200  # customer chat stays public
    assert "s3cret" not in client.get("/api/settings", headers={"X-Admin-Key": "s3cret"}).text  # never leaked


def test_rate_limit(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "3")
    get_settings.cache_clear()
    reset_rate_limits()
    codes = [client.post("/api/conversations", json={}).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]


def test_settings_validation(client):
    assert client.put("/api/settings/lead_scoring", json={"weights": {"intent": 50}}).status_code == 422
    ok = {"intent": 40, "budget_fit": 20, "urgency": 10, "product_interest": 15, "readiness": 15}
    assert client.put("/api/settings/lead_scoring", json={"weights": ok}).json()["weights"]["intent"] == 40
    assert client.put("/api/settings/nope", json={}).status_code == 404
    assert client.put("/api/settings/scheduling", json={"start_hour": 18, "end_hour": 10}).status_code == 422


def test_data_persists_across_restart(client):
    conv = start(client)
    say(client, conv["id"], "My name is Persist Test")
    # brand-new engine on the same database file == application restart
    eng = make_engine(get_settings().database_url)
    with sessionmaker(bind=eng)() as s:
        assert s.query(Customer).filter_by(name="Persist Test").count() == 1
    eng.dispose()
