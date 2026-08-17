# API Notes

## Endpoints

- GET /
- POST /chat/stream

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
