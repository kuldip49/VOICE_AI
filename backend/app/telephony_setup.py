"""Print the Exotel AgentStream setup values for this inbound phone integration.

Run from the backend directory: python -m app.telephony_setup
Exotel number-to-flow assignment is done in the Exotel console.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from .config import get_settings

E164 = re.compile(r"^\+[1-9][0-9]{6,14}$")
STREAM_PATH = "/api/telephony/exotel/stream"


def main() -> None:
    cfg = get_settings()
    required = {
        "EXOTEL_ACCOUNT_SID": cfg.exotel_account_sid,
        "EXOTEL_API_KEY": cfg.exotel_api_key,
        "EXOTEL_API_TOKEN": cfg.exotel_api_token,
        "EXOTEL_PHONE_NUMBER": cfg.exotel_phone_number,
        "EXOTEL_PUBLIC_WSS_URL": cfg.exotel_public_wss_url,
        "SARVAM_API_KEY": cfg.sarvam_api_key,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise SystemExit("Missing backend/.env values: " + ", ".join(missing))

    parsed = urlparse(cfg.exotel_public_wss_url)
    if (parsed.scheme != "wss" or not parsed.netloc or parsed.path != STREAM_PATH
            or parsed.username or parsed.password or parsed.query != "sample-rate=16000" or parsed.fragment):
        raise SystemExit(
            "EXOTEL_PUBLIC_WSS_URL must end in " + STREAM_PATH + "?sample-rate=16000"
        )
    if not E164.fullmatch(cfg.exotel_phone_number.strip()):
        raise SystemExit("EXOTEL_PHONE_NUMBER must be in E.164 format, e.g. +919876543210")
    if cfg.exotel_sample_rate != 16000:
        raise SystemExit("This bridge currently requires EXOTEL_SAMPLE_RATE=16000")

    print("Exotel inbound voice setup values are present.")
    print(f"ExoPhone: {cfg.exotel_phone_number.strip()}")
    print("Voicebot applet URL template (replace placeholders; do not share the credential-bearing URL):")
    print(f"wss://<EXOTEL_API_KEY>:<EXOTEL_API_TOKEN>@{parsed.netloc}{parsed.path}?sample-rate=16000")
    print("Exotel sends those URL credentials as an Authorization: Basic header to the WSS endpoint.")
    print(f"Audio format: mono linear16 PCM, {cfg.exotel_sample_rate} Hz.")
    print("In the Exotel console, assign the ExoPhone to an App Bazaar flow, add a Voicebot applet,")
    print("set its WSS URL/authentication/audio format, and add an End Call applet after the bot.")
    print("The public server must accept WSS on this URL. AgentStream availability and charges depend on your Exotel account plan.")


if __name__ == "__main__":
    main()
