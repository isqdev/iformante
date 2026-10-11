"""Delivery modality and playback acknowledgement for voice calls."""
from alembic import op
import sqlalchemy as sa

revision = "202610110002"
down_revision = "202610110001"
branch_labels = depends_on = None


def upgrade():
    op.add_column("conversations", sa.Column("channel", sa.String(10), nullable=False, server_default="text"))
    op.add_column("messages", sa.Column("response_mode", sa.String(10), nullable=False, server_default="text"))
    op.add_column("messages", sa.Column("playback_status", sa.String(16), nullable=True))


def downgrade():
    op.drop_column("messages", "playback_status")
    op.drop_column("messages", "response_mode")
    op.drop_column("conversations", "channel")
