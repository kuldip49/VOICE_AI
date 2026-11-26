"""Build the repository's current as-built system design PDF."""
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "pdf" / "SalesPilot-AI-System-Design.pdf"
PAGE_W, PAGE_H = landscape(A4)
M = 38

INK = colors.HexColor("#162A31")
MUTED = colors.HexColor("#5C6E72")
TEAL = colors.HexColor("#197769")
TEAL_PALE = colors.HexColor("#EAF5F2")
GOLD = colors.HexColor("#B77C20")
GOLD_PALE = colors.HexColor("#FFF5E3")
PURPLE = colors.HexColor("#7663A7")
PURPLE_PALE = colors.HexColor("#F3F0FA")
LINE = colors.HexColor("#DCE5E3")
PAPER = colors.white
PALE = colors.HexColor("#F5F8F7")

STYLES = {
    "body": ParagraphStyle("body", fontName="Helvetica", fontSize=9.0, leading=12.4, textColor=INK),
    "small": ParagraphStyle("small", fontName="Helvetica", fontSize=8.1, leading=10.8, textColor=INK),
    "tiny": ParagraphStyle("tiny", fontName="Helvetica", fontSize=7.4, leading=9.4, textColor=INK),
    "muted": ParagraphStyle("muted", fontName="Helvetica", fontSize=8.2, leading=11, textColor=MUTED),
    "cardtitle": ParagraphStyle("cardtitle", fontName="Helvetica-Bold", fontSize=10.2, leading=12, textColor=INK),
    "big": ParagraphStyle("big", fontName="Helvetica", fontSize=12.4, leading=17, textColor=INK),
    "hero": ParagraphStyle("hero", fontName="Helvetica-Bold", fontSize=31, leading=35, textColor=INK),
    "section": ParagraphStyle("section", fontName="Helvetica-Bold", fontSize=19, leading=22, textColor=INK),
    "white": ParagraphStyle("white", fontName="Helvetica", fontSize=9.2, leading=13, textColor=colors.white),
    "white_title": ParagraphStyle("white_title", fontName="Helvetica-Bold", fontSize=10.2, leading=12, textColor=colors.white),
}


def para(c, text, x, top, width, style="body"):
    p = Paragraph(escape(str(text)).replace("\n", "<br/>"), STYLES[style])
    _, h = p.wrap(width, PAGE_H)
    p.drawOn(c, x, top - h)
    return top - h


def bullet_list(c, items, x, top, width, style="small", gap=3.0, color=TEAL):
    y = top
    size = STYLES[style].fontSize
    for item in items:
        c.setFillColor(color)
        c.circle(x + 2.2, y - size * 0.63, 2.0, fill=1, stroke=0)
        y = para(c, item, x + 10, y, width - 10, style) - gap
    return y


def card(c, x, top, width, height, title, items, accent=TEAL, fill=PAPER,
         style="small", title_size=None):
    y = top - height
    c.setFillColor(fill)
    c.setStrokeColor(LINE)
    c.setLineWidth(0.8)
    c.roundRect(x, y, width, height, 9, fill=1, stroke=1)
    c.setFillColor(accent)
    c.roundRect(x, y + height - 5, width, 5, 3, fill=1, stroke=0)
    para(c, title, x + 13, top - 16, width - 26, "cardtitle")
    bullet_list(c, items, x + 13, top - 38, width - 26, style, 2.6, accent)
    return y


def line(c, x1, y1, x2, y2, color=LINE, width=1, dash=None):
    c.saveState()
    c.setStrokeColor(color)
    c.setLineWidth(width)
    if dash:
        c.setDash(*dash)
    c.line(x1, y1, x2, y2)
    c.restoreState()


def arrow(c, x1, y1, x2, y2, color=TEAL, dashed=False):
    line(c, x1, y1, x2, y2, color, 1.6, (4, 3) if dashed else None)
    import math
    angle = math.atan2(y2 - y1, x2 - x1)
    size = 6
    c.setFillColor(color)
    path = c.beginPath()
    path.moveTo(x2, y2)
    path.lineTo(x2 - size * math.cos(angle - 0.48), y2 - size * math.sin(angle - 0.48))
    path.lineTo(x2 - size * math.cos(angle + 0.48), y2 - size * math.sin(angle + 0.48))
    path.close()
    c.drawPath(path, fill=1, stroke=0)


