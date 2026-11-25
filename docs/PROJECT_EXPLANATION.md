# Kiln & Signal in plain language

## The problem
TechNova Academy gets enquiries at all hours. Sales staff answer the same questions (fees, batches, refunds) again and again, forget to note who was serious, and book counselling calls by back-and-forth messages. Leads go cold.

## What Kiln & Signal does
It is a digital sales assistant called **Nova** that:

1. **Talks** with a prospective student by voice or text, in English or Hindi.
2. **Answers only from company documents** (course catalogue, policies, FAQ). If the answer is not in them it says so instead of making something up.
3. **Remembers** what the caller said (name, course interest, budget, timeline) and does not ask again.
4. **Scores the lead** from 0 to 100 and labels it Hot, Warm or Cold, with a written reason for every point.
5. **Reads the mood** of each message (interested, hesitant, frustrated…) and suggests how to respond (e.g. "too expensive" → explain EMI).
6. **Books a counselling slot** from real free times, only after the caller says yes, and never double-books.
7. **Writes a call summary** with the recommended next step.
8. Shows all of it in a **CRM and analytics dashboard** built from the stored records.

## One conversation, step by step
| Caller says | What happens inside |
|---|---|
| "I want to learn AI, tell me about your courses" | Browser turns speech into text → backend searches the documents → finds the AI course section → replies with price, duration, batches and cites `course_catalog.txt` → asks "May I know your name?" |
| "My name is Rahul" | Name saved to the customer profile and to long-term memory |
| "My budget is around 20,000" | Budget saved; score compares ₹20,000 with the ₹45,000 course price (44%) and gives 6/20 for budget fit |
| "That's too expensive" | Sentiment = hesitant, objection = price → agent looks up EMI and discount policies |
| "Can I book a counselling appointment?" | Agent fetches the next 4 free slots from the database |
| "2" → "yes" | Slot 2 is held, the agent asks for confirmation, and only then writes the appointment |
| End call | Summary, objections, sentiment and follow-up saved; dashboard numbers update |

## Two modes
- **Demo mode (default, free, offline):** no AI model. Answers are the relevant lines of the retrieved documents in a fixed template. The UI labels them "Template answer (no LLM)".
- **LLM mode:** with a Gemini key or local Ollama, the model rewrites the retrieved facts into a natural answer. It is told to use only those facts, and it is never asked at all when the documents have no answer.

Everything else (memory, scoring, sentiment, booking, CRM, analytics) works the same in both modes, because those parts are deterministic code, not the LLM.

## What it is not
- Not a phone-line product yet: voice runs in the browser (Chrome/Edge).
- Not connected to Google Calendar or Salesforce: it has its own calendar and CRM, with clear extension points.
- Not proven at large scale: the 100,000-user design is documented, not load-tested.
