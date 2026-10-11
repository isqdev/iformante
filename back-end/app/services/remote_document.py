"""Read production PDFs through its protected content endpoint."""
from urllib.parse import quote, urlsplit

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse

from app.security.auth import SESSION_COOKIE


async def remote_document_response(base_url: str, document_id: str, request: Request) -> StreamingResponse:
    parsed = urlsplit(base_url)
    if (parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}
    )) or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise HTTPException(503, "Configure DOCUMENT_REMOTE_BASE_URL com uma URL HTTPS da produção.")
    # Prevent a misconfigured production fallback from forwarding back to itself.
    if request.headers.get("x-document-remote-fetch"):
        raise HTTPException(404, "Arquivo PDF nao encontrado.")

    headers = {"accept": "application/pdf", "accept-encoding": "identity", "x-document-remote-fetch": "1"}
    for name in ("range", "if-range"):
        if value := request.headers.get(name):
            headers[name] = value
    # Only forward the application session to the explicitly configured server.
    if token := request.cookies.get(SESSION_COOKIE):
        headers["cookie"] = f"{SESSION_COOKIE}={token}"
    client = httpx.AsyncClient(timeout=httpx.Timeout(60, connect=10), follow_redirects=False)
    try:
        upstream = await client.send(client.build_request(
            "GET", f"{base_url.rstrip('/')}/documents/{quote(document_id, safe='')}/content", headers=headers,
        ), stream=True)
    except httpx.HTTPError as error:
        await client.aclose()
        raise HTTPException(502, "Não foi possível buscar o PDF em produção.") from error

    if upstream.status_code not in {200, 206} or "application/pdf" not in upstream.headers.get("content-type", "").lower():
        upstream_status = upstream.status_code
        await upstream.aclose()
        await client.aclose()
        code = upstream_status if upstream_status in {401, 403, 404, 416} else 502
        raise HTTPException(code, "O PDF não está disponível no servidor de produção.")

    async def chunks():
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    outgoing = {name: upstream.headers[name] for name in (
        "content-length", "content-range", "accept-ranges", "content-disposition", "content-encoding",
    ) if name in upstream.headers}
    outgoing["cache-control"] = "private, no-store"
    return StreamingResponse(chunks(), status_code=upstream.status_code, media_type="application/pdf", headers=outgoing)