def base(c, page, title, subtitle):
    c.setFillColor(PAPER)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFillColor(TEAL)
    c.rect(0, PAGE_H - 7, PAGE_W, 7, fill=1, stroke=0)
    c.setFillColor(TEAL)
    c.setFont("Helvetica-Bold", 7.6)
    c.drawString(M, PAGE_H - 25, "KILN & SIGNAL  /  SALES PILOT AI")
    para(c, title, M, PAGE_H - 42, PAGE_W - 2 * M, "section")
    para(c, subtitle, M, PAGE_H - 68, PAGE_W - 2 * M, "muted")
    line(c, M, 29, PAGE_W - M, 29, LINE, 0.7)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7.3)
    c.drawString(M, 17, "AS-BUILT SYSTEM DESIGN  /  26 NOV 2026")
    c.drawRightString(PAGE_W - M, 17, f"{page:02d}")


def pill(c, x, y, text, color=TEAL, fill=TEAL_PALE):
    w = stringWidth(text, "Helvetica-Bold", 8) + 20
    c.setFillColor(fill)
    c.roundRect(x, y, w, 22, 11, fill=1, stroke=0)
    c.setFillColor(color)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(x + w / 2, y + 7, text)
    return w


def node(c, x, y, w, h, title, detail, fill, accent):
    c.setFillColor(fill)
    c.setStrokeColor(accent)
    c.setLineWidth(1.1)
    c.roundRect(x, y, w, h, 10, fill=1, stroke=1)
    c.setFillColor(accent)
    c.setFont("Helvetica-Bold", 9.2)
    c.drawCentredString(x + w / 2, y + h - 20, title)
    p = Paragraph(escape(detail).replace("\n", "<br/>"), STYLES["tiny"])
    p.style.textColor = MUTED
    _, ph = p.wrap(w - 20, h - 30)
    p.drawOn(c, x + 10, y + h - 27 - ph)


def page1(c):
    c.setFillColor(PAPER)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFillColor(TEAL)
    c.rect(0, PAGE_H - 8, PAGE_W, 8, fill=1, stroke=0)
    c.setFillColor(TEAL_PALE)
    c.circle(PAGE_W - 115, PAGE_H - 100, 106, fill=1, stroke=0)
    c.setFillColor(PURPLE_PALE)
    c.circle(PAGE_W - 72, PAGE_H - 155, 48, fill=1, stroke=0)
    c.setFillColor(TEAL)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(M, PAGE_H - 40, "KILN & SIGNAL  /  SALES PILOT AI")
    para(c, "System Design\nAs Built", M, PAGE_H - 78, 505, "hero")
    para(c, "A practical map of the system in this repository: what runs, how a customer interaction moves through it, which technologies are used, and what remains optional or planned.", M, PAGE_H - 166, 480, "big")
    x = M
    for label, color, fill in [("WEB DASHBOARD", TEAL, TEAL_PALE), ("AI SALES AGENT", PURPLE, PURPLE_PALE), ("VOICE + PHONE", GOLD, GOLD_PALE), ("LOCAL-FIRST DATA", TEAL, TEAL_PALE)]:
        x += pill(c, x, PAGE_H - 235, label, color, fill) + 9

    # Four-step overview strip
    ytop = PAGE_H - 286
    gap = 12
    w = (PAGE_W - 2 * M - 3 * gap) / 4
    overview = [
        ("01  Experience", ["React and TypeScript dashboard", "Text, browser voice and staff tools"], TEAL),
        ("02  API + agent", ["FastAPI routes", "Rule-based planner and 10 validated tools"], PURPLE),
        ("03  Intelligence", ["BM25 knowledge retrieval", "Lead, sentiment and scheduling services"], GOLD),
        ("04  Records", ["SQLAlchemy ORM", "SQLite default with 13 current tables"], TEAL),
    ]
    for i, (title, items, accent) in enumerate(overview):
        card(c, M + i * (w + gap), ytop, w, 103, title, items, accent, style="small")

    c.setFillColor(INK)
    c.roundRect(M, 55, PAGE_W - 2 * M, 71, 10, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(M + 18, 104, "CURRENT CODEBASE SNAPSHOT")
    c.setFont("Helvetica", 8.8)
    c.drawString(M + 18, 84, "Functional MVP  |  7 dashboard pages  |  10 agent tools  |  13 ORM tables")
    c.setFillColor(colors.HexColor("#C2D5D0"))
    c.setFont("Helvetica", 7.6)
    c.drawString(M + 18, 68, "Scope and verification notes reflect repository documentation dated 26 November 2026.")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7.5)
    c.drawRightString(PAGE_W - M, 29, "01")
    c.showPage()


