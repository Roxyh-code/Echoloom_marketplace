"""Optional owner-selected voice identity and immutable listing snapshot."""
import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("characters", sa.Column("voice_identity", sa.JSON(), nullable=True))
    op.add_column("character_listing_revisions", sa.Column("voice_identity", sa.JSON(), nullable=True))

def downgrade():
    with op.batch_alter_table("character_listing_revisions") as batch:
        batch.drop_column("voice_identity")
    with op.batch_alter_table("characters") as batch:
        batch.drop_column("voice_identity")
