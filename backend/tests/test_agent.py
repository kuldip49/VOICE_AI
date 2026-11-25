"""Agent tools, memory, LLM provider handling."""
import httpx
import pytest

from app.agent.tools import ToolContext, execute_tool
from app.config import Settings
from app.models import AgentToolLog, Customer, CustomerMemory, Message
from app.services import llm
from tests.conftest import say, start


# ---------------- tools
def test_tool_validation_and_permissions(db):
    ctx = ToolContext(db=db)
    r = execute_tool(ctx, "search_knowledge_base", {"query": ""})
    assert not r["ok"] and r["error"]["code"] == "invalid_arguments"
    r = execute_tool(ctx, "drop_table", {"sql": "DROP TABLE customers"})
    assert not r["ok"] and r["error"]["code"] == "tool_not_allowed"
    r = execute_tool(ctx, "retrieve_customer_profile", {"customer_id": 999})
    assert not r["ok"] and r["error"]["code"] == "unknown_customer"
    r = execute_tool(ctx, "update_customer_profile", {"customer_id": 1, "email": "not-an-email"})
    assert not r["ok"] and r["error"]["code"] == "invalid_arguments"
    assert db.query(AgentToolLog).count() == 4  # every attempt is logged
    assert db.query(AgentToolLog).filter_by(success=False).count() == 4


def test_agent_logs_tool_calls(client, db):
    conv = start(client)
    d = say(client, conv["id"], "What is the price of the data science course?")
    tools = [c["tool"] for c in d["tool_calls"]]
    assert "search_knowledge_base" in tools and "analyze_sentiment" in tools and "qualify_lead" in tools
    assert d["assistant_message"]["sources"][0]["title"] == "Course: Data Science with Python"
    assert "₹28,000" in d["assistant_message"]["content"]
    assert d["assistant_message"]["generated_by"] == "demo-rules"  # honest label, no LLM configured
    logs = client.get(f"/api/conversations/{conv['id']}/tool-logs").json()
    assert {l["tool"] for l in logs} >= {"search_knowledge_base", "analyze_sentiment", "qualify_lead"}


def test_not_in_knowledge_base_answer(client):
    conv = start(client)
    d = say(client, conv["id"], "Do you offer a blockchain course?")
    assert "not in our knowledge base" in d["assistant_message"]["content"]
    assert d["assistant_message"]["sources"] == []


# ---------------- memory
def test_contextual_memory_within_conversation(client):
    conv = start(client)
    cid = conv["id"]
    say(client, cid, "My name is Rahul")
    say(client, cid, "I want to learn artificial intelligence")
    d = say(client, cid, "My budget is around 20,000")
    assert d["customer"]["name"] == "Rahul"
    assert d["lead"]["interest"] == "AI & Machine Learning Professional Program"
    assert d["lead"]["budget"] == 20000
    # follow-up without naming the course uses remembered interest
    d = say(client, cid, "What is the price?")
    assert "₹45,000" in d["assistant_message"]["content"]
    # the agent never asks again for things it knows
    assert "your name" not in d["assistant_message"]["content"].lower()
    assert "budget" not in d["assistant_message"]["content"].lower()


def test_bare_answer_to_question_is_understood(client):
    conv = start(client)
    d = say(client, conv["id"], "Tell me about your courses")
    assert "May I know your name?" in d["assistant_message"]["content"]
    d = say(client, conv["id"], "Priya")
    assert d["customer"]["name"] == "Priya"


def test_persistent_memory_across_conversations_and_deletion(client, db):
    conv = start(client)
    say(client, conv["id"], "My name is Rahul and my email is rahul@example.com")
    cust = conv["customer_id"]
    mems = {m.key: m.value for m in db.query(CustomerMemory).filter_by(customer_id=cust)}
    assert mems["name"] == "Rahul" and mems["email"] == "rahul@example.com"
    conv2 = start(client, customer_id=cust)
    assert "Rahul" in conv2["messages"][0]["content"]
    detail = client.get(f"/api/leads/{cust}").json()
    assert {m["key"] for m in detail["memories"]} >= {"name", "email"}
    assert client.delete(f"/api/customers/{cust}/memories").json()["deleted"] >= 2
    assert client.get(f"/api/leads/{cust}").json()["memories"] == []


def test_context_window_rolls_summary(client, db):
    conv = start(client)
    for i in range(8):
        say(client, conv["id"], f"What is the refund policy? ({i})")
    d = client.get(f"/api/conversations/{conv['id']}").json()
    from app.models import Conversation
    c = db.get(Conversation, conv["id"])
    db.refresh(c)
    assert c.memory_summary and "earlier messages" in c.memory_summary
    assert d["message_count"] == 17


