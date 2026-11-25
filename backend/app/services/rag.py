"""Retrieval-Augmented Generation (RAG) pipeline.

Stages:
  1. extract_text()   - read TXT / PDF bytes into plain text
  2. chunk_text()     - split into meaningful chunks (by "## " section, then by size)
  3. ingest_document()- store document + chunks (+ embeddings when a provider is configured)
  4. retrieve()       - rank chunks for a query and return the best ones with source references

Retrieval strategy:
  * Default (free, offline): BM25 keyword ranking with a small synonym / Hindi->English expansion.
  * Optional: if chunk embeddings exist (Gemini key configured), semantic cosine similarity
    is blended with BM25 (hybrid retrieval).
The BM25 index is rebuilt lazily whenever the set of chunks changes.
"""
from __future__ import annotations

import io
import math
import re
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import KnowledgeChunk, KnowledgeDocument

MAX_CHUNK_CHARS = 1200
TOKEN_RE = re.compile(r"[a-z0-9₹]+|[ऀ-ॿ]+")

STOPWORDS = set("""a an the and or of to in on for with is are was were be been it this that these those i you we
they he she me my your our us can could would should do does did have has had what which who whom how when where why
about tell please want like know any some there their them from at by as if so not no yes hi hello hey also just
will shall may might than then too very much more most get give need am im i'm let me okay ok""".split())
STOPWORDS.update("यह बताओ बताइए में का की के क्या है हैं मुझे आप".split())

# Query expansion: synonyms + common Hindi words mapped to English KB vocabulary.
SYNONYMS: dict[str, list[str]] = {
    "ai": ["artificial", "intelligence"], "ml": ["machine", "learning"],
    "price": ["fee", "cost", "₹"], "fee": ["price"], "fees": ["price"], "cost": ["price"],
    "budget": ["price", "fee", "cost"], "बजट": ["price", "fee", "cost"],
    "कितना": ["price", "fee", "cost"], "कितनी": ["price", "fee", "cost"],
    "कितने": ["price", "fee", "cost"], "लगेगा": ["cost", "price"], "खर्च": ["cost", "price"],
    "रुपये": ["price", "fee", "₹"], "रुपया": ["price", "fee", "₹"],
    "expensive": ["price", "emi", "discount"], "costly": ["price", "emi", "discount"],
    "installment": ["emi"], "instalment": ["emi"], "emi": ["installment"],
    "refund": ["refunds"], "money": ["refund", "price"], "back": ["refund"],
    "schedule": ["batch", "batches", "starts"], "batch": ["batches", "starts"], "start": ["starts", "batch"],
    "duration": ["months", "weeks"], "long": ["duration", "months"],
    "job": ["placement"], "jobs": ["placement"], "placement": ["job"],
    "certificate": ["certificate"], "discount": ["discounts", "early", "scholarship"],
    "contact": ["phone", "email", "address"], "phone": ["contact"], "location": ["address"],
    "genai": ["generative", "llm"], "llm": ["generative", "language"],
    # Hindi / Hinglish
    "कोर्स": ["course"], "कीमत": ["price"], "फीस": ["price", "fee"], "दाम": ["price"], "महंगा": ["price", "emi"],
    "रिफंड": ["refund"], "पैसे": ["refund", "price"], "बैच": ["batch", "starts"], "अवधि": ["duration", "months"],
    "नौकरी": ["placement"], "सर्टिफिकेट": ["certificate"], "छूट": ["discount"], "डिस्काउंट": ["discount"],
    "एआई": ["artificial", "intelligence"], "मशीन": ["machine"], "लर्निंग": ["learning"],
    "डेटा": ["data"], "साइंस": ["science"], "पायथन": ["python"], "क्लाउड": ["cloud"], "वेब": ["web"],
    "किश्त": ["emi"], "ईएमआई": ["emi"], "संपर्क": ["contact"], "kitna": ["price"], "kitni": ["price"],
    "fees": ["price"], "mehenga": ["price", "emi"], "mehnga": ["price", "emi"],
}


def tokenize(text: str) -> list[str]:
    toks = TOKEN_RE.findall(text.lower())
    out = []
    for t in toks:
        if t in STOPWORDS or (len(t) < 2 and t != "₹"):
            continue
        if len(t) > 4 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]  # tiny stemmer: courses -> course
        out.append(t)
    return out


def expand_query(tokens: list[str]) -> list[str]:
    out = list(tokens)
    for t in tokens:
        out.extend(SYNONYMS.get(t, []))
    return out


# ---------------------------------------------------------------- extraction + chunking
class UnsupportedFile(ValueError):
    pass


