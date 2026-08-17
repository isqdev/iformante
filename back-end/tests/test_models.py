import string
import unittest

from sqlalchemy import String

from app.models import Base, generate_id
from app.config import Settings
from app.security import hash_password, verify_password


class ModelTests(unittest.TestCase):
    def test_generate_id_returns_nine_lowercase_alphanumeric_characters(self) -> None:
        generated_id = generate_id()

        self.assertEqual(len(generated_id), 9)
        self.assertTrue(
            all(
                character in string.ascii_lowercase + string.digits
                for character in generated_id
            ),
        )

    def test_metadata_contains_relational_tables(self) -> None:
        self.assertEqual(
            {"users", "documents", "conversations", "messages"},
            set(Base.metadata.tables.keys()),
        )

    def test_user_has_password_hash_column(self) -> None:
        users_table = Base.metadata.tables["users"]

        self.assertIn("password_hash", users_table.columns)
        self.assertFalse(users_table.columns["password_hash"].nullable)

    def test_enum_values_are_stored_as_strings(self) -> None:
        users_table = Base.metadata.tables["users"]
        documents_table = Base.metadata.tables["documents"]
        messages_table = Base.metadata.tables["messages"]

        self.assertIsInstance(users_table.columns["role"].type, String)
        self.assertIsInstance(documents_table.columns["ingestion_status"].type, String)
        self.assertIsInstance(messages_table.columns["author"].type, String)


    def test_password_hash_can_be_verified(self) -> None:
        password = "senha-segura-123"

        hashed_password = hash_password(password)

        self.assertNotEqual(password, hashed_password)
        self.assertTrue(verify_password(password, hashed_password))
        self.assertFalse(verify_password("senha-errada", hashed_password))

    def test_conversation_supports_anonymous_owner(self) -> None:
        conversations_table = Base.metadata.tables["conversations"]

        self.assertIn("anonymous_id", conversations_table.columns)
        self.assertTrue(conversations_table.columns["user_id"].nullable)
        self.assertTrue(conversations_table.columns["anonymous_id"].nullable)
        self.assertEqual(conversations_table.columns["anonymous_id"].type.length, 9)

    def test_database_url_is_normalized_for_asyncpg(self) -> None:
        database_url = Settings._normalize_database_url(
            "postgresql://user:pass@host/db?sslmode=require&channel_binding=require",
        )

        self.assertEqual(
            database_url,
            "postgresql+asyncpg://user:pass@host/db?ssl=require",
        )


if __name__ == "__main__":
    unittest.main()
