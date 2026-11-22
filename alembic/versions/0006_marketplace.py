"""Add marketplace creator identities and versioned public character listings.

The migration creates empty tables only; existing character, profile, portrait,
and rehearsal records are not changed.
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketplace_creators",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=True),
        sa.Column("wallet_address", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column(
            "is_approved", sa.Boolean(), nullable=False, server_default="0"
        ),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["user_accounts.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("account_id"),
    )
    op.create_index(
        "ix_marketplace_creators_wallet_address",
        "marketplace_creators",
        ["wallet_address"],
        unique=True,
    )

    op.create_table(
        "character_listings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("character_id", sa.String(36), nullable=False),
        sa.Column("creator_id", sa.String(36), nullable=False),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="unpublished"
        ),
        sa.Column("latest_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(
            ["character_id"], ["characters.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"], ["marketplace_creators.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("character_id"),
    )
    op.create_index(
        "ix_character_listings_creator_id", "character_listings", ["creator_id"]
    )

    op.create_table(
        "character_listing_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("listing_id", sa.String(36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("profile_revision_id", sa.String(36), nullable=False),
        sa.Column("character_version", sa.Integer(), nullable=False),
        sa.Column("portrait_id", sa.String(36), nullable=True),
        sa.Column("public_data", sa.JSON(), nullable=False),
        sa.Column("payout_wallet_address", sa.String(64), nullable=False),
        sa.Column("rights_basis", sa.String(20), nullable=False),
        sa.Column("rights_confirmed_at", sa.String(40), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(
            ["listing_id"], ["character_listings.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["profile_revision_id"], ["character_profiles.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["portrait_id"], ["character_images.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("listing_id", "revision"),
    )
    op.create_index(
        "ix_character_listing_revisions_listing_id",
        "character_listing_revisions",
        ["listing_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_character_listing_revisions_listing_id",
        table_name="character_listing_revisions",
    )
    op.drop_table("character_listing_revisions")

    op.drop_index("ix_character_listings_creator_id", table_name="character_listings")
    op.drop_table("character_listings")

    op.drop_index(
        "ix_marketplace_creators_wallet_address", table_name="marketplace_creators"
    )
    op.drop_table("marketplace_creators")
