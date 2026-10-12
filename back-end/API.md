# API Notes

## Endpoints

- GET /
- POST /chat/stream
- GET /system/prompts
- PATCH /system/prompts/{param}
- PATCH /system/users/role

## System administration

The web page is `/system`, labeled **Sistema** in the sidebar. All `/system/*`
API routes require a verified SUPER session. Changes also require the existing
CSRF token and allowed origin. ADMIN and SUPER both administer documents; only
SUPER manages prompts and ADMIN ↔ SUPER transitions. Registration continues to
assign COMMON to `@estudantes.ifpr.edu.br` and ADMIN to `@ifpr.edu.br`.

`GET /system/prompts` returns `{id, param, value}` for six active parameters:
`prompt_router`, `prompt_reranker`, `prompt_replier`, `prompt_speech_style`,
`prompt_replier_voice`, and `prompt_voice_rewrite`. IDs follow the nine-character
project convention, and `system_params.param` is unique.

Update a prompt with `{value, expected_value}`. The value retains its exact text
and whitespace; an empty prompt is rejected. A stale expected value returns 409.
The voice style requires `{{max_words}}`; the voice response and adaptation
templates require `{{speech_style}}`. These fields use literal substitution,
without evaluating code or interpreting ordinary JSON braces. Each interaction
loads an immutable snapshot from the database; changes apply on the next turn.

Update a role with `{email, role: "SUPER" | "ADMIN"}`. Only verified ADMIN/SUPER
accounts are eligible. COMMON, self changes, and removal of the last SUPER are
rejected. Mutations are serialized using a PostgreSQL transaction advisory lock
and recheck the acting user's permission under that lock. Responses omit emails.

Apply migration `202610120001` before starting the updated API. It seeds the six
prompts and promotes only the verified `isaque123` account matching the confirmed
email; it preserves passwords and other accounts. Reapplying migrations does not
reset edited prompts or later role changes.

To seed missing records directly from the current code constants after migrating,
run `python -m scripts.seed_system_params`. This command inserts only missing
parameters, preserves saved edits, and reports the presence of all six prompts.
Restart an API instance that was launched without reload so it registers the
new `/system/*` routes.

Voice generation/adaptation has no application retry. Exceeding the suggested
word count does not trigger another generation, fallback, truncation, or TTS
rejection. Source extraction and speech normalization still apply.

## POST /chat/stream

Streams the assistant response as plain text.

Request body:

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Ola"
    }
  ]
}
```

Response:

```txt
Texto gerado pelo modelo em streaming.
```
