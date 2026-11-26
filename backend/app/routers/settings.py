"""Settings: business profile, agent instructions, scheduling, scoring, voice + environment status."""
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import KnowledgeChunk
from ..security import require_admin
from ..services.llm import provider_status
from ..services.scheduling import calendar_adapter
from ..services.settings_store import DEFAULTS, all_settings, set_setting

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _exotel_stream_configured(url: str, sample_rate: int) -> bool:
    parsed = urlparse(url)
    return (sample_rate == 16000 and parsed.scheme == "wss" and bool(parsed.netloc)
            and parsed.path == "/api/telephony/exotel/stream" and parsed.query == "sample-rate=16000"
            and not parsed.username and not parsed.password and not parsed.fragment)


@router.get("/public")
def public_settings(db: Session = Depends(get_db)):
    """Non-sensitive values the customer-facing agent UI needs."""
    s = all_settings(db)
    return {"business_profile": {k: s["business_profile"][k] for k in ("company_name", "agent_name")},
            "voice": s["voice"], "lead_scoring_weights": s["lead_scoring"]["weights"], "provider": provider_status(), "auth_required": bool(get_settings().admin_api_key)}


@router.get("", dependencies=[Depends(require_admin)])
def get_all(db: Session = Depends(get_db)):
    cfg = get_settings()
    stream_configured = _exotel_stream_configured(cfg.exotel_public_wss_url, cfg.exotel_sample_rate)
    has_emb = db.execute(select(func.count(KnowledgeChunk.id)).where(KnowledgeChunk.embedding.is_not(None))).scalar_one()
    return {
        "settings": all_settings(db),
        "environment": {  # status only - secrets are never returned
            "environment": cfg.environment,
            "database": "sqlite" if cfg.database_url.startswith("sqlite") else cfg.database_url.split(":")[0],
            "provider": provider_status(cfg),
            "admin_auth_enabled": bool(cfg.admin_api_key),
            "cors_origins": cfg.cors_origin_list,
            "max_upload_mb": cfg.max_upload_mb,
            "rate_limit_per_minute": cfg.rate_limit_per_minute,
            "timezone": cfg.timezone,
            "calendar_provider": calendar_adapter().name,
            "chunks_with_embeddings": has_emb,
            "telephony": {
                "provider": "exotel",
                "phone_number": cfg.exotel_phone_number or None,
                "account_configured": bool(cfg.exotel_account_sid and cfg.exotel_api_key and cfg.exotel_api_token),
                "stream_configured": stream_configured,
                "speech_configured": bool(cfg.sarvam_api_key),
                "wss_url": cfg.exotel_public_wss_url or None,
                "ready": bool(cfg.exotel_account_sid and cfg.exotel_api_key and cfg.exotel_api_token
                             and cfg.exotel_phone_number and stream_configured
                             and cfg.sarvam_api_key),
            },
        },
    }


@router.put("/{key}", dependencies=[Depends(require_admin)])
def update(key: str, value: dict, db: Session = Depends(get_db)):
    if key not in DEFAULTS:
        raise HTTPException(404, "Unknown settings section")
    if key == "lead_scoring":
        w = value.get("weights")
        if w is not None:
            if set(w) != set(DEFAULTS["lead_scoring"]["weights"]) or any(not isinstance(v, int) or v < 0 for v in w.values()):
                raise HTTPException(422, "weights must contain intent, budget_fit, urgency, product_interest, readiness")
            if sum(w.values()) != 100:
                raise HTTPException(422, "weights must add up to 100")
    if key == "scheduling":
        sh, eh = value.get("start_hour", 10), value.get("end_hour", 18)
        if not (0 <= sh < eh <= 24):
            raise HTTPException(422, "start_hour must be before end_hour")
        if value.get("slot_minutes", 30) not in (15, 20, 30, 45, 60):
            raise HTTPException(422, "slot_minutes must be 15, 20, 30, 45 or 60")
    return set_setting(db, key, value)
