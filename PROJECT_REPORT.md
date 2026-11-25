# SalesPilot AI — Project Report

**Date:** 26 November 2026  
**Status:** Functional local MVP with Gemini and knowledge retrieval enabled

## Overview

SalesPilot AI is a voice and text sales assistant for the fictional TechNova Academy. It helps prospective students learn about courses and policies, captures lead details, identifies sentiment and objections, scores leads, offers counselling appointments, and saves conversation summaries. Staff can review leads, calls, appointments, knowledge documents, and analytics in a web dashboard. Conversations support English and Hindi.

## How it works

The browser interface sends messages to a FastAPI backend. The agent retrieves relevant passages from the academy's documents, then uses Gemini to write a natural-language answer grounded in those passages. If no relevant source is found, it avoids inventing an answer. Rule-based orchestration and validated tools handle customer records, lead scoring, sentiment, appointment scheduling, and summaries; the LLM does not directly book appointments. Booking requires the caller's confirmation.

Voice input and playback use the browser Web Speech APIs. The Live Agent also supports typed messages, transcript/source display, hands-free operation, stopping speech, and call-ending phrases. Browser and device support affects voice recognition, so text entry remains available.

## Technology

- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS, and chart/UI components.
- **Backend:** Python, FastAPI, Pydantic, SQLAlchemy, and SQLite.
- **AI and retrieval:** Google Gemini, BM25 document search, Hindi query expansion/translation fallback, and optional embedding-based retrieval; demo templates remain available if no model is configured.
- **Documents and operations:** PDF/TXT/Markdown knowledge uploads, CRM, analytics, and appointment management.

## Run locally

On Windows, install Python 3.11+ and Node.js 20+, then run:

```powershell
./setup.ps1
./start-all.ps1
```

To use Gemini, copy `backend/.env.example` to `backend/.env`, set `LLM_PROVIDER=gemini` and `GEMINI_API_KEY` locally, and restart the backend. The real key belongs only in the ignored `.env` file; it is not part of this repository. The frontend is served at `http://localhost:5173`; the API is at `http://127.0.0.1:8000`.

## Scope and next steps

This repository contains a functional MVP and sample TechNova data, not a production multi-tenant service. Local persistence uses SQLite; authentication, database migrations, production hosting, and external calendar/CRM integrations are future work. Existing sample knowledge chunks may use lexical retrieval until embeddings are generated. Review [README.md](README.md) for setup, [docs/PROJECT_REPORT.md](docs/PROJECT_REPORT.md) for the full report, and [docs/SECURITY.md](docs/SECURITY.md) for security notes.
