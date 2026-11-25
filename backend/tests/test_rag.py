"""RAG retrieval + knowledge-base API tests."""
import io

from pypdf import PdfWriter

from app.models import KnowledgeDocument
from app.services import rag


def test_retrieves_ai_course(db):
    r = rag.retrieve(db, "Tell me about your artificial intelligence and machine learning courses")
    assert r["found"]
    assert "AI & Machine Learning" in r["chunks"][0].title
    assert r["chunks"][0].document == "course_catalog.txt"


def test_retrieves_refund_policy(db):
    r = rag.retrieve(db, "What is the refund policy?")
    assert r["found"] and r["chunks"][0].title == "Refund Policy"


def test_unknown_topic_not_found(db):
    r = rag.retrieve(db, "Do you offer a blockchain course?")
    assert not r["found"]
    assert "blockchain" in r["unknown_terms"]


def test_hindi_query_expansion(db):
    r = rag.retrieve(db, "रिफंड के नियम क्या हैं?")
    assert r["found"] and r["chunks"][0].title == "Refund Policy"


def test_empty_knowledge_base(db):
    for d in db.query(KnowledgeDocument).all():
        db.delete(d)
    db.commit()
    rag.invalidate_index()
    r = rag.retrieve(db, "price of AI course")
    assert r["method"] == "empty-knowledge-base" and not r["found"]


def test_price_lookup_grounded(db):
    assert rag.find_product_price(db, "AI & Machine Learning Professional Program") == 45000
    assert rag.find_product_price(db, "Nonexistent course") is None


def test_upload_txt_then_retrieve_then_delete(client):
    content = b"## Robotics Bootcamp\nPrice: \xe2\x82\xb950,000\nDuration: 10 weeks of hands-on robotics."
    r = client.post("/api/knowledge/documents", files={"file": ("robotics.txt", content, "text/plain")})
    assert r.status_code == 200 and r.json()["status"] == "ready" and r.json()["chunk_count"] == 1
    s = client.post("/api/knowledge/search", json={"query": "robotics bootcamp duration"}).json()
    assert s["found"] and s["results"][0]["document"] == "robotics.txt"
    doc_id = r.json()["id"]
    assert client.delete(f"/api/knowledge/documents/{doc_id}").status_code == 200
    s = client.post("/api/knowledge/search", json={"query": "robotics bootcamp"}).json()
    assert not s["found"]


def test_upload_pdf_without_text_is_marked_failed(client):
    buf = io.BytesIO()
    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    w.write(buf)
    r = client.post("/api/knowledge/documents", files={"file": ("blank.pdf", buf.getvalue(), "application/pdf")})
    assert r.status_code == 200
    assert r.json()["status"] == "failed" and "No extractable text" in r.json()["error"]


def test_upload_validation(client):
    assert client.post("/api/knowledge/documents",
                       files={"file": ("x.exe", b"MZ...", "application/octet-stream")}).status_code == 415
    assert client.post("/api/knowledge/documents",
                       files={"file": ("fake.pdf", b"hello", "application/pdf")}).status_code == 415
    big = b"a" * (5 * 1024 * 1024 + 10)
    assert client.post("/api/knowledge/documents", files={"file": ("big.txt", big, "text/plain")}).status_code == 413
    assert client.post("/api/knowledge/documents", files={"file": ("e.txt", b"", "text/plain")}).status_code == 422
