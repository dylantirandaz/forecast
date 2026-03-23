"""LLM-based forecaster using structured superforecaster methodology.

Two modes:
1. STRUCTURED: base rate -> LLM evidence scoring -> Bayesian update -> calibration
2. DIRECT: LLM reads question + evidence, outputs probability directly

The structured mode is preferred -- it's more transparent, auditable, and
prevents the LLM from ignoring base rates or overreacting to weak evidence.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class LLMForecastResult:
    """Result from the LLM forecaster."""
    predicted_probability: float
    base_rate: float
    evidence_summary: str
    rationale: str
    confidence: str  # "low", "medium", "high"
    model_used: str
    mode: str  # "structured" or "direct"
    cost_usd: float = 0.0
    latency_ms: int = 0
    evidence_scores: list[dict] = field(default_factory=list)
    raw_response: str = ""
    tokens_in: int = 0
    tokens_out: int = 0


@dataclass
class LLMConfig:
    """Configuration for the LLM forecaster."""
    provider: str = "anthropic"  # "anthropic" or "openai"
    model: str = "claude-sonnet-4-6"  # default model
    cheap_model: str = "claude-haiku-4-5-20251001"  # for extraction/scoring
    temperature: float = 0.2  # low for consistency
    max_tokens: int = 2000
    mode: str = "structured"  # "structured" or "direct"
    use_search: bool = False  # whether to use exa.ai search
    api_key: str = ""  # set via env var
    exa_api_key: str = ""  # set via env var

    def __post_init__(self):
        if not self.api_key:
            if self.provider == "anthropic":
                self.api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            else:
                self.api_key = os.environ.get("OPENAI_API_KEY", "")
        if not self.exa_api_key:
            self.exa_api_key = os.environ.get("EXA_API_KEY", "")


# ---- Cost tracking ----
MODEL_COSTS_PER_1K = {
    "claude-sonnet-4-6": {"input": 0.003, "output": 0.015},
    "claude-haiku-4-5-20251001": {"input": 0.0008, "output": 0.004},
    "claude-opus-4-6": {"input": 0.015, "output": 0.075},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4o": {"input": 0.0025, "output": 0.01},
}


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    costs = MODEL_COSTS_PER_1K.get(model, {"input": 0.003, "output": 0.015})
    return (tokens_in / 1000 * costs["input"]) + (tokens_out / 1000 * costs["output"])


# ---- Prompts ----

SYSTEM_PROMPT_STRUCTURED = """You are a superforecaster — one of the most accurate probability estimators in the world. You follow a rigorous, disciplined forecasting methodology:

1. START FROM BASE RATES: Before looking at any specific evidence, anchor on what typically happens in similar situations. What is the historical frequency of this type of event?

2. SCORE EVIDENCE: For each piece of evidence, evaluate:
   - Source credibility (0-1): How trustworthy is this source?
   - Relevance (0-1): How directly does this bear on the question?
   - Directional impact: Does this push toward YES (+1) or NO (-1)?
   - Strength (0-1): How much should this shift the probability?

3. UPDATE INCREMENTALLY: Adjust from the base rate step by step. Don't overreact to any single piece of evidence. Strong, credible, relevant evidence should move the forecast more than weak signals.

4. STAY CALIBRATED: When you say 70%, events like this should happen about 70% of the time. Avoid extremes (below 5% or above 95%) unless the evidence is overwhelming.

5. THINK IN PROBABILITIES: Not "will this happen" but "how likely is this to happen given everything I know?"

You must respond with valid JSON only. No other text."""


EVIDENCE_SCORING_PROMPT = """Score the following evidence items for this forecasting question.

QUESTION: {question_text}
QUESTION DOMAIN: {domain}
FORECAST CUTOFF DATE: {cutoff_date} (you can only consider information available by this date)

EVIDENCE ITEMS:
{evidence_text}

For each evidence item, provide:
- source_credibility (0.0-1.0): reliability of the source
- relevance (0.0-1.0): how directly this relates to the question
- direction: "positive" (supports YES), "negative" (supports NO), or "neutral"
- strength (0.0-1.0): how much this should shift the probability
- key_insight: one sentence on what this evidence tells us

Respond with JSON only:
{{
  "scores": [
    {{
      "evidence_index": 0,
      "source_credibility": 0.85,
      "relevance": 0.9,
      "direction": "positive",
      "strength": 0.6,
      "key_insight": "..."
    }}
  ],
  "overall_evidence_direction": "positive|negative|mixed|neutral",
  "evidence_quality_summary": "brief summary"
}}"""


STRUCTURED_FORECAST_PROMPT = """You are forecasting the following question using the superforecaster methodology.

QUESTION: {question_text}
DOMAIN: {domain}
FORECAST CUTOFF DATE: {cutoff_date}

STEP 1 — BASE RATE:
The historical base rate for {domain} questions of this type is approximately {base_rate:.0%}.
Consider: Is this question easier or harder than typical? Should the base rate be adjusted?

STEP 2 — EVIDENCE ASSESSMENT:
{evidence_summary}

Overall evidence direction: {evidence_direction}
Number of evidence items: {n_evidence}

