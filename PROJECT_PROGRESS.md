# PROJECT_PROGRESS

Last update: 2026-11-26 (verification refresh). Statuses: NOT STARTED · IN PROGRESS · BLOCKED · IMPLEMENTED · TESTED · VERIFIED (= tested + checked in a real browser).

## Current status
Functional MVP with demo mode and Gemini provider support. Gemini is configured in the local ignored `backend/.env`; no API key is stored in this repository. Main business workflow passes in the backend suite, and the earlier real-browser workflow is recorded below.

## Features
| Feature | Status | Evidence |
|---|---|---|
| Text conversation | VERIFIED | `test_full_sales_workflow`, browser steps 2-10 |
| Voice: STT/TTS, mic meter, hands-free, barge-in, mute, stop | IMPLEMENTED | Code + unsupported/blocked-mic UI verified; live mic not testable headless. **Test in Chrome/Edge on PC** |
| English + Hindi | VERIFIED (text) | `test_hindi_workflow`, browser step 7 |
| Contextual + persistent memory, context window | TESTED | `test_contextual_memory…`, `test_persistent_memory…`, `test_context_window_rolls_summary` |
| RAG: upload PDF/TXT, chunk, BM25, sources, not-found guard | VERIFIED | `tests/test_rag.py` (9), Knowledge page step |
| Embedding hybrid retrieval | TESTED (live smoke check) | Live Gemini embedding + hybrid RAG retrieval against an in-memory knowledge base; stored chunks without embeddings continue to use BM25 |
| LLM providers (Gemini, Ollama) + fallback | TESTED | Gemini generation checked live; Ollama/provider HTTP behavior tested with mocks |
| Lead extraction + scoring with reasons | VERIFIED | unit tests + Caller/Score panels |
| Sentiment + objections + recommended action | VERIFIED | unit tests + browser step 5 |
| Appointments: slots, confirm, book, duplicate prevention, cancel, reschedule | VERIFIED | `tests/test_appointments.py` (9), browser step 8 |
| CRM: list/search/filter/sort/profile/transcripts/status/delete/CSV | VERIFIED | `test_crm_search…`, browser steps 11-12 |
| Call summaries | VERIFIED | browser step 10 |
| Analytics from DB + empty states | VERIFIED | `test_empty_analytics`, browser step 15 |
| Settings (business profile, prompt, scoring, availability, voice, env status, admin key) | TESTED | `test_settings_validation`; UI screenshot |
| Security: admin key, validation, upload limits, rate limit, CORS, cascade delete | TESTED | `test_admin_key…`, `test_rate_limit`, `test_upload_validation`, `test_delete_lead_cascades` |
| Dark/light theme, responsive (390 / 820 / 1440 px) | VERIFIED | screenshots in `e2e/output/img` |
| Docker compose | TESTED (configuration) | `docker compose config --quiet` passes; image build not run because Docker Desktop's engine was unavailable |
| Google Calendar | NOT STARTED | Adapter seam only (by design) |
| User accounts / multi-tenancy | NOT STARTED | Documented in SECURITY/SCALABILITY |
| Alembic migrations | NOT STARTED | `create_all` used |
| Docs (11 files + diagrams + cost model) | IMPLEMENTED | `docs/` |

## Verification refresh (2026-11-26)

| Check | Result |
|---|---|
| Backend pytest | **60 passed** (6 dependency/runtime deprecation warnings) |
| Frontend `tsc -b` + `vite build` | **Passed** (Vite native-config compatibility warning) |
| Live Gemini generation | **Passed**, active model label confirmed without printing the key |
| Live Gemini embedding + hybrid retrieval | **Passed** using an in-memory SQLite knowledge base; the persistent local database was not changed |
| Docker Compose configuration | **Passed** with `docker compose config --quiet`; Docker Desktop could not start, so image build remains unverified |
| Browser microphone | Not live-tested on this device; the browser UI, unsupported, and blocked-mic paths remain covered by the earlier browser checks |
| Google Calendar | Not integrated; the local SQL database is the active calendar and the adapter interface is a seam only |

## Tests executed in the original verification cycle
| Suite | Result |
|---|---|
| Backend pytest (unit, API integration, E2E-API workflow, Hindi, memory, RAG, booking, CRM, security, LLM mocks) | **58 passed** |
| Frontend `tsc -b` + `vite build` | pass |
| Frontend lint (oxlint) | 0 errors, 5 warnings (React effect/fast-refresh hints) |
| Browser workflow via Playwright MCP | **20/20 steps passed** |
| Chrome DevTools MCP | 0 console errors, 0 failed requests on 7 pages; Lighthouse A11y 100, Best Practices 100; LCP ~1.5 s (dev server), CLS 0 |
| MCP servers verify | Playwright ✅, DevTools ✅, draw.io ✅, shadcn ⚠️ (registry blocked in sandbox), Context7 ⚠️ (blocked in sandbox) |

## Bugs found and fixed
1. `SalesAgent.tool(name, **args)` clashed with a `name` argument → positional-only parameter.
2. "Do you offer a blockchain course?" returned AI course (remembered interest appended + generic-word matches) → attribute-only context expansion + out-of-vocabulary guard.
3. "Too expensive" retrieved the course page instead of payment options → objection-specific two-query search.
4. Hindi name captured "राहुल है"; Hindi "हाँ" not matched (combining mark breaks `\b`) → fixed regex boundaries.
5. "I'm Vikram" not extracted (case-sensitive prefix) → scoped `(?i:)`.
6. Long single paragraphs exceeded chunk size → hard wrap.
7. Live agent page grew instead of scrolling; caller panel off-screen → fixed-height call panel.
8. Charts invisible in screenshots (animation) and lazy-route blank screenshots → animations off, Suspense inside shell, tests wait for content.
9. Lighthouse robots.txt invalid → added `robots.txt` (internal console, `Disallow: /`; this lowers the SEO score on purpose).
10. Windows: `zoneinfo` needs `tzdata` → added to requirements.

## Current blockers
- **Copy to PC:** no folder attached in this session. Minimum action: Claude desktop app → this chat → **+** → **Add folder** → `Desktop\Projects\SalesPilot-AI`. Or download the zip and unzip there.
- Live microphone test needs a real browser on the PC.

## Next five priorities
1. Run on the PC: `setup.ps1`, voice test in Chrome/Edge (en + hi), `npm run verify-mcp` for shadcn/Context7.
2. Configure Gemini key or Ollama (`ollama pull llama3.2`) and review LLM answer quality/Hindi output.
3. Alembic migrations + PostgreSQL option.
4. Replace shared admin key with user accounts (roles).
5. Streaming responses (SSE) to reduce voice latency; optional Whisper STT.

## Technical decisions
| Decision | Why |
|---|---|
| Rule-based planner + LLM writer | Deterministic, testable, safe bookings, works with no key |
| BM25 default, embeddings optional | Free, offline, explainable for a ~25-chunk KB |
| Templates for transactional replies | Times/IDs cannot be hallucinated |
| DB partial unique index for bookings | Race-proof duplicate prevention |
| Lexicon sentiment | Free, Hindi-capable, explainable; documented trade-off |
| Vite proxy `/api` | No backend URL or secrets in frontend |
| Admin key instead of accounts | Fastest scoped protection for an MVP |
