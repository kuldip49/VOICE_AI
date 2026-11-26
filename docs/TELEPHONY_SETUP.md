# Inbound phone calls with Exotel AgentStream

The inbound call bridge uses Exotel for the Indian phone number and bidirectional call audio. The existing SalesPilot sales agent continues to handle the caller's conversation, CRM updates, lead scoring, appointment workflow and call summary. Sarvam handles real-time speech recognition and spoken replies. This is a separately configured phone channel from browser voice, which uses the browser Web Speech API.

## Call path

1. A caller dials the ExoPhone assigned to the Exotel account.
2. An Exotel App Bazaar flow runs a Voicebot applet and opens a secure WebSocket to `/api/telephony/exotel/stream`.
3. Exotel sends mono, 16 kHz, linear16 PCM audio in JSON `media` events. The backend forwards audio to Sarvam realtime STT.
4. Final transcripts enter the existing `process_message` flow, which invokes the SalesAgent, retrieval, tools and CRM.
5. Sarvam TTS streams the agent's English or Hindi reply back as PCM audio frames for Exotel to play to the caller.
6. Exotel's `stop` event or a goodbye finalizes the conversation and CRM summary. Pressing 9 switches between English and Hindi.

Exotel's inbound setup is a Voicebot applet assigned to a number through an App Bazaar flow. The applet needs an internet-reachable `wss://` URL and Basic Auth credentials. AgentStream availability may require a separate Exotel activation or plan; confirm it with Exotel before relying on it. Sarvam API use also requires an account/key and is subject to Sarvam's current pricing and limits.

## 1. Prepare the server

Install the backend requirements after switching providers:

```powershell
cd backend
pip install -r requirements.txt
```

Set the following in the ignored `backend/.env` file. Keep all credentials server-side; do not put them in the browser or commit the `.env` file.

```dotenv
EXOTEL_ACCOUNT_SID=your_exotel_account_sid
EXOTEL_API_KEY=your_exotel_api_key
EXOTEL_API_TOKEN=your_exotel_api_token
EXOTEL_PHONE_NUMBER=+91xxxxxxxxxx
EXOTEL_PUBLIC_WSS_URL=wss://voice.example.com/api/telephony/exotel/stream
EXOTEL_SAMPLE_RATE=16000
SARVAM_API_KEY=your_sarvam_api_key
SARVAM_STT_MODEL=saaras:v4
SARVAM_TTS_MODEL=bulbul:v3
SARVAM_VOICE_EN=ishita
SARVAM_VOICE_HI=priya
```

Keep the existing LLM configuration if you want Gemini, Grok or Ollama to write the agent's responses. Without a configured hosted/local model, the existing demo response mode remains available. `EXOTEL_PUBLIC_WSS_URL` must be a public secure WebSocket URL ending in `/api/telephony/exotel/stream?sample-rate=16000`; keep credentials out of `.env`'s URL and use the fixed 16 kHz audio setting. For local development, a plain `localhost` URL cannot receive Exotel calls; use a WSS-capable public tunnel or deployed host.

The generated WSS route requires HTTP Basic Auth. Exotel's Voicebot applet takes the API key and token in the WSS URL and sends them in the `Authorization: Basic` header during the handshake. In the Exotel URL field, enter `wss://<API_KEY>:<API_TOKEN>@voice.example.com/api/telephony/exotel/stream?sample-rate=16000`, using your own server host and credentials; this credential-bearing URL belongs only in the Exotel console. Exotel defaults the stream to 8 kHz if the `sample-rate=16000` query is omitted, and this bridge will reject that mismatch. TLS/WSS is required in deployment. The Docker Nginx configuration forwards WebSocket upgrade headers and allows long-lived connections; Vite's development proxy also supports WebSockets.

From the `backend/` directory, run the setup helper to validate environment values and print the console configuration:

```powershell
python -m app.telephony_setup
```

The helper does not call Exotel or attach the number for you; Exotel's number-to-flow assignment is performed in its console. It prints a URL template with credential placeholders, not your secret values.

## 2. Configure the Exotel number and flow

In the Exotel console:

1. Confirm the account has an inbound ExoPhone and that AgentStream / Voicebot applets are enabled for it.
2. Create an App Bazaar flow and add a Voicebot applet.
3. Use the URL template printed by the helper, your public host/path from `EXOTEL_PUBLIC_WSS_URL`, and the credentials from `backend/.env`.
4. In the WSS URL, place `EXOTEL_API_KEY:EXOTEL_API_TOKEN@` between `wss://` and your hostname so Exotel can send the credentials as a Basic Auth header.
5. Keep `?sample-rate=16000` on the URL and select mono linear16 PCM at 16,000 Hz for both directions.
6. Assign the inbound ExoPhone to that flow. A closed bidirectional stream advances to the next applet; add an End Call applet after Voicebot if the flow should end the call.

The API checks the Basic Auth header before accepting the WebSocket. The Exotel start event supplies the call ID and caller number used to create or match the CRM customer and conversation.

## 3. Check configuration and call

Restart the backend after editing `.env`. The admin Settings page reports whether the Exotel credentials, ExoPhone, WSS URL and Sarvam key are present; it never returns secret values. `GET /api/telephony/exotel/status` gives the same non-secret readiness status.

Once the public server is reachable and the number is assigned to the flow, call the ExoPhone from an allowed caller. Speak English or Hindi; press 9 to switch languages. Say goodbye to have the agent finish the conversation summary, or hang up normally to finalize it after Exotel sends `stop`.

Exotel trial accounts may restrict incoming calls from unverified caller numbers and prompt the caller for an account PIN. Trial accounts and usage credits are for restricted evaluation, not an assumption of free production calling. Check current Exotel account/plan terms and AgentStream charges before opening the number to customers.

## Current implementation boundary

The repository contains the Exotel WebSocket handler, Sarvam streaming bridge, CRM/agent callbacks, readiness display, reverse-proxy support and this setup guide. A live number has **not** been connected from this workspace. Live calls still need an Exotel account with Voicebot/AgentStream enabled, an assigned ExoPhone and flow, public WSS hosting, valid Exotel credentials and a Sarvam API key. No credentials are included in this repository.

For protocol details see Exotel's [Voicebot applet documentation](https://docs.exotel.com/exotel-agentstream/voicebot-applet) and [AgentStream setup guidance](https://docs.exotel.com/exotel-agentstream/agentstream-what-to-use-when), Sarvam's [real-time STT guide](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/realtime-streaming) and [streaming TTS guide](https://docs.sarvam.ai/api/api-guides-tutorials/text-to-speech/streaming-api/web-socket), and Exotel's [trial account limitations](https://docs.exotel.com/business-phone-system/create-a-trial-account) and [pricing](https://exotel.com/pricing/business-phone-system/).
