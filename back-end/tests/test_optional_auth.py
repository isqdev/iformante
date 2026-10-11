import json
import os
import re
import secrets
import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool
from app.app import app
from app.config import settings
from app.db import get_database_session
from app.models import User, Conversation, Document
from app.models.auth import EmailDelivery
from app.security.auth import code_hash, mask_email, now
from app.services.auth_mail import cipher
from app.use_cases.chat.receive_message import ReceiveMessageUseCase
from app.rag.generation import AnswerResult
from app.rag.retrieval import ParentRetrievalResult, RetrievedParent


class GuestPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_guest_has_same_response_without_database_writes(self):
        repository = SimpleNamespace(create=AsyncMock(), get_by_id=AsyncMock(), list_model_history=AsyncMock())
        unit = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
        router = SimpleNamespace(is_configured=True, execute=AsyncMock(return_value=SimpleNamespace(direct_response="Olá!")))
        use_case = ReceiveMessageUseCase(repository, repository, unit, router, SimpleNamespace(is_configured=True), None, repository, repository)
        events = [e async for e in use_case.stream(None, None, "Oi")]
        self.assertEqual([e.event for e in events], ["rag", "delta", "done"])
        repository.create.assert_not_awaited()
        repository.get_by_id.assert_not_awaited()
        unit.commit.assert_not_awaited()

    async def test_guest_rag_does_not_persist_sources_or_audit(self):
        repository = SimpleNamespace(create=AsyncMock(), create_many=AsyncMock())
        unit = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
        router = SimpleNamespace(is_configured=True, execute=AsyncMock(return_value=SimpleNamespace(direct_response=None, query="query", user_question="Pergunta")))
        parent = RetrievedParent("chunk1234", "doc123456", "Trecho", [{"page": 1}], None, "Documento.pdf")
        retriever = SimpleNamespace(retrieve=AsyncMock(return_value=ParentRetrievalResult([parent], [], {})))
        async def answer(*args):
            yield AnswerResult(content="Resposta", used_parent_ids=[parent.id])
        generator = SimpleNamespace(is_configured=True, stream=answer)
        use_case = ReceiveMessageUseCase(repository, repository, unit, router, generator, retriever, repository, repository)
        events = [e async for e in use_case.stream(None, None, "Pergunta")]
        self.assertEqual(events[-1].payload["sources"][0]["citations"][0]["chunk_id"], parent.id)
        repository.create.assert_not_awaited()
        repository.create_many.assert_not_awaited()
        unit.commit.assert_not_awaited()


