import asyncio
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
from app.models import AuthSession, SystemParam, User, generate_id
from app.prompts import DEFAULT_PROMPTS, PROMPT_DEFAULTS, PromptSnapshot, validate_prompt
from app.rag.generation import AnswerGenerator, QuestionRouter
from app.rag.retrieval.child_reranker import ChildReranker, RerankCandidate
from app.repositories.system_param_repository import SystemParamRepository
from app.security.auth import now, token_hash
from app.security.roles import is_admin


class PromptContractTests(unittest.IsolatedAsyncioTestCase):
    def test_voice_fields_are_validated_without_interpreting_json(self):
        for key, value in PROMPT_DEFAULTS.items():
            validate_prompt(key, value)
        for invalid in ("   ", "Sem campo automático", "{{speech_style}} {{unknown}}"):
            with self.assertRaises(ValueError):
                validate_prompt("prompt_replier_voice", invalid)
        rendered = DEFAULT_PROMPTS.voice_prompt(60)
        self.assertIn('{"used_sources": ["parent_1"]}', rendered)
        self.assertNotIn("{{max_words}}", rendered)
        self.assertNotIn("{{speech_style}}", rendered)

    def test_super_inherits_admin_permissions(self):
        for role in ("ADMIN", "SUPER"):
            self.assertTrue(is_admin(SimpleNamespace(role=role)))
        self.assertFalse(is_admin(SimpleNamespace(role="COMMON")))
        self.assertFalse(is_admin(None))

    async def test_cached_router_accepts_different_prompts_without_shared_mutation(self):
        model = SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(content="Olá!", tool_calls=[])))
        router = QuestionRouter("test-key", "test-model")
        message = SimpleNamespace(content="Oi", role="user")
        with patch.object(router, "_get_chat_model", return_value=model):
            await router.execute([message], system_prompt="Primeira versão")
            await router.execute([message], system_prompt="Segunda versão")
        self.assertEqual([call.args[0][0].content for call in model.ainvoke.call_args_list], ["Primeira versão", "Segunda versão"])

    async def test_voice_uses_snapshot_prompt_and_one_generation_above_limit(self):
        values = dict(PROMPT_DEFAULTS, prompt_speech_style="Fale naturalmente; orientação: {{max_words}} palavras.", prompt_replier_voice="Prompt novo. {{speech_style}}")
        snapshot = PromptSnapshot.from_values(values)
        model = SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(content=" ".join(["texto"] * 100))))
        generator = AnswerGenerator("test-key", "test-model")
        with patch.object(generator, "_get_chat_model", return_value=model):
            result = await generator.speech_answer("Pergunta", [], system_prompt=snapshot.voice_prompt(60))
        self.assertEqual(model.ainvoke.call_args.args[0][0].content, "Prompt novo. Fale naturalmente; orientação: 60 palavras.")
        model.ainvoke.assert_awaited_once()
        self.assertEqual(len(result.content.split()), 100)

    async def test_reranker_receives_its_prompt_from_the_turn(self):
        model = SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(content='["child_1"]')))
        with patch("app.rag.retrieval.child_reranker.ChatOpenAI", return_value=model):
            reranker = ChildReranker("test-key", system_prompt="Ordenação editada no Sistema")
            order = await reranker.rerank("Pergunta", [RerankCandidate("child_1", "Trecho")])
        self.assertEqual(order, ["child_1"])
        self.assertEqual(model.ainvoke.call_args.args[0][0].content, "Ordenação editada no Sistema")


