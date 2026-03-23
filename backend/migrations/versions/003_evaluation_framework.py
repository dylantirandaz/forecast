"""Add evaluation framework tables: historical questions, evidence, eval sets, runs, predictions.

Revision ID: 003
Revises: 002
Create Date: 2026-03-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Enum type names (PostgreSQL native enums)
# ---------------------------------------------------------------------------
question_domain_enum = postgresql.ENUM(
    "macro", "politics", "technology", "business", "science",
    "housing", "energy", "health", "geopolitics", "other",
    name="question_domain_enum", create_type=False,
)
question_type_eval_enum = postgresql.ENUM(
    "binary", "continuous", "multi",
    name="question_type_eval_enum", create_type=False,
)
eval_run_status_enum = postgresql.ENUM(
    "pending", "running", "completed", "failed",
    name="eval_run_status_enum", create_type=False,
)


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Create enum types
    # ------------------------------------------------------------------
    question_domain_enum.create(op.get_bind(), checkfirst=True)
    question_type_eval_enum.create(op.get_bind(), checkfirst=True)
    eval_run_status_enum.create(op.get_bind(), checkfirst=True)

    # ------------------------------------------------------------------
    # historical_questions
    # ------------------------------------------------------------------
    op.create_table(
        "historical_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("question_text", sa.Text, nullable=False),
        sa.Column("domain", question_domain_enum, nullable=False),
        sa.Column("question_type", question_type_eval_enum, nullable=False),
        sa.Column("open_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("close_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolve_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolution_criteria", sa.Text, nullable=False),
        sa.Column("resolved_value", sa.Float, nullable=False),
        sa.Column("forecast_cutoff_days", postgresql.JSONB, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("difficulty", sa.String(20), nullable=True),
        sa.Column("source_platform", sa.String(100), nullable=True),
        sa.Column("source_url", sa.String(500), nullable=True),
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
    op.create_index("ix_hist_q_domain", "historical_questions", ["domain"])
    op.create_index("ix_hist_q_type", "historical_questions", ["question_type"])
    op.create_index("ix_hist_q_resolve", "historical_questions", ["resolve_date"])

    # ------------------------------------------------------------------
    # historical_evidence
    # ------------------------------------------------------------------
    op.create_table(
        "historical_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("historical_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("url", sa.String(500), nullable=True),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_quality_score", sa.Float, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
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
    op.create_index("ix_hist_ev_question", "historical_evidence", ["question_id"])
    op.create_index("ix_hist_ev_published", "historical_evidence", ["published_at"])

    # ------------------------------------------------------------------
    # evaluation_sets
    # ------------------------------------------------------------------
    op.create_table(
        "evaluation_sets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("domains_included", postgresql.JSONB, nullable=True),
        sa.Column("difficulty_mix", postgresql.JSONB, nullable=True),
        sa.Column("num_questions", sa.Integer, nullable=True, server_default="0"),
        sa.Column("question_ids", postgresql.JSONB, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
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

    # ------------------------------------------------------------------
    # eval_runs
    # ------------------------------------------------------------------
    op.create_table(
        "eval_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "evaluation_set_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evaluation_sets.id"),
            nullable=True,
        ),
        sa.Column("model_config", postgresql.JSONB, nullable=True),
        sa.Column("ablation_flags", postgresql.JSONB, nullable=True),
        sa.Column("cutoff_days", postgresql.JSONB, nullable=True),
        sa.Column(
            "status",
            eval_run_status_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("mean_brier_score", sa.Float, nullable=True),
        sa.Column("mean_log_score", sa.Float, nullable=True),
        sa.Column("calibration_error", sa.Float, nullable=True),
        sa.Column("sharpness", sa.Float, nullable=True),
        sa.Column("total_questions", sa.Integer, nullable=True),
        sa.Column("total_cost_usd", sa.Float, nullable=True),
        sa.Column("total_latency_ms", sa.Integer, nullable=True),
        sa.Column("results_by_domain", postgresql.JSONB, nullable=True),
        sa.Column("results_by_horizon", postgresql.JSONB, nullable=True),
        sa.Column("results_by_difficulty", postgresql.JSONB, nullable=True),
        sa.Column("full_results", postgresql.JSONB, nullable=True),
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
    op.create_index("ix_eval_run_status", "eval_runs", ["status"])

    # ------------------------------------------------------------------
    # eval_predictions
    # ------------------------------------------------------------------
    op.create_table(
        "eval_predictions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "eval_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("eval_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("historical_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("cutoff_days", sa.Integer, nullable=False),
        sa.Column("cutoff_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("predicted_probability", sa.Float, nullable=False),
        sa.Column("predicted_mean", sa.Float, nullable=True),
        sa.Column("predicted_std", sa.Float, nullable=True),
        sa.Column("confidence_lower", sa.Float, nullable=True),
        sa.Column("confidence_upper", sa.Float, nullable=True),
        sa.Column("actual_value", sa.Float, nullable=False),
        sa.Column("brier_score", sa.Float, nullable=True),
        sa.Column("log_score", sa.Float, nullable=True),
        sa.Column("evidence_count", sa.Integer, nullable=True, server_default="0"),
        sa.Column("base_rate_used", sa.Float, nullable=True),
        sa.Column("model_tier_used", sa.String(10), nullable=True),
        sa.Column("cost_usd", sa.Float, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("rationale", sa.Text, nullable=True),
        sa.Column("pipeline_trace", postgresql.JSONB, nullable=True),
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
    op.create_unique_constraint(
        "uq_eval_pred", "eval_predictions",
        ["eval_run_id", "question_id", "cutoff_days"],
    )
    op.create_index("ix_eval_pred_run", "eval_predictions", ["eval_run_id"])
    op.create_index("ix_eval_pred_question", "eval_predictions", ["question_id"])


def downgrade() -> None:
    # Drop tables in reverse creation order
    op.drop_table("eval_predictions")
    op.drop_table("eval_runs")
    op.drop_table("evaluation_sets")
    op.drop_table("historical_evidence")
    op.drop_table("historical_questions")

    # Drop enum types
    eval_run_status_enum.drop(op.get_bind(), checkfirst=True)
    question_type_eval_enum.drop(op.get_bind(), checkfirst=True)
    question_domain_enum.drop(op.get_bind(), checkfirst=True)
