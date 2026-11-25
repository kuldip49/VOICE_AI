# Inbound phone calls

The backend can answer inbound calls through Twilio Programmable Voice. Twilio handles the phone number, speech recognition, and synthesized speech. The app connects each call to the same sales agent used by the web voice desk, so Gemini, RAG, lead extraction, appointment booking, and call summaries are shared. Caller turns and assistant replies are stored in the normal conversation transcript; the provider call SID links that transcript to the phone session.

The caller presses **1 for English** or **2 for Hindi**. Twilio then uses the matching India speech locale (`en-IN` or `hi-IN`). Press **9** during the call to switch between English and Hindi. Say “hang up,” “end the call,” “bye,” or the Hindi equivalent to close the call and create its summary. If the caller hangs up without saying goodbye, configure Twilio's number status callback below so the session can be finalized.

## Configure it

1. Install the project requirements again after pulling this change so the Twilio Python SDK is installed:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
   ```

2. Run the backend on a host that Twilio can reach over public HTTPS. For local development, use a secure HTTPS tunnel; `localhost` and a LAN IP are not reachable by Twilio.

3. Put these values in `backend/.env` (never commit this file):

   ```dotenv
   TWILIO_PUBLIC_BASE_URL=https://your-public-host.example
   TWILIO_AUTH_TOKEN=your_twilio_auth_token
   LLM_PROVIDER=auto
   GEMINI_API_KEY=your_existing_gemini_key
   ```

   Set `TWILIO_PUBLIC_BASE_URL` to the HTTPS **origin** only, with no endpoint path or trailing slash. Keep Gemini configured on the backend; the phone webhook runs the existing provider selection and records `generated_by` on each reply. Check the non-secret readiness view at `/api/telephony/twilio/status`; `configured` must be `true` and `llm` should show the active model label.

4. In the Twilio Console, buy or select a voice-capable phone number. Set its **A call comes in** webhook to:

   ```text
   https://your-public-host.example/api/telephony/twilio/voice
   ```

   Choose **HTTP POST**. If the phone number configuration exposes a status callback, set it to:

   ```text
   https://your-public-host.example/api/telephony/twilio/status
   ```

   Also choose **HTTP POST**. The status callback is optional for answering calls, but it lets the app save a summary if someone disconnects without saying goodbye.

5. Call the Twilio number from a permitted phone. The caller selects a language, asks a business question, and receives spoken answers from the configured agent. Test RAG answers, caller details, a counselling booking, and ending a call before public use.

Twilio signs every webhook. The backend validates `X-Twilio-Signature` using Twilio's official Python SDK, the configured auth token, and the exact public webhook URL; it rejects requests if validation settings or the SDK are missing. Phone-path model calls use short timeouts because Twilio limits call-related webhook responses to 15 seconds; when Gemini times out, the sales agent falls back to a grounded response. Serve only over HTTPS. The Twilio auth token and Gemini API key stay in `backend/.env` and must not be entered in this repository or the browser.

## What has to exist for live calls

The repository contains the inbound call integration, but a code change alone cannot make a reachable phone number. Live calls require a Twilio account with a voice-capable number, a public HTTPS deployment/tunnel, the account auth token set locally, and the number pointed to the webhook above. Twilio phone usage and speech services can incur provider charges; Gemini usage also follows the configured Google account limits/pricing. Availability and supported numbers depend on the Twilio account and country.

## Call flow

```text
Caller -> Twilio number -> signed /voice webhook -> English/Hindi keypad choice
       -> signed speech/DTMF Gather -> /turn -> SalesAgent + Gemini + RAG
       -> Twilio speaks answer -> CRM / booking / summary records
```

Twilio's `<Gather>` sends recognized speech or keypad input to the action URL and continues with the returned TwiML. The selected conversational speech model supports both `en-IN` and `hi-IN`. The backend stores the caller's phone number on the CRM customer record and saves the text transcript; this application does not record caller audio. See Twilio's official [Gather reference](https://www.twilio.com/docs/voice/twiml/gather), [webhook signature guidance](https://www.twilio.com/docs/usage/webhooks/webhooks-security), [voice webhook timeout details](https://www.twilio.com/docs/usage/webhooks/webhooks-connection-overrides), and [IncomingPhoneNumber resource](https://www.twilio.com/docs/phone-numbers/api/incomingphonenumber-resource).