def page2(c):
    base(c, 2, "System context and runtime architecture", "Implemented request paths, optional external services, and the local deployment topology.")
    top = 474
    node(c, 40, 314, 174, 128, "Browser client", "React 19 + TypeScript\nSeven staff pages\nWeb Speech API: STT / TTS", TEAL_PALE, TEAL)
    node(c, 252, 314, 130, 128, "HTTP edge", "Development: Vite proxy\nDocker: Nginx static host\nSame-origin /api", PALE, MUTED)
    node(c, 418, 314, 214, 128, "FastAPI backend", "REST routers + Pydantic\nSalesAgent + 10 tools\nRAG and sales services", TEAL_PALE, TEAL)
    node(c, 668, 314, 136, 128, "Database", "SQLAlchemy ORM\nSQLite by default\n13 current tables", PALE, MUTED)
    arrow(c, 214, 378, 252, 378)
    arrow(c, 382, 378, 418, 378)
    arrow(c, 632, 378, 668, 378)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7.1)
    c.drawCentredString(232, 390, "JSON")
    c.drawCentredString(400, 390, "HTTP")
    c.drawCentredString(650, 390, "ORM")

    node(c, 418, 167, 180, 92, "Model providers (optional)", "Gemini / Grok REST\nOllama local / demo templates", GOLD_PALE, GOLD)
    arrow(c, 500, 314, 500, 259, GOLD, dashed=True)
    para(c, "Grounded answer text; embeddings are optional", 512, 292, 145, "tiny")

    node(c, 40, 167, 263, 92, "Inbound phone path (optional setup)", "Caller -> Exotel ExoPhone -> Voicebot WSS\nSarvam STT/TTS -> SalesAgent / CRM\nNeeds account, public WSS and API keys", GOLD_PALE, GOLD)
    arrow(c, 303, 225, 418, 314, GOLD, dashed=True)
    para(c, "Authenticated audio stream enters FastAPI", 310, 291, 112, "tiny")

    # Legend + deployment facts
    c.setFillColor(TEAL)
    c.circle(52, 116, 4, fill=1, stroke=0)
    para(c, "Implemented in the repository", 64, 122, 180, "small")
    c.setFillColor(GOLD)
    c.circle(274, 116, 4, fill=1, stroke=0)
    para(c, "Provider or account setup required", 286, 122, 210, "small")
    para(c, "Development: Vite :5173 -> FastAPI :8000. Docker Compose: Nginx :8080 -> backend:8000; named volume keeps `/app/data` persistent.", 40, 92, 760, "small")
    c.showPage()


