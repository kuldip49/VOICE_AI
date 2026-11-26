"""Bidirectional Exotel AgentStream bridge with Sarvam streaming speech I/O."""
from __future__ import annotations

import asyncio
import base64
import binascii
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlencode

import websockets
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from ..config import Settings

log = logging.getLogger("salespilot.telephony.exotel")

SAMPLE_RATE = 16000
EXOTEL_MEDIA_CHUNK_BYTES = 3200  # 100 ms of mono linear16 PCM at 16 kHz.
MAX_EXOTEL_EVENT_CHARS = 1_500_000

StartCall = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
HandleTranscript = Callable[[str], Awaitable[dict[str, Any] | None]]
FinishCall = Callable[[], Awaitable[None]]
SwitchLanguage = Callable[[], Awaitable[dict[str, Any] | None]]


class ExotelStreamSession:
    def __init__(self, socket: WebSocket, settings: Settings, *, start_call: StartCall,
                 handle_transcript: HandleTranscript, finish_call: FinishCall,
                 switch_language: SwitchLanguage):
        self.socket = socket
        self.settings = settings
        self.start_call = start_call
        self.handle_transcript = handle_transcript
        self.finish_call = finish_call
        self.switch_language = switch_language
        self.speech_socket = None
        self.stream_sid = ""
        self.call_sid = ""
        self.started = False
        self.stopping = False
        self.ending = False
        self.output_sequence = 0
        self.output_chunk = 0
        self.started_at = time.monotonic()
        self.send_lock = asyncio.Lock()
        self.turn_lock = asyncio.Lock()
        self.playback_task: asyncio.Task | None = None
        self.reply_task: asyncio.Task | None = None

    def _stt_url(self) -> str:
        query = urlencode({
            "model": self.settings.sarvam_stt_model,
            "language_code": "auto",
            "stream_type": "fast",
            "endpointing": "vad",
            "encoding": "linear16",
            "sample_rate": str(SAMPLE_RATE),
        })
        return f"wss://api.sarvam.ai/speech-to-text-realtime/ws?{query}"

    async def run(self) -> None:
        await self.socket.accept()
        try:
            async with websockets.connect(
                self._stt_url(),
                additional_headers={"api-subscription-key": self.settings.sarvam_api_key},
                open_timeout=12,
                ping_interval=20,
                ping_timeout=20,
                max_size=1_000_000,
            ) as speech_socket:
                self.speech_socket = speech_socket
                speech_reader = asyncio.create_task(self._read_speech_events())
                try:
                    await self._read_exotel_events()
                finally:
                    self.stopping = True
                    if self.speech_socket:
                        try:
                            await self.speech_socket.send(json.dumps({"event": "end"}))
                        except Exception:
                            pass
                    speech_reader.cancel()
                    await asyncio.gather(speech_reader, return_exceptions=True)
        except WebSocketDisconnect:
            pass
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Exotel voice stream failed")
            await self._close_socket(1011, "Voice service unavailable")
        finally:
            self.stopping = True
            await self._cancel_playback()
            if self.reply_task and not self.reply_task.done():
                self.reply_task.cancel()
                await asyncio.gather(self.reply_task, return_exceptions=True)
            if self.started:
                try:
                    await self.finish_call()
                except Exception:
                    log.exception("Could not finalize Exotel call %s", self.call_sid)

    async def _read_exotel_events(self) -> None:
        while not self.stopping:
            event = await self.socket.receive()
            if event.get("type") == "websocket.disconnect":
                return
            raw = event.get("text")
            if raw is None and event.get("bytes"):
                raw = event["bytes"].decode("utf-8", errors="strict")
            if not isinstance(raw, str) or len(raw) > MAX_EXOTEL_EVENT_CHARS:
                log.warning("Rejected oversized or non-text Exotel stream event")
                await self._close_socket(1009, "Invalid stream event")
                return
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                log.warning("Rejected malformed Exotel stream event")
                await self._close_socket(1003, "Invalid JSON event")
                return
            if not isinstance(message, dict):
                continue

            event_name = message.get("event")
            if event_name == "connected":
                continue
            if event_name == "start":
                await self._on_start(message)
            elif event_name == "media":
                await self._on_media(message)
            elif event_name == "dtmf":
                await self._on_dtmf(message)
            elif event_name == "stop":
                return
            elif event_name in {"mark", "clear"}:
                continue

    async def _on_start(self, message: dict[str, Any]) -> None:
        if self.started:
            return
        info = message.get("start") if isinstance(message.get("start"), dict) else {}
        sample_rate = info.get("media_format", {}).get("sample_rate") if isinstance(info.get("media_format"), dict) else None
        if sample_rate and int(sample_rate) != SAMPLE_RATE:
            log.error("Exotel stream sample rate mismatch: received %s, expected %s", sample_rate, SAMPLE_RATE)
            await self._close_socket(1008, "Configure Exotel stream at 16000 Hz")
            return
        self.stream_sid = str(message.get("stream_sid") or info.get("stream_sid") or "")
        self.call_sid = str(info.get("call_sid") or message.get("call_sid") or "")
        if not self.stream_sid or not self.call_sid:
            log.warning("Exotel start event did not include a stream SID and call SID")
            await self._close_socket(1008, "Missing call metadata")
            return
        started = await self.start_call(info)
        self.started = True
        greeting = str(started.get("greeting") or "Hello. How can I help you today?")
        language = str(started.get("language") or "en")
        self.playback_task = asyncio.create_task(self._speak(greeting, language))

    async def _on_media(self, message: dict[str, Any]) -> None:
        if not self.started or self.stopping or not self.speech_socket:
            return
        media = message.get("media")
        payload = media.get("payload") if isinstance(media, dict) else None
        if not isinstance(payload, str) or len(payload) > 900_000:
            return
        try:
            base64.b64decode(payload, validate=True)
        except (ValueError, binascii.Error):
            return
        await self.speech_socket.send(json.dumps({"event": "audio_input", "audio": payload}))

    async def _on_dtmf(self, message: dict[str, Any]) -> None:
        detail = message.get("dtmf") if isinstance(message.get("dtmf"), dict) else {}
        if str(detail.get("digit", "")) != "9" or not self.started:
            return
        await self._barge_in()
        async with self.turn_lock:
            result = await self.switch_language()
            if result and result.get("reply"):
                await self._start_speech(str(result["reply"]), str(result.get("language") or "en"))

    async def _read_speech_events(self) -> None:
        try:
            async for raw in self.speech_socket:
                if self.stopping:
                    return
                if not isinstance(raw, str):
                    continue
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(message, dict):
                    continue
                event_name = message.get("event")
                if event_name in {"vad.speech_start", "speech_start"}:
                    await self._barge_in()
                elif event_name == "transcript.final":
                    text = str(message.get("text") or "").strip()
                    if text and not self.ending:
                        self.reply_task = asyncio.create_task(self._handle_turn(text))
                elif event_name == "error":
                    log.error("Sarvam realtime STT error: %s", message.get("message", "unknown error"))
                    if message.get("is_fatal"):
                        await self._close_socket(1011, "Speech recognition unavailable")
                        return
        except asyncio.CancelledError:
            raise
        except Exception:
            if not self.stopping:
                log.exception("Sarvam speech stream failed for Exotel call %s", self.call_sid or "unknown")
                await self._close_socket(1011, "Speech recognition stream failed")

    async def _handle_turn(self, text: str) -> None:
        async with self.turn_lock:
            if self.stopping or self.ending:
                return
            await self._cancel_playback()
            result = await self.handle_transcript(text)
            if not result:
                return
            reply = str(result.get("reply") or "")
            language = str(result.get("language") or "en")
            self.ending = bool(result.get("hangup"))
            await self._start_speech(reply, language, close_after=self.ending)

    async def _barge_in(self) -> None:
        if self.playback_task and not self.playback_task.done():
            await self._send_exotel({"event": "clear", "stream_sid": self.stream_sid})
            await self._cancel_playback()

    async def _cancel_playback(self) -> None:
        task = self.playback_task
        self.playback_task = None
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def _start_speech(self, text: str, language: str, *, close_after: bool = False) -> None:
        if not text or self.stopping:
            return
        self.playback_task = asyncio.create_task(self._speak(text, language, close_after=close_after))
        await self.playback_task

    async def _speak(self, text: str, language: str, *, close_after: bool = False) -> None:
        lang = "hi-IN" if language == "hi" else "en-IN"
        speaker = self.settings.sarvam_voice_hi if language == "hi" else self.settings.sarvam_voice_en
        url = "wss://api.sarvam.ai/text-to-speech/ws?" + urlencode({
            "model": self.settings.sarvam_tts_model,
            "send_completion_event": "true",
        })
        cancelled = False
        try:
            async with websockets.connect(
                url,
                additional_headers={"api-subscription-key": self.settings.sarvam_api_key},
                open_timeout=12,
                ping_interval=20,
                ping_timeout=20,
                max_size=1_000_000,
            ) as tts:
                await tts.send(json.dumps({"type": "config", "data": {
                    "language_code": lang,
                    "speaker": speaker,
                    "speech_sample_rate": SAMPLE_RATE,
                    "output_audio_codec": "linear16",
                    "min_buffer_size": 30,
                    "max_chunk_length": 150,
                }}))
                await tts.send(json.dumps({"type": "text", "data": {"text": text[:2500]}}))
                await tts.send(json.dumps({"type": "flush"}))
                pending = bytearray()
                async for raw in tts:
                    if self.stopping:
                        return
                    if not isinstance(raw, str):
                        continue
                    try:
                        response = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if response.get("type") == "error":
                        log.error("Sarvam TTS error: %s", (response.get("data") or {}).get("message", "unknown error"))
                        return
                    if response.get("type") == "event" and (response.get("data") or {}).get("event_type") == "final":
                        break
                    if response.get("type") != "audio":
                        continue
                    encoded = (response.get("data") or {}).get("audio")
                    if not isinstance(encoded, str):
                        continue
                    try:
                        pending.extend(base64.b64decode(encoded, validate=True))
                    except (ValueError, binascii.Error):
                        continue
                    while len(pending) >= EXOTEL_MEDIA_CHUNK_BYTES:
                        frame = bytes(pending[:EXOTEL_MEDIA_CHUNK_BYTES])
                        del pending[:EXOTEL_MEDIA_CHUNK_BYTES]
                        await self._send_media(frame)
                        await asyncio.sleep(len(frame) / (SAMPLE_RATE * 2))
                if pending and not self.stopping:
                    aligned = ((len(pending) + 319) // 320) * 320
                    pending.extend(b"\x00" * (aligned - len(pending)))
                    if len(pending) < EXOTEL_MEDIA_CHUNK_BYTES:
                        pending.extend(b"\x00" * (EXOTEL_MEDIA_CHUNK_BYTES - len(pending)))
                    frame = bytes(pending)
                    await self._send_media(frame)
                    await asyncio.sleep(len(frame) / (SAMPLE_RATE * 2))
        except asyncio.CancelledError:
            cancelled = True
            raise
        except Exception:
            if not self.stopping:
                log.exception("Sarvam TTS failed for Exotel call %s", self.call_sid or "unknown")
        finally:
            if close_after and not cancelled and not self.stopping:
                self.stopping = True
                await self._close_socket(1000, "Call finished")

    async def _send_media(self, pcm: bytes) -> None:
        self.output_sequence += 1
        self.output_chunk += 1
        event = {
            "event": "media",
            "sequence_number": self.output_sequence,
            "stream_sid": self.stream_sid,
            "media": {
                "chunk": self.output_chunk,
                "timestamp": str(int((time.monotonic() - self.started_at) * 1000)),
                "payload": base64.b64encode(pcm).decode("ascii"),
            },
        }
        await self._send_exotel(event)

    async def _send_exotel(self, message: dict[str, Any]) -> None:
        async with self.send_lock:
            if self.socket.application_state == WebSocketState.CONNECTED:
                await self.socket.send_json(message)

    async def _close_socket(self, code: int, reason: str) -> None:
        try:
            if self.socket.application_state == WebSocketState.CONNECTED:
                await self.socket.close(code=code, reason=reason[:120])
        except Exception:
            pass