def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".txt") or name.endswith(".md"):
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data.decode("latin-1")
    if name.endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join((p.extract_text() or "") for p in reader.pages)
    raise UnsupportedFile("Only .txt, .md and .pdf files are supported")


def chunk_text(text: str) -> list[tuple[str, str]]:
    """Return list of (title, content). Sections start with '## '. Long sections are split on paragraphs."""
    text = text.replace("\r\n", "\n").strip()
    if not text:
        return []
    sections: list[tuple[str, str]] = []
    if "## " in text:
        parts = re.split(r"(?m)^## ", text)
        for p in parts:
            p = p.strip()
            if not p:
                continue
            title, _, body = p.partition("\n")
            sections.append((title.strip(), f"{title.strip()}\n{body.strip()}".strip()))
    else:
        sections.append(("", text))

    chunks: list[tuple[str, str]] = []
    for title, body in sections:
        if len(body) <= MAX_CHUNK_CHARS:
            chunks.append((title, body))
            continue
        # split long section on paragraphs / lines, keep title as context prefix
        buf = ""
        paras = []
        for para in re.split(r"\n\s*\n|\n", body):
            while len(para) > MAX_CHUNK_CHARS:  # hard-wrap very long paragraphs at a word boundary
                cut = para.rfind(" ", 0, MAX_CHUNK_CHARS - 100)
                cut = cut if cut > 0 else MAX_CHUNK_CHARS - 100
                paras.append(para[:cut])
                para = para[cut:].strip()
            paras.append(para)
        for para in paras:
            if len(buf) + len(para) + 1 > MAX_CHUNK_CHARS and buf:
                chunks.append((title, buf.strip()))
                buf = (title + "\n") if title else ""
            buf += para + "\n"
        if buf.strip() and buf.strip() != title:
            chunks.append((title, buf.strip()))
    return chunks


# ---------------------------------------------------------------- index
@dataclass
class _Index:
    signature: tuple = ()
    ids: list[int] = field(default_factory=list)
    tfs: list[Counter] = field(default_factory=list)
    lengths: list[int] = field(default_factory=list)
    df: Counter = field(default_factory=Counter)
    avgdl: float = 1.0


_INDEX = _Index()


def _signature(db: Session) -> tuple:
    count, max_id = db.execute(select(func.count(KnowledgeChunk.id), func.max(KnowledgeChunk.id))).one()
    return (count, max_id)


def _ensure_index(db: Session) -> _Index:
    global _INDEX
    sig = _signature(db)
    if sig == _INDEX.signature:
        return _INDEX
    idx = _Index(signature=sig)
    rows = db.execute(select(KnowledgeChunk.id, KnowledgeChunk.content)
                      .join(KnowledgeDocument).where(KnowledgeDocument.status == "ready")).all()
    for cid, content in rows:
        toks = tokenize(content)
        tf = Counter(toks)
        idx.ids.append(cid)
        idx.tfs.append(tf)
        idx.lengths.append(len(toks))
        idx.df.update(tf.keys())
    idx.avgdl = (sum(idx.lengths) / len(idx.lengths)) if idx.lengths else 1.0
    _INDEX = idx
    return idx


def invalidate_index() -> None:
    global _INDEX
    _INDEX = _Index()


@dataclass
class RetrievedChunk:
    chunk_id: int
    document: str
    title: str
    content: str
    score: float

    def as_source(self) -> dict:
        return {"chunk_id": self.chunk_id, "document": self.document, "title": self.title,
                "score": round(self.score, 3), "excerpt": self.content[:280]}


# Words that match almost everything and therefore do not prove the KB covers a topic.
GENERIC = {"course", "कोर्स", "program", "offer", "provide", "available", "academy", "technova", "class", "classe", "learn",
           "learning", "student", "online", "live", "option", "detail", "information", "info"}

# Minimum BM25 score for a chunk to count as relevant. Tuned on the sample KB (see tests/test_rag.py).
MIN_RELEVANCE = 3.0


def bm25_scores(idx: _Index, query_tokens: list[str], k1: float = 1.4, b: float = 0.75) -> list[float]:
    n = len(idx.ids)
    scores = [0.0] * n
    qtf = Counter(query_tokens)
    for term, qweight in qtf.items():
        df = idx.df.get(term, 0)
        if df == 0:
            continue
        idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
        for i, tf in enumerate(idx.tfs):
            f = tf.get(term, 0)
            if f:
                denom = f + k1 * (1 - b + b * idx.lengths[i] / idx.avgdl)
                scores[i] += idf * (f * (k1 + 1)) / denom * min(qweight, 2)
    return scores


