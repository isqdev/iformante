import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import HTTPException
from starlette.requests import Request

from app.routes.document import get_document_content
from app.services.remote_document import remote_document_response


def request(headers=()):
    return Request({"type": "http", "method": "GET", "path": "/documents/doc/content", "headers": headers})


class PdfStream(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b"%PDF-test"


class RemoteDocumentTests(unittest.IsolatedAsyncioTestCase):
    async def test_remote_stream_preserves_ranges_and_only_session_cookie(self):
        captured = []

        async def handle(incoming):
            captured.append(incoming)
            return httpx.Response(206, headers={"content-type": "application/pdf", "content-range": "bytes 0-8/9"}, stream=PdfStream())

        client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
        with patch("app.services.remote_document.httpx.AsyncClient", return_value=client):
            response = await remote_document_response("https://prod.example/api", "doc", request([
                (b"range", b"bytes=0-8"), (b"cookie", b"other=secret; iformante_session=valid"),
            ]))
            content = b"".join([chunk async for chunk in response.body_iterator])
        self.assertEqual(content, b"%PDF-test")
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.headers["content-range"], "bytes 0-8/9")
        self.assertEqual(str(captured[0].url), "https://prod.example/api/documents/doc/content")
        self.assertEqual(captured[0].headers["cookie"], "iformante_session=valid")
        self.assertEqual(captured[0].headers["range"], "bytes=0-8")
        self.assertTrue(client.is_closed)

    async def test_upstream_not_found_and_client_cleanup(self):
        client = httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(404)))
        with patch("app.services.remote_document.httpx.AsyncClient", return_value=client):
            with self.assertRaises(HTTPException) as error:
                await remote_document_response("https://prod.example", "doc", request())
        self.assertEqual(error.exception.status_code, 404)
        self.assertTrue(client.is_closed)

    async def test_does_not_follow_redirect_or_forward_to_insecure_origin(self):
        with self.assertRaises(HTTPException) as error:
            await remote_document_response("http://prod.example", "doc", request())
        self.assertEqual(error.exception.status_code, 503)
        with self.assertRaises(HTTPException) as error:
            await remote_document_response("https://prod.example", "doc", request([(b"x-document-remote-fetch", b"1")]))
        self.assertEqual(error.exception.status_code, 404)

    async def test_private_document_denied_before_remote_fetch(self):
        document = SimpleNamespace(id="doc", stored_path="/app/downloads/doc/original.pdf", ingestion_status="PROCESSING")
        with patch("app.routes.document.DocumentRepository") as repository, patch("app.routes.document.remote_document_response", new_callable=AsyncMock) as remote:
            repository.return_value.get_by_id = AsyncMock(return_value=document)
            with self.assertRaises(HTTPException) as error:
                await get_document_content("doc", request(), None, None)
            self.assertEqual(error.exception.status_code, 404)
            remote.assert_not_awaited()

    async def test_copied_original_uses_local_root_despite_production_path(self):
        document = SimpleNamespace(id="doc", stored_path="/app/downloads/doc/original.pdf", ingestion_status="INDEXED", file_name="example.pdf")
        with TemporaryDirectory() as directory:
            target = Path(directory) / "doc" / "original.pdf"
            target.parent.mkdir()
            target.write_bytes(b"%PDF-test")
            with patch("app.routes.document.settings", SimpleNamespace(document_storage_dir=directory, document_remote_base_url="https://prod.example")), patch("app.routes.document.DocumentRepository") as repository, patch("app.routes.document.remote_document_response", new_callable=AsyncMock) as remote:
                repository.return_value.get_by_id = AsyncMock(return_value=document)
                response = await get_document_content("doc", request(), None, None)
                self.assertEqual(response.path, target.resolve())
                remote.assert_not_awaited()
