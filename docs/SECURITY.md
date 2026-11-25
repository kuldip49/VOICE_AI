# Security and data privacy

MVP-level controls, honestly scoped. No compliance certification is claimed.

## Implemented
| Control | How | Where |
|---|---|---|
| Secrets in environment only | `backend/.env` (git-ignored); frontend never receives keys; `/api/settings` returns "configured / not set", never values | `config.py`, `routers/settings.py`, test `test_admin_key_protects_crm` |
| Admin access control | When `ADMIN_API_KEY` is set, CRM/knowledge/analytics/settings endpoints require `X-Admin-Key` (constant-time compare). Customer chat stays public | `security.py` |
| Input validation | Pydantic on every body and every agent tool argument (lengths, enums, regex, email format) | routers, `agent/tools.py` |
| No arbitrary execution | Agent can only call 10 whitelisted tools; no SQL, shell or code-eval path exists | `agent/tools.py → AGENT_ALLOWED` |
| SQL injection | SQLAlchemy ORM with bound parameters only | all DB access |
| Upload safety | Extension whitelist (.pdf/.txt/.md), size limit (5 MB default), PDF magic-byte check, binary check for text, filename sanitised | `routers/knowledge.py` |
| Rate limiting | Per-IP sliding window on public chat endpoints (429) | `security.py` |
| CORS | Explicit origin list, limited methods/headers | `main.py` |
| Error handling | Generic 500 message to clients, details only in server logs | `main.py` |
| Booking integrity | Confirmation required; DB unique index prevents double booking | `scheduling.py` |
| Data minimisation | Contact details only stored if the customer volunteers them; unknowns stay unknown | `extraction.py` |
| Right to erasure | Delete lead (cascades to conversations, messages, memories, appointments, summaries, sentiment, tool logs); forget individual memories | `routers/crm.py` |
| No audio storage | Audio never reaches the backend; only recognised text is stored | `useVoice.ts` |
| Unguessable conversation IDs | UUID4 | `models.py` |

## Data storage and retention
- Stored: customer name/email/phone (if given), messages, derived lead data, sentiment, summaries, appointments, tool logs, uploaded documents' text.
- Location: local SQLite file `backend/data/salespilot.db`.
- Retention: indefinite in the MVP. Production: configurable retention (e.g. delete conversations after 12 months, anonymise lost leads after 6 months) as a scheduled job.

## Encryption
- **In transit**: local dev is plain HTTP on localhost. Production must terminate TLS (HTTPS) at the load balancer / gateway; HSTS on.
- **At rest**: SQLite file is not encrypted. Production: managed PostgreSQL with storage encryption (KMS keys), encrypted backups, encrypted object storage.
- Third parties: in LLM mode, the customer message, retrieved chunks and known profile facts are sent to the LLM provider (Gemini). Chrome speech recognition sends audio to Google. Ollama keeps everything on the machine.

## Consent
Production must show, before the first message: that the user is talking to an AI, what is stored, that voice is processed by the browser/speech provider, and a link to the privacy policy; recording consent if raw audio is ever stored (it is not today). India's DPDP Act 2023 and GDPR (for EU visitors) apply to personal data.

## Known gaps (production backlog)
1. Real user accounts with roles (admin, sales rep, viewer) via OAuth/OIDC instead of one shared key.
2. Multi-tenant isolation (`tenant_id` + PostgreSQL row-level security).
3. Redis-based distributed rate limiting (current limiter is per process, in memory).
4. Prompt-injection hardening for uploaded documents (documents are trusted company content today).
5. Audit log for admin actions, field-level encryption for phone/email.
6. Automated dependency/vulnerability scanning in CI.