def page3(c):
    base(c, 3, "Conversation flow and voice paths", "Both browser and phone interactions reach the same backend agent; their audio handling differs.")
    # Process line
    steps = [
        ("1", "Receive", "Save the message; detect English/Hindi."),
        ("2", "Understand", "Extract volunteered facts; analyze sentiment."),
        ("3", "Plan", "Rule-based intent planner selects actions."),
        ("4", "Act", "Validated tools retrieve, qualify or book."),
        ("5", "Reply", "Grounded answer or safe template; save sources."),
    ]
    startx, gap, w, h = 40, 12, 144, 98
    for i, (num, title, detail) in enumerate(steps):
        x = startx + i * (w + gap)
        c.setFillColor(TEAL_PALE if i in (0, 4) else PALE)
        c.setStrokeColor(LINE)
        c.roundRect(x, 351, w, h, 9, fill=1, stroke=1)
        c.setFillColor(TEAL if i in (0, 4) else PURPLE)
        c.circle(x + 18, 427, 10, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(x + 18, 424, num)
        para(c, title, x + 34, 438, w - 44, "cardtitle")
        para(c, detail, x + 12, 407, w - 24, "tiny")
        if i < len(steps) - 1:
            arrow(c, x + w, 400, x + w + gap - 2, 400, TEAL)

    card(c, 40, 324, 370, 128, "Browser text / voice", [
        "Text is sent as JSON through `/api` to FastAPI.",
        "Browser voice uses SpeechRecognition for input and speechSynthesis for playback; microphone metering stays in the browser.",
        "Browser speech recognition may use the browser vendor's online speech service. The backend stores recognized text, not raw audio.",
        "Typed input remains available when microphone or speech support is missing.",
    ], TEAL, style="small")
    card(c, 428, 324, 376, 128, "Inbound Exotel phone", [
        "An Exotel Voicebot applet opens authenticated WSS `/api/telephony/exotel/stream` and sends PCM audio.",
        "Sarvam realtime STT transcribes; the existing SalesAgent handles retrieval, CRM, booking and summaries.",
        "Sarvam TTS streams Hindi/English PCM audio back to Exotel; press 9 to switch languages.",
        "Code exists; a live call needs AgentStream, an assigned ExoPhone flow, public WSS and API keys.",
    ], GOLD, fill=GOLD_PALE, style="small")

    c.setFillColor(PURPLE_PALE)
    c.roundRect(40, 78, 764, 110, 10, fill=1, stroke=0)
    para(c, "Trust and action boundaries", 56, 172, 250, "cardtitle")
    bullet_list(c, [
        "The LLM may write knowledge answers using retrieved chunks; it does not choose tools or execute bookings.",
        "Unknown knowledge triggers a safe refusal. Transactional replies use exact database/tool results.",
        "Booking requires explicit customer confirmation; an active-slot unique index prevents duplicate bookings even when requests race.",
    ], 56, 149, 730, "small", 3, PURPLE)
    c.showPage()


def page4(c):
    base(c, 4, "Product modules and API surface", "The staff dashboard exposes the end-to-end sales workflow; FastAPI groups it by domain.")
    gap, cw, ch = 14, (PAGE_W - 2 * M - 14) / 2, 183
    card(c, M, 485, cw, ch, "Customer and staff experience", [
        "Overview: headline metrics and recent activity.",
        "Live Agent: text/voice, transcript, sources, sentiment, score and tool trace.",
        "CRM: search/filter, profile, conversation history, memories, status, deletion and CSV export.",
        "Appointments: availability, booking, cancellation and rescheduling.",
    ], TEAL, style="small")
    card(c, M + cw + gap, 485, cw, ch, "Knowledge and operations", [
        "Knowledge: upload, inspect, search and delete PDF, TXT and Markdown files.",
        "Analytics: lead, sentiment, question, objection, product and appointment metrics.",
        "Settings: business profile, agent prompt, scoring, schedule, voice and provider status.",
        "Routes: `/`, `/agent`, `/crm`, `/appointments`, `/knowledge`, `/analytics`, `/settings`.",
    ], PURPLE, style="small")

    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(M, 281, "REST API domains")
    domains = [
        ("Conversation", "Create session; post message; fetch/end session; admin conversation and tool-log inspection."),
        ("CRM", "List/export leads; read/update/delete customer records; remove stored memories."),
        ("Appointments", "Look up slots; staff list/create/cancel/reschedule bookings."),
        ("Knowledge", "List documents/chunks; upload/delete files; query retrieval."),
        ("Analytics + settings", "Overview aggregates; public settings; protected read/update configuration."),
        ("Telephony + health", "Exotel readiness; authenticated bidirectional audio WebSocket; `/api/health`."),
    ]
    rowtop = 260
    rowh = 33
    for i, (name, detail) in enumerate(domains):
        y = rowtop - i * rowh
        if i % 2 == 0:
            c.setFillColor(PALE)
            c.roundRect(M, y - 26, PAGE_W - 2 * M, 29, 5, fill=1, stroke=0)
        c.setFillColor(TEAL if i in (0, 1, 2) else PURPLE)
        c.setFont("Helvetica-Bold", 8.4)
        c.drawString(M + 10, y - 9, name)
        para(c, detail, M + 145, y, PAGE_W - 2 * M - 158, "tiny")
    para(c, "FastAPI provides interactive OpenAPI docs at `/docs`. Admin access is optional and uses the `X-Admin-Key` header when configured.", M, 55, PAGE_W - 2 * M, "muted")
    c.showPage()


def page5(c):
    base(c, 5, "Data model and persistence", "Current code defines 13 SQLAlchemy tables; the earlier 12-table note predates the telephony call table.")
    cols = [M, M + 258, M + 516]
    widths = [245, 245, PAGE_W - M - (M + 516)]
    groups = [
        ("Customer and sales records", [
            "customers - name, contact, language", "leads - interest, budget, score, status", "conversations - channel, state, rolling memory", "messages - transcript, intent, source/provider", "customer_memories - durable key/value facts", "appointments - time, status, topic",
        ], TEAL),
        ("Knowledge and conversation analysis", [
            "knowledge_documents - uploaded file metadata", "knowledge_chunks - indexed text + optional embedding", "call_summaries - outcome and follow-up", "sentiment_records - message sentiment and action",
        ], PURPLE),
        ("Operations and integration", [
            "telephony_calls - provider SID and call state", "agent_tool_logs - arguments, results and timing", "app_settings - editable business configuration",
        ], GOLD),
    ]
    for i, (title, items, accent) in enumerate(groups):
        card(c, cols[i], 476, widths[i], 214, title, items, accent, style="tiny")

    c.setFillColor(PALE)
    c.roundRect(M, 143, PAGE_W - 2 * M, 111, 9, fill=1, stroke=0)
    para(c, "Key relationships and integrity", M + 15, 237, 310, "cardtitle")
    bullet_list(c, [
        "Customer has one lead and may have many conversations, memories and appointments.",
        "Conversation owns messages and a summary; sentiment and tool logs retain traceable links.",
        "A knowledge document owns chunks. Exotel call records can link to a conversation.",
        "Foreign-key cascades support deletion; SQLite enables foreign keys and WAL.",
        "Partial unique index on booked appointment start time prevents two active bookings for one slot.",
    ], M + 15, 214, PAGE_W - 2 * M - 30, "tiny", 1.6, TEAL)

    c.setFillColor(INK)
    c.roundRect(M, 61, PAGE_W - 2 * M, 58, 8, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(M + 14, 99, "DEFAULT DATABASE")
    c.setFont("Helvetica", 8.2)
    c.drawString(M + 14, 81, "SQLite at backend/data/salespilot.db; `DATABASE_URL` selects the SQLAlchemy database URL.")
    c.setFillColor(colors.HexColor("#C2D5D0"))
    c.setFont("Helvetica", 7.5)
    c.drawString(M + 14, 67, "PostgreSQL is a documented target; migrations and production operations are not implemented in this MVP.")
    c.showPage()


def page6(c):
    base(c, 6, "Technology stack, one layer at a time", "The implementation choices and the job each one performs in the current system.")
    cols = [M, M + 258, M + 516]
    widths = [245, 245, PAGE_W - M - (M + 516)]
    card(c, cols[0], 480, widths[0], 370, "Frontend", [
        "React 19 - component UI and page composition.",
        "TypeScript - typed code and client models.",
        "Vite 8 - dev server, proxy and production build.",
        "React Router 7 - route navigation and lazy pages.",
        "Tailwind CSS 4 - design tokens and styling.",
        "Radix UI + class-variance-authority - accessible primitives and component variants.",
        "Lucide React - icons; Recharts - charts; Sonner - toast notifications.",
        "Web Speech API - browser recognition and speech synthesis.",
    ], TEAL, style="tiny")
    card(c, cols[1], 480, widths[1], 370, "Backend and persistence", [
        "Python 3.11+ project baseline; Docker image uses Python 3.12.",
        "FastAPI + Uvicorn - HTTP API and ASGI server.",
        "websockets 15 - async client connection for Sarvam streaming STT/TTS.",
        "Pydantic 2 + pydantic-settings - validation and environment configuration.",
        "SQLAlchemy 2 - ORM, relationships and database access.",
        "SQLite - default local relational store; WAL and foreign keys enabled.",
        "httpx - outbound HTTP for model providers; mockable transport.",
        "pypdf - PDF text extraction for uploaded knowledge files.",
        "pytest + FastAPI TestClient - backend unit/API verification.",
        "Playwright MCP / Chrome DevTools MCP scripts - browser workflow and audits in e2e/.",
    ], PURPLE, style="tiny")
    card(c, cols[2], 480, widths[2], 370, "Agent and retrieval", [
        "Rule-based planner - selects intent and tools deterministically.",
        "Ten Pydantic-validated tools - bounded operations with execution logs.",
        "BM25 - default explainable keyword search over document chunks.",
        "Gemini embeddings - optional hybrid retrieval; stored per chunk when generated.",
        "Gemini REST - selected local provider per repository status; answer writing and optional embeddings.",
        "Grok REST - implemented provider adapter.",
        "Ollama - local model provider adapter.",
        "Demo templates - no-key grounded behavior and transactional messages.",
        "Exotel AgentStream - inbound phone transport; account entitlement and flow setup required.",
        "Sarvam realtime STT/TTS - Hindi/English phone transcript and 16 kHz linear16 audio.",
        "Credentials remain backend environment settings; never included in this PDF.",
    ], GOLD, fill=GOLD_PALE, style="tiny")
    para(c, "Actual defaults and provider selection live in backend/app/config.py and backend/app/services/llm.py. Browser voice and Exotel phone voice are distinct implementations.", M, 65, PAGE_W - 2 * M, "muted")
    c.showPage()


def page7(c):
    base(c, 7, "Security, configuration and operations", "Current controls are MVP-scoped; the boundaries below are part of the design, not compliance claims.")
    gap = 14
    w = (PAGE_W - 2 * M - gap) / 2
    card(c, M, 486, w, 203, "Implemented controls", [
        "Backend-only secrets; settings exposes provider configured/not-set, not secret values.",
        "Optional shared X-Admin-Key; no accounts or role-based permissions.",
        "Pydantic validation and a fixed tool allow-list; SQLAlchemy parameterized access.",
        "Limited CORS, generic client errors and per-process in-memory chat rate limiting.",
        "Upload type/size checks; sanitized filename and PDF signature checks.",
        "Booking confirmation plus unique active slot index; UUID conversation IDs.",
        "Customer deletion and memory removal endpoints; browser audio is not stored by this API.",
    ], TEAL, style="tiny")
    card(c, M + w + gap, 486, w, 203, "Environment settings", [
        "DATABASE_URL; LLM_PROVIDER (auto/grok/gemini/ollama/demo); model names and provider keys.",
        "Ollama base URL and timeout; Exotel account/key/token/number/WSS URL; Sarvam key, models and voices.",
        "ADMIN_API_KEY; CORS_ORIGINS; MAX_UPLOAD_MB; RATE_LIMIT_PER_MINUTE; TIMEZONE.",
        "Defaults are in backend/app/config.py; local secrets belong in ignored backend/.env.",
        "This repository snapshot selects Gemini locally; the API can also run in demo mode.",
    ], GOLD, fill=GOLD_PALE, style="tiny")

    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(M, 260, "Run and deployment shape")
    card(c, M, 244, w, 94, "Local development", [
        "Run setup.ps1 and start-all.ps1, or launch services separately.",
        "Vite :5173 proxies /api to FastAPI :8000.",
    ], TEAL, style="tiny")
    card(c, M + w + gap, 244, w, 94, "Docker Compose", [
        "Nginx serves the frontend at :8080 and proxies /api/ to backend:8000.",
        "Named salespilot-data volume persists backend /app/data.",
    ], PURPLE, style="tiny")

    c.setFillColor(PURPLE_PALE)
    c.roundRect(M, 62, PAGE_W - 2 * M, 74, 9, fill=1, stroke=0)
    para(c, "Not included in the running MVP", M + 14, 119, 270, "cardtitle")
    para(c, "User accounts and roles, tenant isolation, PostgreSQL migrations, Redis limits, background workers, Google Calendar sync, external CRM sync, managed deployment and load-tested scaling are future work. Live phone calls require Exotel AgentStream, an assigned flow, public WSS and Sarvam access; provider usage may be charged.", M + 14, 98, PAGE_W - 2 * M - 28, "small")
    c.showPage()


def page8(c):
    base(c, 8, "Current scope, evidence and source map", "A reviewable distinction between implemented code, repository-reported checks and future work.")
    gap = 14
    w = (PAGE_W - 2 * M - gap) / 2
    card(c, M, 485, w, 190, "Implemented product scope", [
        "Seven-page staff dashboard and typed `/api` client.",
        "English/Hindi conversation; browser voice UI; Exotel AgentStream + Sarvam inbound phone path.",
        "Grounded knowledge retrieval, document upload and source tracking.",
        "Fact extraction, persistent customer memory, lead scoring, sentiment and objections.",
        "CRM operations, appointment lifecycle, call summaries and analytics.",
        "Settings, CSV export, SQLite persistence and Docker Compose configuration.",
    ], TEAL, style="small")
    card(c, M + w + gap, 485, w, 190, "Verification recorded in repository", [
        "PROJECT_PROGRESS.md, dated 26 Nov 2026, reports 60 backend tests passing.",
        "It reports frontend TypeScript and production build passing; lint passing with five warnings.",
        "It reports a live Gemini smoke check and Docker Compose config check.",
        "The same record marks live mic/phone/browser refresh and Docker image build as not completed in that session.",
        "The Exotel/Sarvam code change in this snapshot has not been connected to a live account or number.",
        "These are recorded results; tests were not rerun to generate this document.",
    ], GOLD, fill=GOLD_PALE, style="small")

    c.setFillColor(PALE)
    c.roundRect(M, 184, PAGE_W - 2 * M, 92, 9, fill=1, stroke=0)
    para(c, "Where to inspect the implementation", M + 15, 263, PAGE_W - 2 * M - 30, "cardtitle")
    left = [
        "UI: frontend/src/App.tsx, pages/, components/",
        "Voice/client: frontend/src/hooks/useVoice.ts, src/lib/api.ts",
        "API/config/security: backend/app/main.py, config.py, security.py",
        "Agent/tools: backend/app/agent/orchestrator.py, tools.py",
        "Retrieval/providers: backend/app/services/rag.py, llm.py",
    ]
    right = [
        "Data: backend/app/models.py, database.py, seed.py",
        "Routers/services: backend/app/routers/, services/",
        "Runtime: docker-compose.yml, Dockerfiles, frontend/nginx.conf",
        "Tests/automation: backend/tests/, e2e/",
        "Security/phone: docs/SECURITY.md, docs/TELEPHONY_SETUP.md",
    ]
    bullet_list(c, left, M + 15, 241, 360, "tiny", 1.4, TEAL)
    bullet_list(c, right, M + 407, 241, PAGE_W - M - (M + 407) - 15, "tiny", 1.4, PURPLE)

    c.setFillColor(INK)
    c.roundRect(M, 56, PAGE_W - 2 * M, 108, 9, fill=1, stroke=0)
    para(c, "Design takeaway", M + 15, 144, 260, "white_title")
    para(c, "A deterministic, auditable agent owns business actions. Retrieval grounds product answers. The relational store is the source of truth for leads, conversations and bookings. External model and telephony services are replaceable integrations; scale-out infrastructure is a documented next phase.", M + 15, 121, PAGE_W - 2 * M - 30, "white")
    c.showPage()


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUT), pagesize=(PAGE_W, PAGE_H), pageCompression=1)
    c.setTitle("SalesPilot AI - System Design As Built")
    c.setAuthor("SalesPilot AI / Kiln & Signal")
    c.setSubject("As-built architecture, components, technology and implementation status")
    page1(c)
    page2(c)
    page3(c)
    page4(c)
    page5(c)
    page6(c)
    page7(c)
    page8(c)
    c.save()
    print(OUT)


if __name__ == "__main__":
    main()
