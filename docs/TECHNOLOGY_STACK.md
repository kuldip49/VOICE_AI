# Technology stack

| Layer | Choice | Why | Alternatives |
|---|---|---|---|
| Backend language | **Python 3.11+** | Best AI/ML ecosystem, readable for beginners | Node.js, Go |
| Web framework | **FastAPI** | Async-ready, automatic OpenAPI docs at `/docs`, Pydantic validation built in | Flask (no validation), Django (heavier) |
| Validation | **Pydantic v2** | Same models validate API bodies *and* agent tool arguments | marshmallow |
| ORM | **SQLAlchemy 2** | Prevents SQL injection via parameterised queries, DB-agnostic (SQLite → PostgreSQL) | Django ORM, raw SQL |
| Database | **SQLite** (MVP) | Zero install, single file, survives restarts | PostgreSQL (production), MySQL |
| PDF text | **pypdf** | Pure Python, no system deps on Windows | pdfplumber, PyMuPDF |
| HTTP client | **httpx** | Timeouts + mockable transport for tests | requests |
| LLM | **Gemini REST** or **Ollama** (optional) | Gemini has a free tier; Ollama is free and local | OpenAI, Anthropic, Groq |
| Retrieval | **BM25** (own ~60 lines) + optional Gemini embeddings | Free, offline, explainable scores | FAISS, Chroma, pgvector, Qdrant |
| Frontend | **React 19 + TypeScript** | Component model, type safety, huge ecosystem | Vue, Svelte |
| Build tool | **Vite** | Instant dev server, `/api` proxy | webpack, Next.js |
| Styling | **Tailwind CSS v4** | Design tokens in CSS variables, dark mode via class | CSS modules |
| Components | **shadcn/ui pattern** (Radix + cva), **Lucide** icons | Accessible primitives, code you own (copied, not a dependency) | MUI, Chakra |
| Charts | **Recharts** | Declarative React charts | Chart.js, ECharts |
| Voice | **Web Speech API** | Free, no server audio processing | Whisper / Vosk (STT), Piper / Coqui (TTS), Deepgram, Azure Speech |
| Tests | **pytest**, FastAPI TestClient; browser tests through **Playwright MCP** and **Chrome DevTools MCP** | | Cypress, Selenium |

## Component libraries vs MCP servers
- **Component libraries** (shadcn/ui, Magic UI, Aceternity UI) are source code you copy into the app. SalesPilot uses the shadcn/ui pattern only; Magic UI/Aceternity were not needed because the brief asked for restrained, non-decorative UI.
- **MCP servers** are tools an AI coding assistant calls while building (search components, drive a browser, fetch docs, draw diagrams). They are not part of the running product. See [MCP_SETUP.md](MCP_SETUP.md).

## Why not a vector database in the MVP?
The sample knowledge base is ~25 chunks. BM25 over that is instant, needs no model, and its scores are explainable in an interview. The code already supports embeddings (hybrid scoring) when a Gemini key is present, and the production plan moves to pgvector/Qdrant.