STEP 3 — EVIDENCE SCORES:
{evidence_scores_text}

STEP 4 — PRODUCE YOUR FORECAST:
Starting from the base rate of {base_rate:.0%}, adjust based on the evidence.
- Strong credible evidence in one direction should shift 5-15 percentage points
- Moderate evidence should shift 2-5 percentage points
- Weak or conflicting evidence should shift 0-2 percentage points
- Never move more than 25 percentage points from base rate without extraordinary evidence

Respond with JSON only:
{{
  "base_rate": {base_rate},
  "adjusted_base_rate": <your adjusted base rate if you think the default is wrong>,
  "evidence_shift": <total shift from evidence, positive = toward YES>,
  "raw_probability": <your probability before calibration>,
  "final_probability": <your final calibrated probability, between 0.03 and 0.97>,
  "confidence": "low|medium|high",
  "rationale": "<2-3 sentences explaining your reasoning>",
  "key_factors": ["factor1", "factor2", "factor3"]
}}"""


DIRECT_FORECAST_PROMPT = """You are a superforecaster. Estimate the probability of the following question resolving YES.

QUESTION: {question_text}
DOMAIN: {domain}
FORECAST CUTOFF DATE: {cutoff_date} (you only know information available before this date)

AVAILABLE EVIDENCE:
{evidence_text}

Think step by step:
1. What is the base rate for questions like this?
2. What does the evidence tell us?
3. How reliable and relevant is the evidence?
4. What is your probability estimate?

Rules:
- Stay calibrated. 70% means it happens 7 times out of 10.
- Avoid extremes unless evidence is overwhelming.
- Keep between 0.03 and 0.97.

