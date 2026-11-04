"""Persist investigation execution state, evidence, and timeline."""

from alembic import op
import sqlalchemy as sa

revision = "0002_investigation_storage"
down_revision = "0001_incident_storage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "investigations",
        sa.Column("investigation_id", sa.String(length=100), primary_key=True),
        sa.Column("incident_id", sa.String(length=100),
                  sa.ForeignKey("incidents.incident_id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completion_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state_json", sa.JSON(), nullable=False),
        sa.Column("report_json", sa.JSON(), nullable=True),
        sa.Column("errors_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_investigations_incident_id", "investigations", ["incident_id"])
    op.create_index("ix_investigations_status", "investigations", ["status"])
    op.create_table(
        "investigation_timeline",
        sa.Column("event_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("investigation_id", sa.String(length=100),
                  sa.ForeignKey("investigations.investigation_id", ondelete="CASCADE"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("step", sa.String(length=80), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
    )
    op.create_index("ix_investigation_timeline_id_timestamp", "investigation_timeline",
                    ["investigation_id", "timestamp"])


def downgrade() -> None:
    op.drop_index("ix_investigation_timeline_id_timestamp", table_name="investigation_timeline")
    op.drop_table("investigation_timeline")
    op.drop_index("ix_investigations_status", table_name="investigations")
    op.drop_index("ix_investigations_incident_id", table_name="investigations")
    op.drop_table("investigations")
