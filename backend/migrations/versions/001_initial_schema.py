"""Initial schema for NYC Housing Forecasting system.

Revision ID: 001
Revises: None
Create Date: 2026-03-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Enum type names (PostgreSQL native enums)
# ---------------------------------------------------------------------------
target_category_enum = postgresql.ENUM(
    "supply", "price", "quality", name="target_category_enum", create_type=False
)
target_frequency_enum = postgresql.ENUM(
    "monthly", "quarterly", "annual", name="target_frequency_enum", create_type=False
)
target_type_enum = postgresql.ENUM(
    "binary", "continuous", "categorical", name="target_type_enum", create_type=False
)
question_status_enum = postgresql.ENUM(
    "active", "resolved", "retired", name="question_status_enum", create_type=False
)
scenario_intensity_enum = postgresql.ENUM(
    "soft", "moderate", "aggressive", name="scenario_intensity_enum", create_type=False
)
model_type_enum = postgresql.ENUM(
    "bayesian_updater", "ensemble", "llm_structured", "statistical", "hybrid",
    name="model_type_enum", create_type=False,
)
policy_event_type_enum = postgresql.ENUM(
    "legislation", "executive_order", "regulatory_change", "budget", "court_ruling",
    name="policy_event_type_enum", create_type=False,
)
source_type_enum = postgresql.ENUM(
    "official_data", "research", "news", "expert", "model_output",
    name="source_type_enum", create_type=False,
)
directional_effect_enum = postgresql.ENUM(
    "positive", "negative", "neutral", "ambiguous",
    name="directional_effect_enum", create_type=False,
)
forecast_status_enum = postgresql.ENUM(
    "draft", "published", "superseded", name="forecast_status_enum", create_type=False
)
backtest_status_enum = postgresql.ENUM(
    "pending", "running", "completed", "failed",
    name="backtest_status_enum", create_type=False,
)


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Create enum types
    # ------------------------------------------------------------------
    target_category_enum.create(op.get_bind(), checkfirst=True)
    target_frequency_enum.create(op.get_bind(), checkfirst=True)
    target_type_enum.create(op.get_bind(), checkfirst=True)
    question_status_enum.create(op.get_bind(), checkfirst=True)
    scenario_intensity_enum.create(op.get_bind(), checkfirst=True)
    model_type_enum.create(op.get_bind(), checkfirst=True)
    policy_event_type_enum.create(op.get_bind(), checkfirst=True)
    source_type_enum.create(op.get_bind(), checkfirst=True)
    directional_effect_enum.create(op.get_bind(), checkfirst=True)
    forecast_status_enum.create(op.get_bind(), checkfirst=True)
    backtest_status_enum.create(op.get_bind(), checkfirst=True)

    # ------------------------------------------------------------------
    # targets
    # ------------------------------------------------------------------
    op.create_table(
        "targets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", target_category_enum, nullable=False),
        sa.Column("metric_key", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("unit", sa.String(100), nullable=True),
        sa.Column("frequency", target_frequency_enum, nullable=False),
        sa.Column("geography", sa.String(100), nullable=False, server_default="nyc"),
        sa.Column("data_source", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ------------------------------------------------------------------
    # forecasting_questions
    # ------------------------------------------------------------------
    op.create_table(
        "forecasting_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("target_type", target_type_enum, nullable=False),
        sa.Column("target_metric", sa.String(255), nullable=True),
        sa.Column("unit_of_analysis", sa.String(255), nullable=True),
        sa.Column("forecast_horizon_months", sa.Integer, nullable=True),
        sa.Column("resolution_criteria", sa.Text, nullable=True),
        sa.Column(
            "status",
            question_status_enum,
            nullable=False,
            server_default="active",
        ),
        sa.Column("resolution_date", sa.Date, nullable=True),
        sa.Column("resolution_value", sa.Float, nullable=True),
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
        "ix_forecasting_questions_status",
        "forecasting_questions",
        ["status"],
    )
    op.create_index(
        "ix_forecasting_questions_target_type",
        "forecasting_questions",
        ["target_type"],
    )

    # ------------------------------------------------------------------
    # scenarios
    # ------------------------------------------------------------------
    op.create_table(
        "scenarios",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("narrative", sa.Text, nullable=True),
        sa.Column("assumptions", postgresql.JSONB, nullable=True),
        sa.Column("policy_levers", postgresql.JSONB, nullable=True),
        sa.Column("timing_start", sa.Date, nullable=True),
        sa.Column("timing_end", sa.Date, nullable=True),
        sa.Column("intensity", scenario_intensity_enum, nullable=True),
        sa.Column("expected_channels", postgresql.JSONB, nullable=True),
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
    # model_versions
    # ------------------------------------------------------------------
    op.create_table(
        "model_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("model_type", model_type_enum, nullable=False),
        sa.Column("config", postgresql.JSONB, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "is_active", sa.Boolean, nullable=False, server_default=sa.text("true")
        ),
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
    # policy_events
    # ------------------------------------------------------------------
    op.create_table(
        "policy_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("event_type", policy_event_type_enum, nullable=False),
        sa.Column("effective_date", sa.Date, nullable=True),
        sa.Column("announced_date", sa.Date, nullable=True),
        sa.Column("jurisdiction", sa.String(255), nullable=True),
        sa.Column("affected_targets", postgresql.JSONB, nullable=True),
        sa.Column("source_url", sa.String(2048), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_policy_events_event_type", "policy_events", ["event_type"]
    )
    op.create_index(
        "ix_policy_events_effective_date", "policy_events", ["effective_date"]
    )

    # ------------------------------------------------------------------
    # source_documents
    # ------------------------------------------------------------------
    op.create_table(
        "source_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("document_type", sa.String(100), nullable=True),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column("file_path", sa.String(1024), nullable=True),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ------------------------------------------------------------------
    # base_rates
    # ------------------------------------------------------------------
    op.create_table(
        "base_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("target_metric", sa.String(255), nullable=False),
        sa.Column(
            "geography", sa.String(100), nullable=False, server_default="nyc"
        ),
        sa.Column("period_start", sa.Date, nullable=True),
        sa.Column("period_end", sa.Date, nullable=True),
        sa.Column("mean_value", sa.Float, nullable=True),
        sa.Column("median_value", sa.Float, nullable=True),
        sa.Column("std_dev", sa.Float, nullable=True),
        sa.Column("percentile_10", sa.Float, nullable=True),
        sa.Column("percentile_90", sa.Float, nullable=True),
        sa.Column("sample_size", sa.Integer, nullable=True),
        sa.Column("data_source", sa.String(255), nullable=True),
        sa.Column("methodology_notes", sa.Text, nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_base_rates_target_metric", "base_rates", ["target_metric"]
    )
    op.create_index(
        "ix_base_rates_geography", "base_rates", ["geography"]
    )

    # ------------------------------------------------------------------
    # evidence_items
    # ------------------------------------------------------------------
    op.create_table(
        "evidence_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("source_url", sa.String(2048), nullable=True),
        sa.Column("source_name", sa.String(255), nullable=True),
        sa.Column("source_type", source_type_enum, nullable=False),
        sa.Column("content_summary", sa.Text, nullable=True),
        sa.Column("raw_content", sa.Text, nullable=True),
        sa.Column("published_date", sa.Date, nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_evidence_items_source_type", "evidence_items", ["source_type"]
    )

    # ------------------------------------------------------------------
    # evidence_scores
    # ------------------------------------------------------------------
    op.create_table(
        "evidence_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "evidence_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evidence_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("forecasting_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_credibility", sa.Float, nullable=True),
        sa.Column("recency_score", sa.Float, nullable=True),
        sa.Column("domain_relevance", sa.Float, nullable=True),
        sa.Column("redundancy_score", sa.Float, nullable=True),
        sa.Column("directional_effect", directional_effect_enum, nullable=True),
        sa.Column("expected_magnitude", sa.Float, nullable=True),
        sa.Column("uncertainty", sa.Float, nullable=True),
        sa.Column("composite_weight", sa.Float, nullable=True),
        sa.Column(
            "scored_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_evidence_scores_question_id", "evidence_scores", ["question_id"]
    )
    op.create_index(
        "ix_evidence_scores_evidence_item_id",
        "evidence_scores",
        ["evidence_item_id"],
    )

    # ------------------------------------------------------------------
    # forecast_runs
    # ------------------------------------------------------------------
    op.create_table(
        "forecast_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("forecasting_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "scenario_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scenarios.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "model_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("model_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("prior_value", sa.Float, nullable=True),
        sa.Column("posterior_value", sa.Float, nullable=True),
        sa.Column("prior_distribution", postgresql.JSONB, nullable=True),
        sa.Column("posterior_distribution", postgresql.JSONB, nullable=True),
        sa.Column("confidence_lower", sa.Float, nullable=True),
        sa.Column("confidence_upper", sa.Float, nullable=True),
        sa.Column("rationale", sa.Text, nullable=True),
        sa.Column(
            "status",
            forecast_status_enum,
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_forecast_runs_question_id", "forecast_runs", ["question_id"]
    )
    op.create_index(
        "ix_forecast_runs_scenario_id", "forecast_runs", ["scenario_id"]
    )
    op.create_index(
        "ix_forecast_runs_status", "forecast_runs", ["status"]
    )

    # ------------------------------------------------------------------
    # forecast_updates
    # ------------------------------------------------------------------
    op.create_table(
        "forecast_updates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "forecast_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("forecast_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("update_order", sa.Integer, nullable=False),
        sa.Column("prior_value", sa.Float, nullable=True),
        sa.Column("posterior_value", sa.Float, nullable=True),
        sa.Column(
            "evidence_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evidence_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("weight_applied", sa.Float, nullable=True),
        sa.Column("shift_applied", sa.Float, nullable=True),
        sa.Column("rationale", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_forecast_updates_forecast_run_id",
        "forecast_updates",
        ["forecast_run_id"],
    )

    # ------------------------------------------------------------------
    # resolutions
    # ------------------------------------------------------------------
    op.create_table(
        "resolutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("forecasting_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "forecast_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("forecast_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actual_value", sa.Float, nullable=True),
        sa.Column("actual_date", sa.Date, nullable=True),
        sa.Column("brier_score", sa.Float, nullable=True),
        sa.Column("log_score", sa.Float, nullable=True),
        sa.Column("calibration_bucket", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_resolutions_question_id", "resolutions", ["question_id"]
    )

    # ------------------------------------------------------------------
    # scores
    # ------------------------------------------------------------------
    op.create_table(
        "scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "model_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("model_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("period_start", sa.Date, nullable=True),
        sa.Column("period_end", sa.Date, nullable=True),
        sa.Column("total_questions", sa.Integer, nullable=True),
        sa.Column("mean_brier_score", sa.Float, nullable=True),
        sa.Column("mean_log_score", sa.Float, nullable=True),
        sa.Column("calibration_error", sa.Float, nullable=True),
        sa.Column("resolution_score", sa.Float, nullable=True),
        sa.Column("sharpness", sa.Float, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_scores_model_version_id", "scores", ["model_version_id"]
    )

    # ------------------------------------------------------------------
    # backtest_runs
    # ------------------------------------------------------------------
    op.create_table(
        "backtest_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "model_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("model_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("targets", postgresql.JSONB, nullable=True),
        sa.Column("config", postgresql.JSONB, nullable=True),
        sa.Column(
            "status",
            backtest_status_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("results_summary", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_backtest_runs_status", "backtest_runs", ["status"]
    )

    # ------------------------------------------------------------------
    # backtest_forecasts
    # ------------------------------------------------------------------
    op.create_table(
        "backtest_forecasts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "backtest_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("backtest_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("forecasting_questions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("forecast_date", sa.Date, nullable=True),
        sa.Column("cutoff_date", sa.Date, nullable=True),
        sa.Column("predicted_value", sa.Float, nullable=True),
        sa.Column("predicted_distribution", postgresql.JSONB, nullable=True),
        sa.Column("actual_value", sa.Float, nullable=True),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_backtest_forecasts_backtest_run_id",
        "backtest_forecasts",
        ["backtest_run_id"],
    )


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("backtest_forecasts")
    op.drop_table("backtest_runs")
    op.drop_table("scores")
    op.drop_table("resolutions")
    op.drop_table("forecast_updates")
    op.drop_table("forecast_runs")
    op.drop_table("evidence_scores")
    op.drop_table("evidence_items")
    op.drop_table("base_rates")
    op.drop_table("source_documents")
    op.drop_table("policy_events")
    op.drop_table("model_versions")
    op.drop_table("scenarios")
    op.drop_table("forecasting_questions")
    op.drop_table("targets")

    # Drop enum types
    backtest_status_enum.drop(op.get_bind(), checkfirst=True)
    forecast_status_enum.drop(op.get_bind(), checkfirst=True)
    directional_effect_enum.drop(op.get_bind(), checkfirst=True)
    source_type_enum.drop(op.get_bind(), checkfirst=True)
    policy_event_type_enum.drop(op.get_bind(), checkfirst=True)
    model_type_enum.drop(op.get_bind(), checkfirst=True)
    scenario_intensity_enum.drop(op.get_bind(), checkfirst=True)
    question_status_enum.drop(op.get_bind(), checkfirst=True)
    target_type_enum.drop(op.get_bind(), checkfirst=True)
    target_frequency_enum.drop(op.get_bind(), checkfirst=True)
    target_category_enum.drop(op.get_bind(), checkfirst=True)
