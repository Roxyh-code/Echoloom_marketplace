"""Allow account-owned character listings to be published without a wallet.

Publishing and monetization are independent:
- A creator may have no payout wallet until enabling monetization.
- A published listing is not automatically eligible for paid scenes.
- All existing listings begin with monetization_enabled=False.
- Existing wallet strings are NOT marked verified by this migration.

SQLite needs Alembic's batch mode to rebuild tables when relaxing NOT NULL.
Existing rows, listing revisions and indexes are preserved.
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Relax the creator-wallet requirement for ordinary character publishing.
    with op.batch_alter_table("marketplace_creators") as batch:
        batch.alter_column(
            "wallet_address",
            existing_type=sa.String(length=64),
            existing_nullable=False,
            nullable=True,
        )
        batch.add_column(sa.Column("wallet_verified_at", sa.String(length=40), nullable=True))

    # Publishing a listing never enables monetization implicitly.
    op.add_column(
        "character_listings",
        sa.Column(
            "monetization_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # Old snapshots remain intact; future wallet-free publish revisions may
    # store NULL. Later monetization must create a NEW pinned payout revision.
    with op.batch_alter_table("character_listing_revisions") as batch:
        batch.alter_column(
            "payout_wallet_address",
            existing_type=sa.String(length=64),
            existing_nullable=False,
            nullable=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    # The previous schema requires a wallet for every creator and revision.
    # Refuse a destructive rollback if wallet-free records already exist.
    missing_creator_wallet = bind.execute(
        sa.text("SELECT 1 FROM marketplace_creators WHERE wallet_address IS NULL LIMIT 1")
    ).first()
    missing_revision_wallet = bind.execute(
        sa.text(
            "SELECT 1 FROM character_listing_revisions "
            "WHERE payout_wallet_address IS NULL LIMIT 1"
        )
    ).first()
    if missing_creator_wallet or missing_revision_wallet:
        raise RuntimeError(
            "Cannot downgrade 0007: wallet-free creator/listing rows exist. "
            "Back up the database and resolve them before downgrading."
        )

    with op.batch_alter_table("character_listing_revisions") as batch:
        batch.alter_column(
            "payout_wallet_address",
            existing_type=sa.String(length=64),
            existing_nullable=True,
            nullable=False,
        )

    op.drop_column("character_listings", "monetization_enabled")

    with op.batch_alter_table("marketplace_creators") as batch:
        batch.drop_column("wallet_verified_at")
        batch.alter_column(
            "wallet_address",
            existing_type=sa.String(length=64),
            existing_nullable=True,
            nullable=False,
        )