Respond with JSON only:
{{
  "probability": <float between 0.03 and 0.97>,
  "confidence": "low|medium|high",
  "base_rate_estimate": <your estimated base rate>,
  "rationale": "<2-3 sentences>",
  "key_factors": ["factor1", "factor2"]
}}"""


class LLMForecaster:
    """LLM-based forecaster with structured and direct modes."""

    def __init__(self, config: LLMConfig | None = None):
        self.config = config or LLMConfig()
        self._client = None
        self._cheap_client = None

    def _get_client(self):
        """Lazily initialize the API client."""
        if self._client is not None:
            return self._client

        if self.config.provider == "anthropic":
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.config.api_key)
            except ImportError:
                raise RuntimeError("pip install anthropic")
        else:
            try:
                import openai
                self._client = openai.OpenAI(api_key=self.config.api_key)
            except ImportError:
                raise RuntimeError("pip install openai")

        return self._client

    def _call_llm(self, prompt: str, model: str | None = None, system: str | None = None) -> tuple[str, int, int]:
        """Call the LLM and return (response_text, tokens_in, tokens_out)."""
        client = self._get_client()
        model = model or self.config.model

        if self.config.provider == "anthropic":
            kwargs: dict[str, Any] = {
                "model": model,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system:
                kwargs["system"] = system

            response = client.messages.create(**kwargs)
            text = response.content[0].text
            tokens_in = response.usage.input_tokens
            tokens_out = response.usage.output_tokens

        else:  # openai
            messages: list[dict[str, str]] = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )
            text = response.choices[0].message.content
            tokens_in = response.usage.prompt_tokens
            tokens_out = response.usage.completion_tokens

        return text, tokens_in, tokens_out

    def _parse_json(self, text: str) -> dict:
        """Extract JSON from LLM response, handling markdown code blocks."""
        text = text.strip()
        # Strip markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last lines (```json and ```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON in the text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            raise ValueError(f"Could not parse JSON from LLM response: {text[:200]}")

    def forecast_structured(
        self,
        question_text: str,
        domain: str,
        evidence: list[dict],
        cutoff_date: str,
        base_rate: float = 0.5,
    ) -> LLMForecastResult:
        """Structured forecast: score evidence with cheap model, synthesize with strong model.

        Pipeline:
        1. Score evidence items (cheap model)
        2. Synthesize forecast from base rate + scored evidence (strong model)
        """
        start = time.monotonic()
        total_tokens_in = 0
        total_tokens_out = 0
        total_cost = 0.0

        # Step 1: Score evidence with cheap model
        evidence_scores: list[dict] = []
        evidence_direction = "neutral"
        evidence_summary = "No evidence available."

        if evidence:
            evidence_text = "\n\n".join(
                f"[{i}] Source: {ev.get('source', 'Unknown')} ({ev.get('source_type', 'unknown')})\n"
                f"    Date: {ev.get('published_at', 'unknown')}\n"
                f"    Title: {ev.get('title', 'untitled')}\n"
                f"    Content: {ev.get('content', '')}"
                for i, ev in enumerate(evidence)
            )

            scoring_prompt = EVIDENCE_SCORING_PROMPT.format(
                question_text=question_text,
                domain=domain,
                cutoff_date=cutoff_date,
                evidence_text=evidence_text,
            )

            try:
                score_response, t_in, t_out = self._call_llm(
                    scoring_prompt,
                    model=self.config.cheap_model,
                    system=SYSTEM_PROMPT_STRUCTURED,
                )
                total_tokens_in += t_in
                total_tokens_out += t_out
                total_cost += estimate_cost(self.config.cheap_model, t_in, t_out)

                score_data = self._parse_json(score_response)
                evidence_scores = score_data.get("scores", [])
                evidence_direction = score_data.get("overall_evidence_direction", "neutral")
                evidence_summary = score_data.get("evidence_quality_summary", "")
            except Exception as e:
                logger.warning(f"Evidence scoring failed: {e}")
                evidence_summary = f"Evidence scoring failed. {len(evidence)} items available but unscored."

        # Step 2: Format evidence scores for the synthesis prompt
        if evidence_scores:
            scores_text = "\n".join(
                f"  [{s.get('evidence_index', i)}] credibility={s.get('source_credibility', 0.5):.1f} "
                f"relevance={s.get('relevance', 0.5):.1f} direction={s.get('direction', 'neutral')} "
                f"strength={s.get('strength', 0.3):.1f} — {s.get('key_insight', 'N/A')}"
                for i, s in enumerate(evidence_scores)
            )
        else:
            scores_text = "  No evidence scores available."

        # Step 3: Synthesize forecast with strong model
        synthesis_prompt = STRUCTURED_FORECAST_PROMPT.format(
            question_text=question_text,
            domain=domain,
            cutoff_date=cutoff_date,
            base_rate=base_rate,
            evidence_summary=evidence_summary or "No summary available.",
            evidence_direction=evidence_direction,
            n_evidence=len(evidence),
            evidence_scores_text=scores_text,
        )

        try:
            synth_response, t_in, t_out = self._call_llm(
                synthesis_prompt,
                model=self.config.model,
                system=SYSTEM_PROMPT_STRUCTURED,
            )
            total_tokens_in += t_in
            total_tokens_out += t_out
            total_cost += estimate_cost(self.config.model, t_in, t_out)

            result = self._parse_json(synth_response)
            probability = float(result.get("final_probability", result.get("raw_probability", 0.5)))
            probability = max(0.03, min(0.97, probability))

        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            probability = base_rate
            result = {"rationale": f"Synthesis failed, falling back to base rate: {e}"}

        elapsed_ms = int((time.monotonic() - start) * 1000)

        return LLMForecastResult(
            predicted_probability=round(probability, 4),
            base_rate=base_rate,
            evidence_summary=evidence_summary,
            rationale=result.get("rationale", ""),
            confidence=result.get("confidence", "medium"),
            model_used=self.config.model,
            mode="structured",
            cost_usd=round(total_cost, 6),
            latency_ms=elapsed_ms,
            evidence_scores=evidence_scores,
            raw_response=str(result),
            tokens_in=total_tokens_in,
            tokens_out=total_tokens_out,
        )

    def forecast_direct(
        self,
        question_text: str,
        domain: str,
        evidence: list[dict],
        cutoff_date: str,
    ) -> LLMForecastResult:
        """Direct forecast: LLM reads everything and outputs probability.

        Simpler but less transparent. Good for comparison.
        """
        start = time.monotonic()

        if evidence:
            evidence_text = "\n\n".join(
                f"- [{ev.get('source', 'Unknown')}] {ev.get('title', '')}: {ev.get('content', '')}"
                for ev in evidence[:15]  # cap at 15 to manage tokens
            )
        else:
            evidence_text = "No specific evidence available. Use your general knowledge up to the cutoff date."

        prompt = DIRECT_FORECAST_PROMPT.format(
            question_text=question_text,
            domain=domain,
            cutoff_date=cutoff_date,
            evidence_text=evidence_text,
        )

        try:
            response_text, tokens_in, tokens_out = self._call_llm(
                prompt,
                model=self.config.model,
                system="You are a superforecaster. Respond with JSON only.",
            )
            cost = estimate_cost(self.config.model, tokens_in, tokens_out)
            result = self._parse_json(response_text)
            probability = float(result.get("probability", 0.5))
            probability = max(0.03, min(0.97, probability))

        except Exception as e:
            logger.error(f"Direct forecast failed: {e}")
            probability = 0.5
            result = {"rationale": f"Failed: {e}"}
            tokens_in, tokens_out, cost = 0, 0, 0.0

        elapsed_ms = int((time.monotonic() - start) * 1000)

        return LLMForecastResult(
            predicted_probability=round(probability, 4),
            base_rate=result.get("base_rate_estimate", 0.5),
            evidence_summary="",
            rationale=result.get("rationale", ""),
            confidence=result.get("confidence", "medium"),
            model_used=self.config.model,
            mode="direct",
            cost_usd=round(cost, 6),
            latency_ms=elapsed_ms,
            evidence_scores=[],
            raw_response=str(result),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )

    def forecast(
        self,
        question_text: str,
        domain: str,
        evidence: list[dict],
        cutoff_date: str,
        base_rate: float = 0.5,
    ) -> LLMForecastResult:
        """Main entry point. Routes to structured or direct based on config."""
        if self.config.mode == "structured":
            return self.forecast_structured(question_text, domain, evidence, cutoff_date, base_rate)
        else:
            return self.forecast_direct(question_text, domain, evidence, cutoff_date)
