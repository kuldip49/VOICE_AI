# Live coding: common change requests

Run `.\run-tests.ps1` after each change.

## 1. Change the lead scoring formula
- **No code:** Settings → Lead scoring → change points (must total 100) and thresholds.
- **Code:** `backend/app/services/scoring.py → score_lead()`. Example: make "within 1 month" worth full urgency:
  ```python
  URGENCY_FRACTION = {"immediately": 1.0, "within 1 month": 1.0, "1-3 months": 0.5, "3+ months": 0.2}
  ```
  Add a new criterion: add a weight in `settings_store.py → DEFAULTS["lead_scoring"]["weights"]`, compute it in `score_lead`, add a label in `frontend/src/pages/LiveAgent.tsx → CRITERIA` and `Settings.tsx → CRITERIA`, and update the validation in `routers/settings.py` (weights set).

## 2. Add a new language (e.g. Marathi `mr`)
1. Backend: `routers/conversations.py → StartIn.language` pattern `^(en|hi|mr)$`.
2. `agent/orchestrator.py`: add `"mr"` entries to every template in `T` and `QUAL_Q`; extend `detect_language` (Devanagari is shared with Hindi, so use the conversation language or keywords).
3. `services/rag.py → SYNONYMS`: add Marathi words mapped to English KB terms.
4. Frontend: `LiveAgent.tsx → LOCALE` add `mr: 'mr-IN'` and a `SelectItem`.
5. Check Chrome supports `mr-IN` recognition and a voice exists.

## 3. Add a knowledge document
UI: Knowledge base → drop a PDF/TXT. Use `## Heading` sections for best chunks. Or put a `.txt` in `backend/data/knowledge/` and run `.\reset-demo-data.ps1`. Verify with "Test retrieval".

## 4. Change appointment availability
UI: Settings → Appointment availability (days, hours, slot length, window). Code defaults: `settings_store.py → DEFAULTS["scheduling"]`; logic in `services/scheduling.py → _grid()`.

## 5. Add a CRM field (e.g. "city")
1. `models.py → Customer`: `city: Mapped[str | None] = mapped_column(String(80))` (delete the dev DB or add an Alembic migration).
2. Extraction: `services/extraction.py` add a regex (`r"\bfrom ([A-Z][a-z]+)"`) and `city` on `Extracted`.
3. Tool: `agent/tools.py → UpdateProfileIn` add `city`, and include it in the loop in `t_update_customer_profile`.
4. API output: `serializers.py → customer()`.
5. CSV: `routers/crm.py → export_csv` header + row.
6. Frontend: `lib/api.ts → Customer` type, show it in `Crm.tsx` profile `<dl>`.
7. Test: add an assertion in `tests/test_units.py`.

## 6. Modify the AI system prompt
UI: Settings → Agent instructions (stored in `app_settings`). Default text: `settings_store.py → DEFAULTS["agent_instructions"]`. Prompt assembly: `orchestrator.py → _llm_answer()`.

## 7. Add a new agent tool (e.g. `send_brochure`)
1. `agent/tools.py`: input model
   ```python
   class BrochureIn(BaseModel):
       customer_id: int = Field(gt=0)
       course: str = Field(min_length=2, max_length=200)
   def t_send_brochure(ctx: ToolContext, a: BrochureIn) -> dict:
       c = ctx.db.get(Customer, a.customer_id)
       if not c or not c.email:
           raise ToolError("no_email", "Customer has no email address")
       # MVP: record the request; a real mailer would be called here
       return {"queued_for": c.email, "course": a.course}
   ```
   Register: `TOOLS["send_brochure"] = (BrochureIn, t_send_brochure)` (it becomes allowed via `AGENT_ALLOWED = set(TOOLS)`; remove it from that set to restrict).
2. `orchestrator.py`: add an intent regex (e.g. `brochure|details by email`) in `_intents`, call `self.tool("send_brochure", ...)` in `handle`, add a reply template.
3. `_brief()` for the trace text; a test in `tests/test_agent.py`.
