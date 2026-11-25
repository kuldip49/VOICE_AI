# Demo script

## 30-second introduction
"Kiln & Signal is a considered customer-conversation desk for a training company. A prospective student talks to it by voice or text in English or Hindi. It answers from the company's documents, remembers the student's needs, scores the lead with a reason for each point, books a counselling call after confirmation, and gives the sales team a clear follow-up summary. The workspace has a quiet monochrome design; Gemini or a local model can write grounded answers."

## Before the demo (5 minutes earlier)
1. `.\reset-demo-data.ps1` (fresh DB), then `.\start-all.ps1`.
2. Open Chrome/Edge at `http://localhost:5173/agent`, allow the microphone once.
3. Check the top-right badge (Demo mode or your LLM). Test one voice sentence.
4. Backup plan: if the mic or internet fails, type the same sentences (identical behaviour).

## 5-minute script
| Time | Say | Do |
|---|---|---|
| 0:00 | **Problem.** "Institutes lose enquiries after hours, reps repeat the same answers, and leads aren't qualified consistently." | Overview page (empty state) |
| 0:30 | **Solution.** "Nova is a digital sales rep available 24/7, connected to a CRM." | Live agent → Start call |
| 0:45 | **Architecture** (one sentence). "React voice UI, FastAPI backend, an agent with ten validated tools, RAG over company documents, SQLite." | Point at agent actions trace later |
| 1:00 | Speak: *"Hello, I want to learn AI and machine learning. Can you tell me about your courses?"* | Show answer, source chip `course_catalog.txt`, the follow-up question |
| 1:30 | *"My name is Rahul."* *"My budget is around 20,000."* *"I want to start next month."* | Caller panel fills; score rises; open "Why this score" |
| 2:10 | *"That's too expensive for me."* | Sentiment hesitant + price objection; EMI/discount answer |
| 2:30 | *"Do you offer a blockchain course?"* | "Not in our knowledge base": no hallucination |
| 2:45 | *"Can I book a counselling appointment?"* → *"Two"* → *"Yes"* | Slots from DB, confirmation step, booking #. Expand "agent actions" to show `book_appointment` |
| 3:20 | End call | Summary + next step |
| 3:35 | **CRM** | Leads → Rahul → profile, score reasons, transcript, saved facts (delete one to show privacy control) |
| 3:55 | **Appointments + Analytics** | Booking in the week view; charts from real rows |
| 4:15 | **Hindi** (optional): switch to हिन्दी, new call, *"रिफंड की नीति क्या है?"* | |
| 4:30 | **Commercial + scale.** "Subscription plus usage; LLM cost is under a rupee per conversation with browser voice. For 100k users: stateless API pods, Postgres, Redis, vector DB, streaming voice; designed, not load-tested." | |
| 4:50 | **Close.** "Everything you saw is stored data; 60 backend tests and a 20-step browser workflow are recorded as passing." | |

## Likely questions during the demo
- "Is that a real AI answer?" → Point at the badge "Template answer (no LLM)" or "Written by gemini:…".
- "What if two people book the same slot?" → DB unique index; show the test name.
- "Can it work for another business?" → Settings → business profile + upload new documents in Knowledge base.
