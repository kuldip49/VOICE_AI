# Interview questions and answers (66)

Answers reference real files so you can open the code while practising. ⚠️ marks tough follow-ups.

## A. Project and architecture
**1. Explain the project in 30 seconds.**
SalesPilot is an AI sales agent for a training company. Customers talk to it by voice or text in English or Hindi; it answers from the company's documents using RAG, remembers their details, scores the lead 0-100 with reasons, books counselling slots without double booking, and writes a call summary. Staff use a CRM and analytics dashboard built on the same database.

**2. Draw the architecture.**
React (Vite) in the browser with Web Speech for STT/TTS → REST JSON → FastAPI → agent orchestrator → 10 tools → services (RAG, scoring, sentiment, scheduling, summary) → SQLite via SQLAlchemy. Optional LLM (Gemini/Ollama) only writes answer text. See `docs/SYSTEM_ARCHITECTURE.md`.

**3. Why is it an agent and not a chatbot?**
It takes actions toward a goal: updates profiles, scores leads, books and cancels appointments, writes summaries, through explicit tools with validated inputs and an audit log (`agent_tool_logs`). A chatbot only replies.

**4. ⚠️ Your "agent" uses rules to pick tools. Isn't a real agent LLM-driven?**
Both are agents; the difference is who plans. I chose a deterministic planner because bookings and CRM writes must be correct and testable without an API key, and so the LLM can't trigger a booking on its own. Each tool has a Pydantic schema, so moving to Gemini function calling is a change in the planner only; validation, permissions and logging stay.

**5. What happens when a message arrives?** (`agent/orchestrator.py → handle`)
Save message, detect language, extract facts → `update_customer_profile`, `analyze_sentiment`, detect intents, run the matching tools, `update_crm_record` + `qualify_lead`, compose the reply (LLM or template), append one missing qualifying question, save reply with sources and `generated_by`.

**6. What runs if there is no API key?**
Everything. Demo mode answers by quoting the retrieved lines with a label "Template answer (no LLM)". Memory, scoring, sentiment, booking, CRM and analytics are code, not LLM.

**7. ⚠️ How do you prove an answer wasn't written by an LLM?**
Every assistant message stores `generated_by` (`demo-rules`, `gemini:model`, `ollama:model`, or `demo-rules (llm-error)`), and the UI shows it. Tests assert it (`test_agent_logs_tool_calls`).

## B. Python and FastAPI
**8. Why FastAPI?** Automatic validation with Pydantic, auto-generated OpenAPI docs at `/docs`, dependency injection (DB session, admin check, rate limit), good performance.

**9. What is dependency injection here?** `Depends(get_db)` gives each request its own session and closes it; `Depends(require_admin)` protects routers; `Depends(rate_limit)` guards chat endpoints.

**10. Sync or async endpoints?** Sync `def`; FastAPI runs them in a thread pool. SQLAlchemy sync + SQLite is simpler for an MVP. For high concurrency I'd move LLM calls to async httpx and stream responses.

**11. How are settings loaded?** `pydantic-settings` reads environment variables and `backend/.env` into a typed `Settings` object (`config.py`).

**12. How do you handle errors?** Validation errors → 422 with field messages; domain errors → 404/409 with a code (`slot_taken`); unknown errors → generic 500 while the stack trace goes to server logs only.

## C. React and frontend
**13. How is the frontend structured?** Routes per page (lazy-loaded), shadcn-style UI primitives, a typed API client, hooks for data (`useApi`), theme and voice.

**14. How does the frontend reach the backend without CORS issues in dev?** Vite proxies `/api` to port 8000. CORS is still configured for other origins.

**15. How do you handle loading, empty and error states?** `useApi` returns `loading/error/data`; pages render `Loading`, `Empty` (with an action, e.g. "Start a call") or `ErrorState` with "Try again". Backend offline shows "Cannot reach the SalesPilot backend…" (verified in browser).

**16. Why shadcn/ui?** It's copy-in source built on Radix (accessible dialogs, selects, tabs), so I own and can style the code; not a black-box dependency.

**17. Accessibility?** Radix keyboard handling, labelled icon buttons, `aria-live` transcript, visible focus ring, reduced-motion support, colour never the only signal (badges have text). Lighthouse accessibility 100 on tested pages.

