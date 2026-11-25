# PROJECT_PROGRESS

Last update: 2026-11-26 (Twilio inbound phone integration). Statuses: NOT STARTED · IN PROGRESS · BLOCKED · IMPLEMENTED · TESTED · VERIFIED (= tested + checked in a real browser).

## Current status
Functional MVP rebranded as Kiln & Signal. The inbound Twilio phone-call backend now reuses the Gemini/RAG sales agent, CRM, appointment and summary pipeline, with signed webhooks and English/Hindi keypad language choice. Gemini is configured in the local ignored `backend/.env`; no API keys are stored in this repository. Live phone calls still need a Twilio voice-capable number and a public HTTPS URL configured in Twilio Console.

## Features
| Feature | Status | Evidence |
|---|---|---|
| Text conversation | VERIFIED | `test_full_sales_workflow`, browser steps 2-10 |
| Voice: STT/TTS, mic meter, hands-free, barge-in, mute, stop | IMPLEMENTED | Code + unsupported/blocked-mic UI verified; live mic not testable headless. **Test in Chrome/Edge on PC** |
| Inbound phone calls (Twilio, speech turns, Gemini/RAG, CRM, summaries) | IMPLEMENTED (external setup pending) | FastAPI Twilio webhook routes and setup guide added; live carrier call not configured | Requires public HTTPS backend, Twilio voice number/auth token, and Twilio Console webhook settings; dependency install required. |
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
| Kiln & Signal visual identity, monochrome theme, subtle motion and reduced-motion support | IMPLEMENTED | Updated shared CSS tokens, app shell, dashboard hero, page title, favicon and user-facing app labels; production build passes |
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
| Frontend lint | **Passed with 5 warnings** (existing Fast Refresh/effect guidance) |
| Local HTTP/browser smoke | **Not completed**; the sandbox blocked local socket access, and the browser safety layer could not identify the active URL |
| Live Gemini generation | **Passed**, active model label confirmed without printing the key |
| Live Gemini embedding + hybrid retrieval | **Passed** using an in-memory SQLite knowledge base; the persistent local database was not changed |
| Docker Compose configuration | **Passed** with `docker compose config --quiet`; Docker Desktop could not start, so image build remains unverified |
| Browser microphone | Not live-tested on this device; the browser UI, unsupported, and blocked-mic paths remain covered by the earlier browser checks |
| Visual browser screenshot audit | Not completed; the Windows computer-use safety layer could not resolve the active browser URL |
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
- Live microphone test needs a real browser and microphone on the target PC.
- A screenshot-based visual audit should be completed in a normal browser session; the UI safety layer could not identify the active browser URL during this refresh.

## Next five priorities
1. Run the refreshed interface in Chrome/Edge at desktop and mobile widths; test English/Hindi speech on the target microphone.
2. Backfill embeddings for existing knowledge chunks if hybrid search is desired throughout the sample KB.
3. Add a Google Calendar adapter if an external calendar is required.
4. Add Alembic migrations, PostgreSQL, authentication and tenant isolation before a production multi-user deployment.
5. Consider streaming responses and dedicated STT/TTS if phone-line voice becomes a requirement.

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
