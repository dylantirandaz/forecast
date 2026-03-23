"""Add benchmark, ablation, cost, and calibration-run tables.

Revision ID: 002
Revises: 001
Create Date: 2026-03-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Enum type names (PostgreSQL native enums)
# ---------------------------------------------------------------------------
experiment_type_enum = postgresql.ENUM(
    "ablation", "benchmark", "calibration_study", "model_comparison",
    name="experiment_type_enum", create_type=False,
)
experiment_status_enum = postgresql.ENUM(
    "pending", "running", "completed", "failed",
    name="experiment_status_enum", create_type=False,
)
benchmark_status_enum = postgresql.ENUM(
    "draft", "submitted", "scored", "invalidated",
    name="benchmark_status_enum", create_type=False,
)
cost_operation_type_enum = postgresql.ENUM(
    "forecast_run", "evidence_scoring", "base_rate_compute",
    "backtest_run", "experiment_run", "llm_call", "data_ingestion",
    name="cost_operation_type_enum", create_type=False,
)
calibration_scope_enum = postgresql.ENUM(
    "global", "domain_specific", "target_specific", "scenario_specific",
    name="calibration_scope_enum", create_type=False,
)
calibration_method_enum = postgresql.ENUM(
    "platt_scaling", "isotonic_regression", "histogram_binning", "none",
    name="calibration_method_enum", create_type=False,
)


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Create enum types
    # ------------------------------------------------------------------
    experiment_type_enum.create(op.get_bind(), checkfirst=True)
    experiment_status_enum.create(op.get_bind(), checkfirst=True)
    benchmark_status_enum.create(op.get_bind(), checkfirst=True)
    cost_operation_type_enum.create(op.get_bind(), checkfirst=True)
    calibration_scope_enum.create(op.get_bind(), checkfirst=True)
    calibration_method_enum.create(op.get_bind(), checkfirst=True)

    # ------------------------------------------------------------------
    # experiment_runs
    # ------------------------------------------------------------------
    op.create_table(
        "experiment_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("experiment_type", experiment_type_enum, nullable=True),
        sa.Column("config", postgresql.JSONB, nullable=True),
        sa.Column("ablation_flags", postgresql.JSONB, nullable=True),
        sa.Column(
            "model_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("model_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            experiment_status_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("results", postgresql.JSONB, nullable=True),
        sa.Column("total_cost_usd", sa.Float, nullable=True),
        sa.Column("total_questions", sa.Integer, nullable=True),
        sa.Column("mean_brier_score", sa.Float, nullable=True),
        sa.Column("mean_log_score", sa.Float, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_experiment_runs_status", "experiment_runs", ["status"]
    )
    op.create_index(
        "ix_experiment_runs_experiment_type",
        "experiment_runs",
        ["experiment_type"],
    )

    # ------------------------------------------------------------------
    # benchmark_submissions
    # ------------------------------------------------------------------
    op.create_table(
        "benchmark_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("benchmark_name", sa.String(255), nullable=False),
        sa.Column("submission_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submission_payload", postgresql.JSONB, nullable=True),
        sa.Column(
            "experiment_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiment_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "model_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("model_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("config", postgresql.JSONB, nullable=True),
        sa.Column("scores", postgresql.JSONB, nullable=True),
        sa.Column(
            "status",
            benchmark_status_enum,
            nullable=False,
            server_default="draft",
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_benchmark_submissions_benchmark_name",
        "benchmark_submissions",
        ["benchmark_name"],
    )
    op.create_index(
        "ix_benchmark_submissions_status",
        "benchmark_submissions",
        ["status"],
    )

    # ------------------------------------------------------------------
    # cost_logs
    # ------------------------------------------------------------------
    op.create_table(
        "cost_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("operation_type", cost_operation_type_enum, nullable=False),
        sa.Column(
            "reference_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("reference_type", sa.String(255), nullable=True),
        sa.Column("model_tier", sa.String(100), nullable=True),
        sa.Column("model_name", sa.String(255), nullable=True),
        sa.Column("input_tokens", sa.Integer, nullable=True),
        sa.Column("output_tokens", sa.Integer, nullable=True),
        sa.Column("cost_usd", sa.Float, nullable=False),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_cost_logs_operation_type", "cost_logs", ["operation_type"]
    )
    op.create_index(
        "ix_cost_logs_created_at", "cost_logs", ["created_at"]
    )
    op.create_index(
        "ix_cost_logs_reference_id", "cost_logs", ["reference_id"]
    )

    # ------------------------------------------------------------------
    # calibration_runs
    # ------------------------------------------------------------------
    op.create_table(
        "calibration_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("scope", calibration_scope_enum, nullable=True),
        sa.Column("domain", sa.String(255), nullable=True),
        sa.Column("target_metric", sa.String(255), nullable=True),
        sa.Column("method", calibration_method_enum, nullable=True),
        sa.Column("n_forecasts", sa.Integer, nullable=True),
        sa.Column("pre_calibration_brier", sa.Float, nullable=True),
        sa.Column("post_calibration_brier", sa.Float, nullable=True),
        sa.Column("pre_calibration_log_score", sa.Float, nullable=True),
        sa.Column("post_calibration_log_score", sa.Float, nullable=True),
        sa.Column("calibration_params", postgresql.JSONB, nullable=True),
        sa.Column("bucket_data", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_calibration_runs_scope", "calibration_runs", ["scope"]
    )
    op.create_index(
        "ix_calibration_runs_domain", "calibration_runs", ["domain"]
    )


def downgrade() -> None:
    # Drop tables in reverse creation order
    op.drop_table("calibration_runs")
    op.drop_table("cost_logs")
    op.drop_table("benchmark_submissions")
    op.drop_table("experiment_runs")

    # Drop enum types
    calibration_method_enum.drop(op.get_bind(), checkfirst=True)
    calibration_scope_enum.drop(op.get_bind(), checkfirst=True)
    cost_operation_type_enum.drop(op.get_bind(), checkfirst=True)
    benchmark_status_enum.drop(op.get_bind(), checkfirst=True)
    experiment_status_enum.drop(op.get_bind(), checkfirst=True)
    experiment_type_enum.drop(op.get_bind(), checkfirst=True)
