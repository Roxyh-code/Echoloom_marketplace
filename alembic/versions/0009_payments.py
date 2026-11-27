"""Add payment order, verified payment and entitlement ledgers."""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "payment_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scene_id", sa.String(36), nullable=False),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("buyer_wallet", sa.String(44), nullable=False),
        sa.Column("product_id", sa.String(128), nullable=False),
        sa.Column("program_id", sa.String(44), nullable=False),
        sa.Column("mint", sa.String(44), nullable=False),
        sa.Column("config_pda", sa.String(44), nullable=False),
        sa.Column("receipt_pda", sa.String(44), nullable=False, unique=True),
        sa.Column("amount_minor_units", sa.BigInteger(), nullable=False),
        sa.Column("payout_lines", sa.JSON(), nullable=False),
        sa.Column("config_version", sa.BigInteger(), nullable=False),
        sa.Column("expires_at_unix", sa.BigInteger(), nullable=False),
        sa.Column("signer_pubkey", sa.String(44), nullable=False),
        sa.Column("authorization_message_b64", sa.Text(), nullable=False),
        sa.Column("authorization_signature_b64", sa.String(88), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.CheckConstraint("amount_minor_units > 0", name="ck_order_amount"),
        sa.CheckConstraint("config_version >= 0", name="ck_order_config_version"),
        sa.CheckConstraint("status IN ('pending', 'paid', 'rejected', 'expired')", name="ck_order_status"),
    )
    op.create_index("ix_payment_orders_scene_id", "payment_orders", ["scene_id"])
    op.create_index("ix_payment_orders_account_id", "payment_orders", ["account_id"])
    op.create_table(
        "payments",
        sa.Column("order_id", sa.String(36), sa.ForeignKey("payment_orders.id"), primary_key=True),
        sa.Column("tx_signature", sa.String(88), nullable=False, unique=True),
        sa.Column("verified_slot", sa.BigInteger(), nullable=False),
        sa.Column("verified_at", sa.String(40), nullable=False),
    )
    op.create_table(
        "payment_entitlements",
        sa.Column("order_id", sa.String(36), sa.ForeignKey("payments.order_id"), primary_key=True),
        sa.Column("extra_sentences", sa.Integer(), nullable=False, server_default="40"),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.CheckConstraint("extra_sentences = 40", name="ck_entitlement_sentences"),
    )


def downgrade():
    op.drop_table("payment_entitlements")
    op.drop_table("payments")
    op.drop_index("ix_payment_orders_account_id", table_name="payment_orders")
    op.drop_index("ix_payment_orders_scene_id", table_name="payment_orders")
    op.drop_table("payment_orders")