# ---------------- LLM providers
class FakeLLM:
    label = "fake:test"

    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def generate(self, system, messages):
        self.calls.append((system, messages))
        if self.fail:
            raise llm.LLMError("boom")
        return "The AI & ML program costs ₹45,000."


def test_llm_answer_is_grounded_and_labelled(client):
    fake = FakeLLM()
    llm.set_provider_override(fake)
    conv = start(client)
    d = say(client, conv["id"], "How much is the AI and machine learning course?")
    assert d["assistant_message"]["generated_by"] == "fake:test"
    system = fake.calls[0][0]
    assert "KNOWLEDGE BASE CONTEXT" in system and "Price: ₹45,000" in system  # retrieved chunk injected


def test_llm_failure_falls_back_to_labelled_demo(client):
    llm.set_provider_override(FakeLLM(fail=True))
    conv = start(client)
    d = say(client, conv["id"], "What is the refund policy?")
    assert d["assistant_message"]["generated_by"] == "demo-rules (llm-error)"
    assert "refund" in d["assistant_message"]["content"].lower()


def test_llm_not_called_when_kb_has_no_answer(client):
    fake = FakeLLM()
    llm.set_provider_override(fake)
    conv = start(client)
    d = say(client, conv["id"], "Do you offer a blockchain course?")
    assert fake.calls == []  # never let the model guess
    assert "not in our knowledge base" in d["assistant_message"]["content"]


def test_gemini_provider_parsing_and_errors():
    s = Settings(gemini_api_key="test-key", llm_provider="gemini")
    ok = httpx.MockTransport(lambda req: httpx.Response(200, json={
        "candidates": [{"content": {"parts": [{"text": "Hello from Gemini"}]}}]}))
    assert llm.GeminiProvider(s, transport=ok).generate("sys", [llm.ChatMessage("user", "hi")]) == "Hello from Gemini"
    bad = httpx.MockTransport(lambda req: httpx.Response(500, json={}))
    with pytest.raises(llm.LLMError):
        llm.GeminiProvider(s, transport=bad).generate("sys", [llm.ChatMessage("user", "hi")])

    def boom(req):
        raise httpx.ConnectError("no network")
    with pytest.raises(llm.LLMError):
        llm.GeminiProvider(s, transport=httpx.MockTransport(boom)).generate("s", [llm.ChatMessage("user", "x")])


def test_grok_provider_parsing_auth_and_auto_selection():
    llm.set_provider_override(None)
    s = Settings(grok_api_key="test-key", llm_provider="auto")
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "Hello from Grok"}}]})

    transport = httpx.MockTransport(respond)
    selected = llm.get_provider(s)
    assert isinstance(selected, llm.GrokProvider)
    provider = llm.GrokProvider(s, transport=transport)
    assert provider.generate("system prompt", [llm.ChatMessage("user", "hi")]) == "Hello from Grok"
    assert requests[0].url == "https://api.x.ai/v1/chat/completions"
    assert requests[0].headers["Authorization"] == "Bearer test-key"
    assert requests[0].read()  # request was sent with a JSON body
    assert llm.provider_status(s)["active"] == "grok:grok-4.7"
    assert llm.provider_status(s)["grok_key_present"] is True


def test_grok_provider_errors_and_missing_key():
    s = Settings(grok_api_key="test-key", llm_provider="grok")
    bad = httpx.MockTransport(lambda req: httpx.Response(500, json={}))
    with pytest.raises(llm.LLMError):
        llm.GrokProvider(s, transport=bad).generate("sys", [llm.ChatMessage("user", "hi")])

    assert llm.get_provider(Settings(grok_api_key="", llm_provider="grok")) is None


def test_missing_api_key_means_demo_mode():
    llm.set_provider_override(None)
    s = Settings(gemini_api_key="", llm_provider="gemini")
    assert llm.get_provider(s) is None
    assert llm.provider_status(Settings(gemini_api_key="", llm_provider="demo"))["mode"] == "demo"


def test_ollama_provider_parsing():
    s = Settings(llm_provider="ollama")
    t = httpx.MockTransport(lambda req: httpx.Response(200, json={"message": {"content": "local answer"}}))
    assert llm.OllamaProvider(s, transport=t).generate("sys", [llm.ChatMessage("user", "hi")]) == "local answer"
