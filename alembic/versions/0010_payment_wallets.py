"""Add verified buyer wallets and one-time challenges."""
import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "payment_buyer_wallets",
        sa.Column("account_id", sa.String(36), sa.ForeignKey("user_accounts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("wallet", sa.String(44), nullable=False, unique=True),
        sa.Column("verified_at", sa.String(40), nullable=False),
    )
    op.create_table(
        "payment_wallet_challenges",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("user_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("wallet", sa.String(44), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("expires_at_unix", sa.BigInteger(), nullable=False),
        sa.Column("consumed_at", sa.String(40), nullable=True),
    )
    op.create_index("ix_payment_wallet_challenges_account_id", "payment_wallet_challenges", ["account_id"])


def downgrade():
    op.drop_index("ix_payment_wallet_challenges_account_id", table_name="payment_wallet_challenges")
    op.drop_table("payment_wallet_challenges")
    op.drop_table("payment_buyer_wallets")