## D. Database
**18. Main tables?** customers, leads, conversations, messages, customer_memories, appointments, knowledge_documents, knowledge_chunks, call_summaries, sentiment_records, agent_tool_logs, app_settings.

**19. Why is leads separate from customers?** Customer = identity; lead = sales state (score, status, interest). Keeps personal data apart from derived sales data and maps to CRM concepts.

**20. ⚠️ How exactly do you prevent double booking under concurrency?** Application check inside the transaction plus a **partial unique index** on `appointments.start_time WHERE status='booked'`. If two requests pass the check simultaneously, the database rejects the second commit; we catch `IntegrityError` and return `slot_taken`. Tested in `test_database_unique_index_blocks_race`.

**21. What happens when a lead is deleted?** ORM + FK cascades delete conversations, messages, memories, appointments, summaries, sentiment records and tool logs (`test_delete_lead_cascades`).

**22. Why SQLite and how do you move to PostgreSQL?** Zero setup for a demo. Change `DATABASE_URL`, add psycopg and Alembic migrations; the ORM code stays.

**23. ⚠️ You use `create_all`, not migrations. Problem?** Fine for a fresh demo DB, wrong for evolving production data. Alembic is the first item on the production list.

## E. REST APIs
**24. Give an example of good REST design in the project.** `POST /api/conversations` creates, `POST /api/conversations/{id}/messages` adds a message, `POST /api/appointments/{id}/cancel` is an action on a resource, `GET /api/leads?category=HOT` filters.

**25. Status codes you return?** 200, 401 (admin key), 404, 409 (slot taken / ended conversation), 413 (file too big), 415 (wrong type), 422 (validation), 429 (rate limit), 500.

**26. How is CSV export done?** `StreamingResponse` with UTF-8 BOM so Excel shows ₹ and Hindi correctly.

## F. Speech
**27. How does STT work in your app?** Browser `SpeechRecognition` with `hi-IN`/`en-IN`, interim results shown live, final text sent to the API.

**28. ⚠️ Limitations of Web Speech API?** Chrome/Edge only (Firefox none, Safari partial), Chrome sends audio to Google so it needs internet, accuracy varies with noise/accents, no control over the model. Production: streaming Whisper or a speech provider over WebSocket.

**29. TTS for Hindi?** `speechSynthesis` with a hi-IN voice; if none is installed the UI warns that replies may sound English-accented.

**30. What is barge-in?** The user can interrupt: starting to listen cancels speech (`stopSpeaking()` in `listen()`).

**31. Do you store audio?** No. Only recognised text reaches the backend.

## G. RAG and embeddings
**32. Explain RAG in your project.** Upload → extract → chunk by section → BM25 index (+embeddings optional) → retrieve top chunks → inject into prompt → answer → return sources.

**33. Why chunk by section?** A course's price, duration and batches stay together; splitting by fixed characters could separate a price from its course name.

**34. What is BM25?** Keyword ranking using term frequency, inverse document frequency and length normalisation. Rare words ("refund") matter more than common ones ("course").

**35. ⚠️ BM25 can't understand synonyms. How do you cope?** Small synonym and Hindi→English expansion table (`SYNONYMS`), and hybrid embeddings when a key is configured. For larger corpora: embeddings + vector DB.

**36. How do you stop hallucinated answers?** (1) relevance threshold, (2) out-of-vocabulary guard ("blockchain"), (3) LLM not called when nothing relevant is found, (4) prompt says use only provided context, (5) sources shown. Tests: `test_unknown_topic_not_found`, `test_llm_not_called_when_kb_has_no_answer`.

**37. ⚠️ How did you choose the threshold 3.0?** Empirically on the sample KB, checked by tests for both answerable and unanswerable questions. It must be re-tuned for a different knowledge base; the Knowledge page shows top score vs threshold to help.

**38. What are embeddings / cosine similarity?** Vectors representing meaning; cosine of the angle between them measures similarity. Used in hybrid mode (`rag.retrieve`, `_cosine`).

**39. What happens with a scanned PDF?** No extractable text → document marked "failed" with an explanation; OCR would be needed (`test_upload_pdf_without_text_is_marked_failed`).

## H. LLMs
**40. Which LLMs are supported?** Gemini via REST, any Ollama model locally; selection in `.env` (`LLM_PROVIDER=auto|gemini|ollama|demo`).

**41. What's in the prompt?** Editable system instructions, reply language, known customer facts, conversation summary, sentiment with suggested approach, retrieved chunks, last 8 messages.

