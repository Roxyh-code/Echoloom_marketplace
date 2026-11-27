"""Immutable creator attribution at quote time."""
import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "payment_creator_earning_snapshots",
        sa.Column("order_id", sa.String(36), sa.ForeignKey("payment_orders.id"), primary_key=True),
        sa.Column("cast_slot", sa.Integer(), primary_key=True),
        sa.Column("creator_account_id", sa.String(36), nullable=False),
        sa.Column("character_id", sa.String(36), nullable=False),
        sa.Column("listing_id", sa.String(36), nullable=True),
        sa.Column("listing_revision", sa.Integer(), nullable=True),
        sa.Column("character_name", sa.String(80), nullable=False),
        sa.Column("wallet", sa.String(44), nullable=False),
        sa.Column("amount_minor_units", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("amount_minor_units > 0", name="ck_creator_earning_amount"),
    )
    op.create_index("ix_payment_creator_earning_snapshots_creator_account_id",
                    "payment_creator_earning_snapshots", ["creator_account_id"])


def downgrade():
    op.drop_index("ix_payment_creator_earning_snapshots_creator_account_id",
                  table_name="payment_creator_earning_snapshots")
    op.drop_table("payment_creator_earning_snapshots")
