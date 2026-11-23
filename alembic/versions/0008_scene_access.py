"""Add server-side Marketplace scene access, first-trial claim and usage journal.

Creates empty tables. Existing scenes/characters/listings are untouched;
legacy Marketplace scenes are initialized lazily on their first access.
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketplace_scene_access",
        sa.Column("scene_id", sa.String(36), sa.ForeignKey("rehearsal_scenes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("user_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("opening_available", sa.Integer(), server_default="0", nullable=False),
        sa.Column("directions_available", sa.Integer(), server_default="0", nullable=False),
        sa.Column("opening_consumed", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("trial_granted", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
    )
    op.create_index("ix_marketplace_scene_access_account_id", "marketplace_scene_access", ["account_id"])
    op.create_table(
        "marketplace_trial_claims",
        sa.Column("account_id", sa.String(36), sa.ForeignKey("user_accounts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("scene_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
    )
    op.create_table(
        "marketplace_scene_usage",
        sa.Column("operation_id", sa.String(36), primary_key=True),
        sa.Column("scene_id", sa.String(36), sa.ForeignKey("rehearsal_scenes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("user_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
    )
    op.create_index("ix_marketplace_scene_usage_scene_id", "marketplace_scene_usage", ["scene_id"])


def downgrade() -> None:
    op.drop_index("ix_marketplace_scene_usage_scene_id", table_name="marketplace_scene_usage")
    op.drop_table("marketplace_scene_usage")
    op.drop_table("marketplace_trial_claims")
    op.drop_index("ix_marketplace_scene_access_account_id", table_name="marketplace_scene_access")
    op.drop_table("marketplace_scene_access")
