"""Private research provenance."""
import sqlalchemy as sa
from alembic import op
revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None
def upgrade():
    op.add_column("characters",sa.Column("research_data",sa.JSON(),nullable=True))
def downgrade():
    op.drop_column("characters","research_data")
