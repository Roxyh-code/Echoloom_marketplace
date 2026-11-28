"""Durable daily synthesis budgets."""
import sqlalchemy as sa
from alembic import op
revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None
def upgrade():
    op.create_table("voice_usage_daily",
        sa.Column("scope", sa.String(80), primary_key=True),
        sa.Column("day", sa.String(10), primary_key=True),
        sa.Column("characters", sa.Integer(), nullable=False),
        sa.CheckConstraint("characters >= 0", name="ck_voice_usage_nonnegative"))
def downgrade():
    op.drop_table("voice_usage_daily")
