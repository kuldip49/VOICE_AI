"""Connect the configured Twilio phone number to this app's inbound-call webhooks.

Run from the backend directory: python -m app.telephony_setup
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from twilio.rest import Client

from .config import get_settings

VOICE_PATH = "/api/telephony/twilio/voice"
STATUS_PATH = "/api/telephony/twilio/status"
E164 = re.compile(r"^\+[1-9][0-9]{6,14}$")


def main() -> None:
    cfg = get_settings()
    missing = [name for name, value in (
        ("TWILIO_ACCOUNT_SID", cfg.twilio_account_sid),
        ("TWILIO_AUTH_TOKEN", cfg.twilio_auth_token),
        ("TWILIO_PHONE_NUMBER", cfg.twilio_phone_number),
        ("TWILIO_PUBLIC_BASE_URL", cfg.twilio_public_base_url),
    ) if not value]
    if missing:
        raise SystemExit("Missing backend/.env values: " + ", ".join(missing))

    parsed = urlparse(cfg.twilio_public_base_url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise SystemExit("TWILIO_PUBLIC_BASE_URL must be an HTTPS origin only, e.g. https://voice.example.com")
    if not E164.fullmatch(cfg.twilio_phone_number.strip()):
        raise SystemExit("TWILIO_PHONE_NUMBER must be in E.164 format, e.g. +14155550123")

    base = cfg.twilio_public_base_url.rstrip("/")
    voice_url = f"{base}{VOICE_PATH}"
    status_url = f"{base}{STATUS_PATH}"
    client = Client(cfg.twilio_account_sid, cfg.twilio_auth_token)
    matches = client.incoming_phone_numbers.list(phone_number=cfg.twilio_phone_number.strip(), limit=20)
    number = next((item for item in matches if item.phone_number == cfg.twilio_phone_number.strip()), None)
    if number is None:
        raise SystemExit("That phone number was not found in the configured Twilio account.")
    if number.voice_application_sid or number.trunk_sid:
        raise SystemExit("This number is attached to a Twilio Voice Application or SIP trunk. "
                         "Detach it in Twilio before switching its incoming-call handler.")

    updated = number.update(
        voice_url=voice_url,
        voice_method="POST",
        status_callback=status_url,
        status_callback_method="POST",
    )
    if updated.voice_url != voice_url:
        raise SystemExit("Twilio did not confirm the expected incoming-call webhook URL.")

    print(f"Connected {updated.phone_number} to the Kiln & Signal inbound voice webhook.")
    print(f"Voice webhook: {updated.voice_url} (POST)")
    print(f"Status callback: {updated.status_callback} (POST)")


if __name__ == "__main__":
    main()
