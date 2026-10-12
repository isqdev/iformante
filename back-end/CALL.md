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
The defaults are `POCKET_TTS_CONFIG_PATH=voices/pocket-tts/portuguese.yaml` and
`POCKET_TTS_VOICE_PATH=voices/pocket-tts/george.safetensors`. The runtime is
Kyutai Pocket TTS 3.3.0 with its Portuguese model and George's matching voice
state. Portuguese text and Brazilian speech normalization are preserved.
George's original reference recording is English, so an accent can remain.
The installer downloads the public model, tokenizer and Portuguese George state
from `kyutai/pocket-tts-without-voice-cloning`, revision
`575d14372df89a4534bcb989870a34e77544b09f`, verifying SHA-256 before replacing
files. It writes the Portuguese architecture config with local paths, so runtime
synthesis needs no network downloads, Hugging Face token or gated model access.
Audio is mono PCM16 at 24,000 Hz. PyTorch uses its CPU distribution.
The Docker build runs the same installer. Relative configuration and voice paths
resolve from `back-end`. Attribution and licenses are in `voices/NOTICE.md`.

## Response and audio policy

The existing chat route defaults to `ResponseMode.TEXT`; the call route explicitly
sets `ResponseMode.SPEECH`. Clients and model outputs cannot select this mode.
The same router and retrieval are reused, with a separate speech presentation
prompt. Direct router responses also pass through speech preparation.

Before synthesis, numbers, dates, currencies and supported abbreviations are prepared
for reading. The prompt suggests 60 words, but the server does not reject,
rewrite, truncate or replace an answer that exceeds that suggestion. Each speech
generation/adaptation calls the model once, without application retries or a
word-budget fallback. Explanations normally aim for
40-55 spoken words when needed; greetings and simple answers stay brief.
Responses start with the answer, without repeating or paraphrasing the question.
Complete, connected sentences replace headings, lists, labels and parenthetical
asides. Written structures and question-echo introductions do not trigger another
generation. Direct router responses receive the same oral style;
the exact scope refusal remains unchanged. Dates use a natural first-day form,
singular times agree correctly, and paragraph boundaries preserve sentence pauses.
Source labels are separate metadata.
There is no 20-second playback timer or automatic audio cutoff. Duration varies
with pauses, voice and pronunciation.

The voice worker keeps the model and George's voice state loaded between turns.
Each turn uses a copy of that state to avoid carrying generated speech into the
next response. Pocket TTS does not supply phoneme timings, so the mouth follows
the amplitude of the audio actually being played. Cancelling a synthesis
terminates the worker; the next turn starts a fresh worker. Audio is returned
progressively by `generate_audio_stream` after response validation. The
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
`audio`, `audio_done`, `done`, `error`. Audio is mono PCM16 in base64,
with ordered frame sequences. The browser also accepts optional `alignment`
events for compatibility; the current engine does not emit them.
The Next proxy preserves response streaming. Keys remain only on the back-end.

The first version supports one synthesis worker per API process and at most eight
active turns per process. Run one API worker for explicit cancellation routing.
Multiple API replicas require a shared cancellation registry/voice queue or sticky
routing; the current in-memory registry must not be advertised as distributed.

## Verification

Voice presentation update on 2026-10-12: 30 call tests and the two current
answer/router streaming regressions passed. The three HTTP chat-route tests
also passed; five older tests in the same file still use outdated interfaces,
as noted below. Real local synthesis with George completed a 60-word response
in 24.4 seconds, with ordered PCM frames and no playback cutoff. The 40-word
sample took 16.48 seconds in the same run. Word count includes expanded numbers
and dates. Comparing actual model-generated phrasing against the old policy
requires explicit approval to send the selected project excerpts to OpenAI.

Validation on 2026-10-11: 18 call back-end tests, two current chat regressions
and three Chromium playback/control scenarios passed. Browser tests use 24 kHz
audio without phoneme timings. Real offline synthesis with George confirmed
PCM format, ordered frames, sample totals, worker reuse, termination and restart.
The 40-word sample took 16.56 seconds; the normalized dates/numbers sample took
11.52 seconds. External Groq/OpenAI calls were mocked in the regression tests.

The commands below verify the current engine. Local regression tests mock
external Groq/OpenAI calls. The local voice smoke test uses the installed
Portuguese model with George, including model reuse, cancellation and restart.

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

The local smoke script verifies Brazilian synthesis, PCM format, ordered frames,
sample totals, worker reuse and actual
termination/restart. Its optional `--api-url http://127.0.0.1:8000` sends a synthetic
academic question through the complete external Groq/OpenAI flow and must only be
run with authorization for that external test. Local regression tests use
mocked external services; they do not validate real Groq/OpenAI credentials.

The existing broad back-end suite has unrelated stale tests: old `top_k` router
arguments, old document interfaces, Qdrant imports, old model table expectations
and existing architecture constraints. Targeted call and current streaming tests
are the relevant regression checks for this change.
