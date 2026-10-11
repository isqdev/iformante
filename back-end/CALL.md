# Chamada

The UI is available at `/call`, including a sidebar entry and a hold-to-talk button.
Opening the page automatically prepares the microphone and requests permission
when needed, without recording or sending audio. Web Audio is prepared while
suspended; the first keyboard/pointer recording gesture resumes it. Permission
failures offer a manual retry. Ending the call leaves it off until explicitly
resumed or the page is reopened.
Hold space or the button to record; release to send. Recording is available only
when ready; the talk button is disabled during transcription, generation and
playback, and space presses do not interrupt the response. Ending the call or
leaving the page cancels its active turn and releases the microphone. Pointer
cancellation and window blur discard incomplete recordings. The portrait and
controls are centered; question and answer cards are omitted. Source buttons
remain available below the controls. PDFs open in the fullscreen /docs viewer;
web sources open their URL in a separate tab, matching /docs.

## Setup

Run from `back-end`:

```powershell
uv sync --frozen
uv run python scripts/install_call_voice.py
uv run alembic upgrade head
```

Set `GROQ_API_KEY` and the existing `OPENAI_API_KEY` in the server environment.
The default `PIPER_MODEL_PATH` is `voices/pt_BR-faber-medium.onnx`. Its adjacent
`.onnx.json` is also required. The Docker build downloads and verifies both files.
The installed voice is Brazilian Portuguese, medium quality, 22,050 Hz. The
download is pinned to revision `2f8dbe0`, with checksums verified before replacing
local files. Attribution and license information are in `voices/NOTICE.md`.

## Response and audio policy

The existing chat route defaults to `ResponseMode.TEXT`; the call route explicitly
sets `ResponseMode.SPEECH`. Clients and model outputs cannot select this mode.
The same router and retrieval are reused, with a separate speech presentation
prompt. Direct router responses also pass through speech preparation.

Before Piper, numbers, dates, currencies and supported abbreviations are prepared
for reading. The server enforces 40 words on the resulting string, allowing one
shortening attempt and a safe short fallback. Source labels are separate metadata.
There is no 20-second playback timer or automatic audio cutoff. A local sample of
40 words took 15.06 seconds; duration varies with pauses and pronunciation.

The voice worker loads the model once and keeps it between turns. It uses phoneme
alignment to animate the mouth, with an amplitude fallback when alignment is
unavailable. Cancelling a synthesis terminates the worker; the next turn starts a
fresh worker. Audio is returned progressively after response validation. The
browser uses an AudioWorklet, PCM queue and resampling; its consumed audio clock
drives the mouth. Transmission completion and playback completion are separate.

Uploads are limited to 10 MB and verified by audio file signature. Groq uses
`whisper-large-v3-turbo`, language `pt`, and rejects empty/no-speech transcription.
Raw recordings and call conversations are not persisted, including for signed-in
users. Context and playback status exist only in the current page session. The
server always invokes the temporary chat path and ignores submitted conversation
identifiers. Ending/leaving the page cancels playback; incomplete responses are
marked locally so subsequent turns do not assume they were fully heard.

## Endpoints

- `GET /call/status`: whether transcription, voice and response configuration exist.
- `POST /call/stream`: multipart `audio`, random `turn_id` and JSON `messages`.
  The response is SSE; calls never create sidebar conversations.
- `POST /call/cancel`: JSON `turn_id`. Active turns are owner-bound; a random UUID
  is a capability for anonymous turns. Do not expose it in links or logs.
- `POST /call/playback`: legacy compatibility endpoint; always returns
  `saved: false` without database writes. Current clients track playback locally.

SSE events: `state`, `transcript`, `rag`, `answer`, `audio_format`,
`alignment`, `audio`, `audio_done`, `done`, `error`. Audio is mono PCM16 in base64,
with ordered frame sequences; phoneme timings are relative to the audio stream.
The Next proxy preserves response streaming. Keys remain only on the back-end.

The first version supports one synthesis worker per API process and at most eight
active turns per process. Run one API worker for explicit cancellation routing.
Multiple API replicas require a shared cancellation registry/voice queue or sticky
routing; the current in-memory registry must not be advertised as distributed.

## Verification

Local validation on 2026-10-11: 15 call back-end tests, 2 current chat streaming
regression tests and 14 Chromium browser scenarios passed (with targeted reruns), including automatic
page entry, microphone denial/retry, temporary signed-in context, fullscreen
PDF sources and gesture-gated audio playback. TypeScript checking
and ESLint passed. Desktop and mobile screenshots were inspected. Piper's local
worker test confirmed alignment, model reuse, cancellation and restart.

```powershell
uv run python -m unittest discover -s tests -p test_call.py -v
$env:PYTHONPATH = '.'
uv run python scripts/verify_call_voice.py
```

From `front-end`, with the UI running:

```powershell
$env:TEST_BASE_URL = 'http://localhost:3000'
npx playwright test tests/browser/call.spec.ts --workers=1
npx tsc --noEmit
npm run lint -- --quiet
```

The local smoke script verifies synthesis, alignment, worker reuse and actual
termination/restart. Its optional `--api-url http://127.0.0.1:8000` sends a synthetic
academic question through the complete external Groq/OpenAI flow and must only be
run with authorization for that external test. Local regression tests use
mocked external services; they do not validate real Groq/OpenAI credentials.

The existing broad back-end suite has unrelated stale tests: old `top_k` router
arguments, old document interfaces, Qdrant imports, old model table expectations
and existing architecture constraints. Targeted call and current streaming tests
are the relevant regression checks for this change.
