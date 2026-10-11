"""Optional institutional authentication and seven-day conversation retention."""
from alembic import op
import sqlalchemy as sa

revision = "202610110001"
down_revision = "202608190001"
branch_labels = depends_on = None


def upgrade():
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index("uq_users_normalized_email", "users", [sa.text("lower(email)")], unique=True)
    op.add_column("conversations", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE conversations SET expires_at = created_at + interval '7 days'")
    op.alter_column("conversations", "expires_at", nullable=False)
    op.create_index("ix_conversations_expires_at", "conversations", ["expires_at"])
    op.create_table("pending_registrations",
        sa.Column("id", sa.String(32), primary_key=True), sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True), sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_send_at", sa.DateTime(timezone=True), nullable=False))
    for table in ("auth_sessions", "password_resets"):
        fields = [sa.Column("token_hash", sa.String(64), primary_key=True),
                  sa.Column("user_id", sa.String(9), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
                  sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False)]
        if table == "auth_sessions":
            fields.append(sa.Column("csrf_token", sa.String(64), nullable=False))
        op.create_table(table, *fields)
        op.create_index(f"ix_{table}_user_id", table, ["user_id"])
        op.create_index(f"ix_{table}_expires_at", table, ["expires_at"])
    op.create_table("email_deliveries", sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("payload", sa.Text(), nullable=False), sa.Column("challenge_id", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("state", sa.String(20), nullable=False))
    op.create_index("ix_email_deliveries_challenge_id", "email_deliveries", ["challenge_id"])
    op.execute("""CREATE OR REPLACE FUNCTION cleanup_iformante_expired() RETURNS void LANGUAGE plpgsql AS $$
    BEGIN
        DELETE FROM conversations WHERE expires_at <= now();
        DELETE FROM auth_sessions WHERE expires_at <= now();
        DELETE FROM password_resets WHERE expires_at <= now();
        DELETE FROM pending_registrations WHERE expires_at < now() - interval '1 day';
        DELETE FROM email_deliveries WHERE expires_at <= now() OR state <> 'PENDING';
    END; $$""")


def downgrade():
    op.execute("DROP FUNCTION IF EXISTS cleanup_iformante_expired()")
    for table in ("email_deliveries", "password_resets", "auth_sessions", "pending_registrations"):
        op.drop_table(table)
    op.drop_index("ix_conversations_expires_at", table_name="conversations")
    op.drop_column("conversations", "expires_at")
    op.drop_index("uq_users_normalized_email", table_name="users")
    op.drop_column("users", "email_verified")
