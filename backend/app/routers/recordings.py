"""Private call recording storage and manager playback endpoints."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import DATA_DIR
from ..database import get_db
from ..models import CallRecording, Conversation
from ..security import require_admin

router = APIRouter(prefix="/api", tags=["call recordings"], dependencies=[Depends(require_admin)])
RECORDING_DIR = DATA_DIR / "recordings"
MAX_RECORDING_BYTES = 25 * 1024 * 1024
ALLOWED_AUDIO_TYPES = {"audio/webm", "audio/mp4", "audio/ogg", "audio/wav", "audio/mpeg"}
EXTENSIONS = {"audio/webm": ".webm", "audio/mp4": ".mp4", "audio/ogg": ".ogg", "audio/wav": ".wav", "audio/mpeg": ".mp3"}


def _row(recording: CallRecording, conversation: Conversation) -> dict:
    return {
        "id": recording.id,
        "conversation_id": recording.conversation_id,
        "customer_id": recording.customer_id,
        "customer_name": conversation.customer.name or f"Unnamed caller #{recording.customer_id}",
        "started_at": conversation.started_at.isoformat() if conversation.started_at else None,
        "ended_at": conversation.ended_at.isoformat() if conversation.ended_at else None,
        "duration_seconds": recording.duration_seconds,
        "size_bytes": recording.size_bytes,
        "content_type": recording.content_type,
        "created_at": recording.created_at.isoformat() if recording.created_at else None,
    }


@router.post("/conversations/{conversation_id}/recording")
async def upload_recording(conversation_id: str, file: UploadFile, duration_seconds: int = 0,
                           db: Session = Depends(get_db)):
    conversation = db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(404, "Conversation not found")
    if conversation.channel != "voice":
        raise HTTPException(400, "Only voice conversations can have audio recordings")
    if db.execute(select(CallRecording.id).where(CallRecording.conversation_id == conversation_id)).first():
        raise HTTPException(409, "A recording already exists for this conversation")
    content_type = (file.content_type or "").split(";")[0].lower()
    if content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(415, "Unsupported audio format")
    content = await file.read(MAX_RECORDING_BYTES + 1)
    if not content or len(content) > MAX_RECORDING_BYTES:
        raise HTTPException(413, "Recording must be between 1 byte and 25 MB")

    RECORDING_DIR.mkdir(parents=True, exist_ok=True)
    storage_key = f"{uuid.uuid4().hex}{EXTENSIONS[content_type]}"
    path = RECORDING_DIR / storage_key
    try:
        path.write_bytes(content)
        recording = CallRecording(conversation_id=conversation_id, customer_id=conversation.customer_id,
                                  storage_key=storage_key, content_type=content_type, size_bytes=len(content),
                                  duration_seconds=max(0, min(duration_seconds, 7200)))
        db.add(recording)
        db.commit()
        db.refresh(recording)
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    return _row(recording, conversation)


@router.get("/recordings")
def list_recordings(db: Session = Depends(get_db)):
    rows = db.execute(select(CallRecording, Conversation).join(
        Conversation, CallRecording.conversation_id == Conversation.id
    ).order_by(CallRecording.created_at.desc()).limit(500)).all()
    return [_row(recording, conversation) for recording, conversation in rows]


@router.get("/recordings/{recording_id}/audio")
def play_recording(recording_id: int, db: Session = Depends(get_db)):
    recording = db.get(CallRecording, recording_id)
    if not recording:
        raise HTTPException(404, "Recording not found")
    path = RECORDING_DIR / Path(recording.storage_key).name
    if not path.is_file():
        raise HTTPException(404, "Recording file is missing")
    return FileResponse(path, media_type=recording.content_type, filename=f"call-{recording.id}{path.suffix}",
                        content_disposition_type="inline", headers={"Cache-Control": "private, no-store"})