**42. What if the LLM fails or times out?** `LLMError` → answer falls back to the template and is labelled `demo-rules (llm-error)` (`test_llm_failure_falls_back_to_labelled_demo`).

**43. ⚠️ How do you test LLM code without calling an LLM?** httpx `MockTransport` for provider parsing/errors and a fake provider injected into the agent to check prompt content and fallback.

## I. Memory
**44. Short vs long-term memory?** Short: messages + `conversation.state` (offered slots, pending booking, what we asked). Long: `customer_memories` key/value facts across conversations.

**45. How do you avoid sending the whole history?** Last 8 messages verbatim; older ones compressed into `memory_summary`.

**46. Example of context use?** "What is the price?" → interest remembered (AI & ML) → query expanded → ₹45,000 returned (`test_contextual_memory_within_conversation`). A bare "Rahul" after "May I know your name?" is stored as the name.

**47. Can users see/delete what is remembered?** Yes: Leads → profile → Saved facts → delete one or all.

## J. Sentiment and lead qualification
**48. How does sentiment work?** Lexicon of cue phrases per label in English/Hindi/Hinglish, priority order, confidence lowered for mixed signals, objection detection, recommended action.

**49. ⚠️ Why not an ML sentiment model?** Free, offline, explainable, Hindi-capable without training data. Trade-off: misses sarcasm and unseen phrasing. Next step: multilingual transformer (e.g. XLM-R based) or the LLM, evaluated on labelled call data.

**50. Sentiment vs intent?** "Too expensive" = hesitant but still interested; "Thanks, not interested" = polite but negative. Separate signals, separate fields.

**51. Explain the score for Rahul.** Intent high 30/30, budget ₹20k vs ₹45k (44%) 6/20, timeline 1-3 months 10/20, interest 15/15, readiness (appointment yes, contact no) 8/15 = 69 → WARM.

**52. Where does the course price come from?** Parsed from the knowledge base chunk (`find_product_price`), not hardcoded.

**53. How would you change the formula?** Weights in Settings (must sum to 100) or code in `services/scoring.py`.

## K. Appointments
**54. Booking flow?** Request → `get_available_slots` → customer picks → agent asks to confirm (nothing saved) → "yes" → `book_appointment(confirmed=True)` → DB.

**55. What if the slot was taken in between?** `slot_taken` error, agent apologises and offers fresh slots.

**56. Google Calendar?** Not implemented. `CalendarAdapter` protocol with `on_booked/on_cancelled` is the seam for a `GoogleCalendarAdapter`.

## L. Security
**57. How are API keys protected?** Only in backend `.env`, git-ignored, never sent to the frontend, status-only in Settings; test checks the key never appears in responses.

**58. ⚠️ Can a prompt injection make the agent delete data?** The LLM has no tool access; tools are chosen by code, arguments validated, and no delete tool is exposed to the agent. Document-borne injection could still distort an answer's wording, which is why sources are shown.

**59. How is the CRM protected?** `ADMIN_API_KEY` header check on admin routers; production plan is OIDC users with roles.

## M. Scalability and deployment
**60. Can it handle 100,000 users?** Not as-is, and I haven't load-tested it. The design: stateless API pods, PostgreSQL, Redis, queues, vector DB, LLM router, streaming voice services. See `docs/SCALABILITY.md`.

**61. Registered vs concurrent?** 100k registered with ~5% daily active and a 15% peak hour ≈ 750 concurrent conversations ≈ 50 msgs/s: assumptions to validate.

**62. What would break first?** SQLite writes and the per-process BM25 index and rate limiter, then LLM latency/cost.

**63. How do you deploy?** Locally via PowerShell scripts; Docker compose files exist but weren't built in my environment. Cheapest hosted path: a small VM or free-tier container host + managed Postgres, HTTPS in front.

## N. Business, limitations, future
**64. How would you price it?** Subscription tiers + per-conversation overage because LLM/speech costs scale with usage (`docs/BUSINESS_MODEL.md`).

**65. Biggest limitations?** Browser-only voice; rule-based NLP misses unusual phrasing; English KB answered in Hindi template mode mixes languages unless an LLM translates; single shared admin key; no load test.

**66. Next three improvements?** LLM function calling with the same validated tools; streaming voice over WebSocket with Whisper; PostgreSQL + auth + multi-tenancy.
