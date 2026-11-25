# Business model and commercial feasibility

All numbers here are **illustrative estimates with stated assumptions**. No market research was done and no customer demand has been validated. Editable cost model: [cost_model.csv](cost_model.csv) (open in Excel).

## Target customers
Small and mid-sized businesses whose sales start with many similar enquiries: training institutes and ed-tech (like TechNova), coaching centres, real-estate developers, clinics, travel agencies, B2B SaaS with inbound demos.

## Problem and value proposition
| Pain | SalesPilot answer |
|---|---|
| Enquiries after hours go unanswered | 24/7 agent by voice or chat |
| Reps repeat the same answers | Grounded answers from the company's own documents |
| Leads not qualified consistently | Transparent 0-100 score with reasons |
| Booking calls takes back-and-forth | Real-time slot booking with confirmation |
| Conversation insight is lost | Summaries, objections, sentiment, analytics |
| Customers prefer Hindi | English + Hindi out of the box |

## Revenue model
SaaS subscription per business (workspace) + usage overage per conversation minute/message, because LLM and speech costs scale with usage.

| Plan (illustrative, INR/month) | Price | Includes | For |
|---|---|---|---|
| Starter | ₹2,999 | 1 agent, 500 conversations, text + browser voice, 20 documents, CSV export | Single-location institute |
| Growth | ₹9,999 | 3 agents, 3,000 conversations, analytics, calendar integration, 3 users | Growing team |
| Business | ₹29,999 | 10,000 conversations, phone-line voice, CRM integrations, SSO, priority support | Multi-branch |
| Overage | ₹1.5 per extra conversation | | |

## Cost drivers (per conversation, estimate)
Assumptions: 10 customer messages per conversation, ~1,500 input + 150 output tokens per LLM call, browser voice (no paid STT/TTS).

| Item | Assumption | Est. cost |
|---|---|---|
| LLM (small/flash-class model) | 10 calls × 1,650 tokens at ~$0.10–0.40 per 1M tokens | ₹0.15–0.60 |
| Embeddings | negligible after ingestion | < ₹0.01 |
| Paid streaming STT+TTS (only for phone/advanced voice) | 4 min at ~$0.01–0.02/min each | ₹7–14 |
| Infrastructure share | small VM/containers + Postgres for ~1k businesses | ₹0.2–0.5 |

Prices change often; re-check provider pricing pages before using these numbers. The big lever is voice: browser speech is free, telephony-grade speech is the dominant cost.

## Infrastructure (estimate)
- Pilot: 1 small VM or free-tier container host + managed Postgres starter: ~₹1,500–4,000/month.
- 100k registered users (see SCALABILITY.md): 3–6 API containers, Postgres with replica, Redis, workers: roughly ₹40k–1.5L/month before LLM/speech usage.

## Customer acquisition
Ed-tech and coaching communities, partnerships with CRM/website agencies, free tier for one agent, case studies with measured before/after response time and booking rate.

## Differentiation
- Grounded-only answers with visible sources and an explicit "not in our knowledge base" behaviour.
- Explainable lead scores (every point has a reason) instead of a black-box number.
- Hindi + English, priced for Indian SMBs.
- Works with zero paid APIs for a pilot.

## ROI example for a business (illustrative)
Institute with 600 enquiries/month, average course ₹30,000, 4% current conversion → 24 enrolments. If faster 24/7 response + booked counselling lifts conversion to 5% → 30 enrolments → +6 × ₹30,000 = **₹1.8L extra revenue/month** vs a ₹9,999 plan. The uplift is an assumption to test in a pilot, not a promise.