@unittest.skipUnless(settings.database_url, "Requires configured PostgreSQL")
class SystemIntegrationTests(unittest.IsolatedAsyncioTestCase):
    """Real API/database checks, all data rolled back; no mail or AI requests."""
    async def asyncSetUp(self):
        asyncio.get_running_loop().slow_callback_duration = 30
        self.engine = create_async_engine(settings.database_url, poolclass=NullPool, connect_args={"timeout": 30})
        self.connection = await self.engine.connect()
        self.transaction = await self.connection.begin()
        self.session = AsyncSession(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        async def database():
            yield self.session
        app.dependency_overrides[get_database_session] = database
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")
        self.actor = await self.create_user("SUPER")
        self.target = await self.create_user("ADMIN")

    async def asyncTearDown(self):
        await self.client.aclose()
        app.dependency_overrides.clear()
        await self.session.close()
        await self.transaction.rollback()
        await self.connection.close()
        await self.engine.dispose()

    async def create_user(self, role, *, verified=True):
        user = User(id=generate_id(), name="Teste Sistema", email=f"test{secrets.token_hex(10)}@ifpr.edu.br", password_hash="not-used", role=role, email_verified=verified)
        self.session.add(user)
        await self.session.flush()
        return user

    async def authenticate(self, user, *, csrf=True):
        token, csrf_token = secrets.token_hex(32), secrets.token_hex(32)
        self.session.add(AuthSession(token_hash=token_hash(token), user_id=user.id, expires_at=now() + timedelta(hours=1), csrf_token=csrf_token))
        await self.session.commit()
        self.client.cookies.set("iformante_session", token)
        if csrf:
            self.client.headers["x-csrf-token"] = csrf_token
        else:
            self.client.headers.pop("x-csrf-token", None)

    async def test_prompt_permissions_csrf_and_exact_value_persistence(self):
        self.assertEqual((await self.client.get("/system/prompts")).status_code, 401)
        for role in ("COMMON", "ADMIN"):
            await self.authenticate(await self.create_user(role))
            self.assertEqual((await self.client.get("/system/prompts")).status_code, 403)
            self.assertEqual((await self.client.patch("/system/prompts/prompt_router", json={"value": "Blocked", "expected_value": ""})).status_code, 403)
            self.assertEqual((await self.client.patch("/system/users/role", json={"email": self.target.email, "role": "SUPER"})).status_code, 403)
        await self.authenticate(self.actor, csrf=False)
        response = await self.client.get("/system/prompts")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()), 6)
        self.assertTrue(all(len(prompt["id"]) == 9 for prompt in response.json()))
        original = next(prompt for prompt in response.json() if prompt["param"] == "prompt_router")
        body = {"value": "  ## Novo Router\n\nTexto literal.  \n", "expected_value": original["value"]}
        self.assertEqual((await self.client.patch("/system/prompts/prompt_router", json=body)).status_code, 403)
        await self.authenticate(self.actor)
        saved = await self.client.patch("/system/prompts/prompt_router", json=body)
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()["value"], body["value"])
        self.assertEqual((await SystemParamRepository(self.session).snapshot()).router, body["value"])
        conflict = await self.client.patch("/system/prompts/prompt_router", json={**body, "value": "Outra aba"})
        self.assertEqual(conflict.status_code, 409)

    async def test_prompt_key_empty_value_and_voice_template_validation(self):
        await self.authenticate(self.actor)
        self.assertEqual((await self.client.patch("/system/prompts/unknown", json={"value": "hello", "expected_value": ""})).status_code, 404)
        self.assertEqual((await self.client.patch("/system/prompts/prompt_router", json={"value": " \n", "expected_value": ""})).status_code, 422)
        self.assertEqual((await self.client.patch("/system/prompts/prompt_speech_style", json={"value": "{{unknown}}", "expected_value": ""})).status_code, 422)

    async def test_admin_super_transition_and_session_observes_demotion(self):
        await self.authenticate(self.actor)
        response = await self.client.patch("/system/users/role", json={"email": "  " + self.target.email.upper() + "  ", "role": "SUPER"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["role"], "SUPER")
        self.assertNotIn(self.target.email, response.text)
        await self.authenticate(self.target)
        self.assertEqual((await self.client.get("/system/prompts")).status_code, 200)
        await self.authenticate(self.actor)
        self.assertEqual((await self.client.patch("/system/users/role", json={"email": self.target.email, "role": "ADMIN"})).status_code, 200)
        await self.authenticate(self.target)
        self.assertEqual((await self.client.get("/system/prompts")).status_code, 403)
        self.assertEqual((await self.client.get("/auth/me")).json()["role"], "ADMIN")

    async def test_role_validation_self_demotion_and_super_document_access(self):
        await self.authenticate(self.actor)
        for user in (await self.create_user("COMMON"), await self.create_user("ADMIN", verified=False)):
            self.assertEqual((await self.client.patch("/system/users/role", json={"email": user.email, "role": "SUPER"})).status_code, 409)
        self.assertEqual((await self.client.patch("/system/users/role", json={"email": self.actor.email, "role": "ADMIN"})).status_code, 409)
        self.assertEqual((await self.client.patch("/system/users/role", json={"email": "nonexistent@ifpr.edu.br", "role": "SUPER"})).status_code, 404)
        self.assertEqual((await self.client.patch("/system/users/role", json={"email": self.target.email, "role": "COMMON"})).status_code, 422)
        # The existing route returns 400 for a missing document, after passing authorization.
        self.assertEqual((await self.client.delete("/documents/none00000")).status_code, 400)

    async def test_snapshot_remains_immutable_after_an_update(self):
        before = await SystemParamRepository(self.session).snapshot()
        original = (await self.session.execute(select(SystemParam).where(SystemParam.param == "prompt_router"))).scalar_one()
        await self.authenticate(self.actor)
        saved = await self.client.patch("/system/prompts/prompt_router", json={"value": "Router do próximo turno", "expected_value": original.value})
        self.assertEqual(saved.status_code, 200)
        after = await SystemParamRepository(self.session).snapshot()
        self.assertNotEqual(before.router, after.router)
        self.assertEqual(after.router, "Router do próximo turno")

    async def test_factory_loads_saved_prompt_for_the_real_use_case(self):
        from app.factories.chat import get_receive_message_use_case
        repository = SystemParamRepository(self.session)
        original = (await repository.snapshot()).router
        await repository.update_value("prompt_router", "Router carregado para este turno", original)
        await self.session.commit()
        router = SimpleNamespace(is_configured=True, execute=AsyncMock(return_value=SimpleNamespace(direct_response="Olá!")))
        generator = SimpleNamespace(is_configured=True)
        with patch("app.factories.chat.ParentRetriever"):
            use_case = await get_receive_message_use_case(self.session, router, generator)
        events = [event async for event in use_case.stream(None, None, "Oi")]
        self.assertEqual(events[-1].event, "done")
        self.assertEqual(router.execute.call_args.kwargs["system_prompt"], "Router carregado para este turno")
