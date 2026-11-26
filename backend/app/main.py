"""FastAPI application entry point.  Run:  uvicorn app.main:app --reload --port 8000"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .routers import analytics, appointments, conversations, crm, knowledge, recordings, settings, telephony
from .seed import init_db, seed_knowledge
from .services.llm import provider_status

log = logging.getLogger("salespilot")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    seed_knowledge()
    log.info("SalesPilot AI started. LLM mode: %s", provider_status()["active"])
    yield


app = FastAPI(title="SalesPilot AI API", version="1.0.0", lifespan=lifespan)
cfg = get_settings()
app.add_middleware(CORSMiddleware, allow_origins=cfg.cors_origin_list, allow_credentials=False,
                   allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Content-Type", "X-Admin-Key"])


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):  # secure error handling: no stack traces to clients
    log.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/api/health")
def health():
    return {"status": "ok", "llm": provider_status()["active"]}


for r in (conversations.router, conversations.admin, crm.router, recordings.router, appointments.router, knowledge.router,
          analytics.router, settings.router, telephony.router):
    app.include_router(r)
