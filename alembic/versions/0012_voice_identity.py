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
    # SQLite >= 3.35 supports native DROP COLUMN. Rebuilding characters via
    # batch_alter_table would DROP the parent table under foreign_keys=ON,
    # cascading deletion of profiles/conversations/messages.
    # Neither of these optional JSON columns participates in an FK or index.
    op.drop_column("character_listing_revisions", "voice_identity")
    op.drop_column("characters", "voice_identity")