def retrieve(db: Session, query: str, top_k: int = 3, embed_fn=None) -> dict:
    """Return {"chunks": [RetrievedChunk], "found": bool, "method": str}."""
    idx = _ensure_index(db)
    if not idx.ids:
        return {"chunks": [], "found": False, "method": "empty-knowledge-base"}
    q_tokens = expand_query(tokenize(query))
    if not q_tokens:
        return {"chunks": [], "found": False, "method": "bm25"}
    scores = bm25_scores(idx, q_tokens)
    method = "bm25"

    # Optional hybrid: blend cosine similarity when embeddings are available.
    if embed_fn is not None:
        try:
            qvec = embed_fn(query)
            emb_rows = dict(db.execute(select(KnowledgeChunk.id, KnowledgeChunk.embedding)
                                       .where(KnowledgeChunk.id.in_(idx.ids))).all())
            if qvec and any(emb_rows.values()):
                max_bm = max(scores) or 1.0
                for i, cid in enumerate(idx.ids):
                    v = emb_rows.get(cid)
                    if v:
                        cos = _cosine(qvec, v)
                        scores[i] = 0.5 * (scores[i] / max_bm) * 10 + 0.5 * cos * 10
                method = "hybrid-bm25-embeddings"
        except Exception:  # embedding failure -> keep keyword ranking
            method = "bm25 (embedding unavailable)"

    # Out-of-vocabulary guard: "Do you offer a blockchain course?" matches only generic words
    # ("offer", "course"), while "blockchain" appears nowhere -> report not found instead of guessing.
    base_tokens = tokenize(query)
    n_docs = len(idx.ids)
    oov = [t for t in base_tokens if idx.df.get(t, 0) == 0 and t not in SYNONYMS and len(t) >= 4]
    specific = [t for t in q_tokens if t not in GENERIC and 0 < idx.df.get(t, 0)]
    oov_block = bool(oov) and not specific

    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    ranked = [i for i in ranked if scores[i] > 0]
    if not ranked:
        return {"chunks": [], "found": False, "method": method}
    top = scores[ranked[0]]
    # keep chunks reasonably close to the best one
    keep = [i for i in ranked if scores[i] >= max(MIN_RELEVANCE * 0.6, top * 0.6)]
    ids = [idx.ids[i] for i in keep]
    rows = {c.id: c for c in db.execute(select(KnowledgeChunk).where(KnowledgeChunk.id.in_(ids))).scalars()}
    chunks = [RetrievedChunk(cid, rows[cid].document.filename, rows[cid].title, rows[cid].content,
                             scores[idx.ids.index(cid)]) for cid in ids if cid in rows]
    found = top >= MIN_RELEVANCE and not oov_block
    return {"chunks": chunks, "found": found, "method": method, "top_score": round(top, 3),
            "unknown_terms": oov}


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def ingest_document(db: Session, filename: str, content_type: str, data: bytes, embed_fn=None) -> KnowledgeDocument:
    """Extract, chunk and store a document. Re-uploading a filename replaces the old version."""
    existing = db.execute(select(KnowledgeDocument).where(KnowledgeDocument.filename == filename)).scalar_one_or_none()
    if existing:
        db.delete(existing)
        db.flush()
    doc = KnowledgeDocument(filename=filename, content_type=content_type, size_bytes=len(data), status="processing")
    db.add(doc)
    db.flush()
    try:
        text = extract_text(filename, data)
        pieces = chunk_text(text)
        if not pieces:
            raise ValueError("No extractable text found (scanned PDFs without OCR are not supported)")
        for i, (title, content) in enumerate(pieces):
            emb = None
            if embed_fn is not None:
                try:
                    emb = embed_fn(content)
                except Exception:
                    emb = None
            db.add(KnowledgeChunk(document_id=doc.id, chunk_index=i, title=title[:255], content=content, embedding=emb))
        doc.chunk_count = len(pieces)
        doc.status = "ready"
    except Exception as e:  # keep a failed record so the UI can show the error
        doc.status = "failed"
        doc.error = str(e)[:500]
    db.commit()
    invalidate_index()
    return doc


PRICE_RE = re.compile(r"Price:\s*₹\s*([\d,]+)")


def find_product_price(db: Session, product_name: str) -> int | None:
    """Look up a product's price from the knowledge base (grounded, not hardcoded)."""
    row = db.execute(select(KnowledgeChunk.content).where(KnowledgeChunk.title.ilike(f"%{product_name}%"))).first()
    if not row:
        return None
    m = PRICE_RE.search(row[0])
    return int(m.group(1).replace(",", "")) if m else None
