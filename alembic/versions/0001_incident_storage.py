"""Create persistent incident, history, and correlation tables."""

from alembic import op
import sqlalchemy as sa

revision = "0001_incident_storage"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("incident_id", sa.String(length=100), primary_key=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True, unique=True),
        sa.Column("payload_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("service_name", sa.String(length=100), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("alert_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("affected_services", sa.JSON(), nullable=False),
        sa.Column("metrics_snapshot", sa.JSON(), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
    )
    op.create_index("ix_incidents_service_severity", "incidents", ["service_name", "severity"])
    op.create_index("ix_incidents_created_at", "incidents", ["created_at"])
    op.create_index("ix_incidents_correlation_id", "incidents", ["correlation_id"])

    op.create_table(
        "incident_history",
        sa.Column("history_id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("incident_id", sa.String(length=100),
                  sa.ForeignKey("incidents.incident_id", ondelete="CASCADE"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event", sa.String(length=40), nullable=False),
        sa.Column("previous_status", sa.String(length=16), nullable=True),
        sa.Column("new_status", sa.String(length=16), nullable=True),
        sa.Column("related_incident_id", sa.String(length=100), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
    )
    op.create_index("ix_incident_history_incident_timestamp", "incident_history", ["incident_id", "timestamp"])

    op.create_table(
        "incident_correlations",
        sa.Column("left_incident_id", sa.String(length=100),
                  sa.ForeignKey("incidents.incident_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("right_incident_id", sa.String(length=100),
                  sa.ForeignKey("incidents.incident_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("left_incident_id < right_incident_id", name="ck_correlation_order"),
    )


def downgrade() -> None:
    op.drop_table("incident_correlations")
    op.drop_index("ix_incident_history_incident_timestamp", table_name="incident_history")
    op.drop_table("incident_history")
    op.drop_index("ix_incidents_correlation_id", table_name="incidents")
    op.drop_index("ix_incidents_created_at", table_name="incidents")
    op.drop_index("ix_incidents_service_severity", table_name="incidents")
    op.drop_table("incidents")