@unittest.skipUnless(settings.database_url, "Requires configured PostgreSQL")
class AuthenticationIntegrationTests(unittest.IsolatedAsyncioTestCase):
    """All writes use savepoints inside a transaction rolled back after each test. No mail worker runs."""
    async def asyncSetUp(self):
        self.environment = patch.dict(os.environ, {"AUTH_SECRET": "test-secret-" * 5, "SMTP_HOST": "invalid.test", "SMTP_FROM": "test@invalid.test"})
        self.environment.start()
        self.engine = create_async_engine(settings.database_url, poolclass=NullPool)
        self.connection = await self.engine.connect()
        self.transaction = await self.connection.begin()
        self.session = AsyncSession(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        async def database():
            yield self.session
        app.dependency_overrides[get_database_session] = database
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")

    async def asyncTearDown(self):
        await self.client.aclose()
        app.dependency_overrides.clear()
        await self.session.close()
        await self.transaction.rollback()
        await self.connection.close()
        await self.engine.dispose()
        self.environment.stop()

    async def signup(self, domain="estudantes.ifpr.edu.br"):
        email = "test" + secrets.token_hex(8) + "@" + domain
        response = await self.client.post("/auth/register", json={"name": "Teste Sobrenome", "email": email, "password": "abcdefgh", "confirm_password": "abcdefgh"})
        self.assertEqual(response.status_code, 202, response.text)
        registration = response.json()["registration_id"]
        delivery = (await self.session.execute(select(EmailDelivery).where(EmailDelivery.challenge_id == registration))).scalar_one()
        code = re.search(r"código é (\d{3})", json.loads(cipher().decrypt(delivery.payload.encode()))["body"])[1]
        return email, registration, code

    async def test_registration_confirmation_login_and_permissions(self):
        email, registration, code = await self.signup()
        for _ in range(7):
            wrong = "001" if code != "001" else "002"
            response = await self.client.post("/auth/register/confirm", json={"registration_id": registration, "code": wrong})
            self.assertEqual(response.status_code, 400)
        self.assertEqual((await self.client.post("/auth/register/confirm", json={"registration_id": registration, "code": code})).status_code, 200)
        self.assertEqual((await self.client.post("/auth/register/confirm", json={"registration_id": registration, "code": code})).status_code, 400)
        response = await self.client.post("/auth/login", json={"email": email.upper(), "password": "abcdefgh"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["role"], "COMMON")
        self.assertEqual(set(response.json()), {"id", "first_name", "role"})
        self.client.headers["x-csrf-token"] = self.client.cookies["iformante_csrf"]
        self.assertEqual((await self.client.delete("/documents/nonexistent")).status_code, 403)
        self.assertEqual((await self.client.post("/auth/register", json={"name": "Teste", "email": email, "password": "abcdefgh", "confirm_password": "abcdefgh"})).status_code, 409)
        await self.client.post("/auth/logout")
        self.assertIsNone((await self.client.get("/auth/me")).json())
        self.assertEqual((await self.client.get("/conversations")).status_code, 401)

    async def test_admin_domain_and_public_document_projection(self):
        email, registration, code = await self.signup("ifpr.edu.br")
        await self.client.post("/auth/register/confirm", json={"registration_id": registration, "code": code})
        result = await self.client.post("/auth/login", json={"email": email, "password": "abcdefgh"})
        self.assertEqual(result.json()["role"], "ADMIN")
        user_id = result.json()["id"]
        for status in ["INDEXED", "ERROR"]:
            self.session.add(Document(title="Test " + secrets.token_hex(6), uploaded_by=user_id, source_type="PDF", file_name="test-" + secrets.token_hex(6) + ".pdf", stored_path="", ingestion_status=status))
        await self.session.commit()
        self.client.cookies.clear()
        response = await self.client.get("/documents")
        self.assertTrue(all(set(d) == {"id", "name", "url", "source_type"} for d in response.json()))
        self.assertEqual((await self.client.delete("/documents/nonexistent")).status_code, 401)

    async def test_reset_mask_single_use_and_session_revocation(self):
        email, registration, code = await self.signup()
        await self.client.post("/auth/register/confirm", json={"registration_id": registration, "code": code})
        await self.client.post("/auth/login", json={"email": email, "password": "abcdefgh"})
        response = await self.client.post("/auth/password/forgot", json={"email": email})
        self.assertEqual(response.status_code, 202)
        deliveries = (await self.session.execute(select(EmailDelivery))).scalars().all()
        body = next(json.loads(cipher().decrypt(d.payload.encode()))["body"] for d in deliveries if d.challenge_id.startswith("reset:"))
        token = body.split("token=")[1].split()[0]
        response = await self.client.post("/auth/password/reset/validate", json={"token": token})
        self.assertEqual(response.json(), {"masked_email": mask_email(email)})
        self.assertNotIn("@", response.text)
        response = await self.client.post("/auth/password/reset", json={"token": token, "password": "newpass1", "confirm_password": "newpass1"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual((await self.client.post("/auth/password/reset/validate", json={"token": token})).status_code, 400)
        self.assertIsNone((await self.client.get("/auth/me")).json())

    async def test_invalid_domain_and_short_password(self):
        for email, password in [("test@evil.ifpr.edu.br", "abcdefgh"), ("test@ifpr.edu.br", "short")]:
            response = await self.client.post("/auth/register", json={"name": "Teste", "email": email, "password": password, "confirm_password": password})
            self.assertEqual(response.status_code, 400)
            self.assertNotIn(email, response.text)

    async def test_expired_and_other_owner_conversations_are_hidden(self):
        email, registration, code = await self.signup()
        await self.client.post("/auth/register/confirm", json={"registration_id": registration, "code": code})
        login = await self.client.post("/auth/login", json={"email": email, "password": "abcdefgh"})
        owner = login.json()["id"]
        active = Conversation(user_id=owner, title="Active", expires_at=now() + timedelta(days=7))
        expired = Conversation(user_id=owner, title="Expired", expires_at=now() - timedelta(seconds=1))
        other = Conversation(user_id="isaque123", title="Other", expires_at=now() + timedelta(days=7))
        self.session.add_all([active, expired, other])
        await self.session.commit()
        result = await self.client.get("/conversations")
        self.assertEqual([item["id"] for item in result.json()], [active.id])
        self.assertEqual((await self.client.get(f"/conversations/{expired.id}")).status_code, 404)
        self.assertEqual((await self.client.get(f"/conversations/{other.id}")).status_code, 404)
        self.assertEqual((await self.client.get(f"/conversations/{active.id}")).status_code, 200)

if __name__ == "__main__": unittest.main()
