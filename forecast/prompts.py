from __future__ import annotations

SYSTEM_PROMPT = """You are a superforecaster. You estimate probabilities with extreme care and discipline.

Your methodology:
1. Start from BASE RATES — what usually happens in similar situations
2. Evaluate each piece of EVIDENCE for credibility, relevance, and directional impact
3. UPDATE incrementally — strong evidence shifts more, weak evidence shifts less
4. Stay CALIBRATED — when you say 70%, it should happen ~70% of the time
5. Avoid EXTREMES unless evidence is overwhelming (stay between 0.05 and 0.95)

You must respond with valid JSON only. No other text."""

EVIDENCE_SCORING_PROMPT = """Score these evidence items for this forecasting question.

QUESTION: {question}
DOMAIN: {domain}
CUTOFF DATE: {cutoff} (only information available before this date)

EVIDENCE:
{evidence}

For each item, score:
- source_credibility (0-1)
- relevance (0-1)
- direction: "positive" (YES), "negative" (NO), or "neutral"
- strength (0-1): how much this should shift probability

Respond with JSON:
{{"scores": [{{"idx": 0, "credibility": 0.8, "relevance": 0.7, "direction": "positive", "strength": 0.5, "insight": "..."}}], "overall_direction": "positive|negative|mixed|neutral"}}"""

STRUCTURED_FORECAST_PROMPT = """Forecast this question using the superforecaster method.

QUESTION: {question}
DOMAIN: {domain}
CUTOFF DATE: {cutoff}

BASE RATE: The historical base rate for {domain} questions like this is ~{base_rate:.0%}.

EVIDENCE SCORES:
{scores}

Overall evidence direction: {direction}

Now produce your forecast:
- Start from base rate {base_rate:.0%}
- Adjust based on evidence (strong+credible = 5-15pp shift, moderate = 2-5pp, weak = 0-2pp)
- Never shift more than 30pp from base rate without extraordinary evidence

Respond with JSON:
{{"probability": <float 0.05-0.95>, "confidence": "low|medium|high", "rationale": "<2 sentences>", "base_rate_adjustment": "<why you adjusted the base rate, if at all>"}}"""

DIRECT_FORECAST_PROMPT = """Estimate the probability this question resolves YES.

QUESTION: {question}
DOMAIN: {domain}
CUTOFF DATE: {cutoff} (only use information available before this date)

EVIDENCE:
{evidence}

Think step by step:
1. What's the base rate for questions like this?
2. What does the evidence say?
3. How reliable is the evidence?

Respond with JSON:
{{"probability": <float 0.05-0.95>, "confidence": "low|medium|high", "rationale": "<2 sentences>"}}"""

QUERY_DECOMPOSITION_PROMPT = """You are a research assistant helping a forecaster find evidence.

FORECASTING QUESTION: {question}
DOMAIN: {domain}
INFORMATION CUTOFF DATE: {cutoff_date}

Generate 3-5 specific, targeted web search queries that would find the most decision-relevant evidence for forecasting this question. Focus on:

1. RECENT DATA: Search for the latest concrete data points, statistics, or measurements directly related to the question (e.g. specific price levels, official statistics, poll numbers)
2. EXPERT ANALYSIS: Search for expert commentary or analysis about the likelihood of this outcome
3. PRECEDENT/CONTEXT: Search for recent developments, announcements, or decisions that bear on this question
4. CONTRARY EVIDENCE: One query specifically looking for reasons the expected outcome might NOT happen

Rules:
- Queries should be short, factual search queries (not full sentences)
- Include specific names, dates, numbers where possible
- Target queries to find information published BEFORE {cutoff_date}
- Do NOT search for the resolution/answer directly

Respond with JSON only:
{{"queries": ["query 1", "query 2", "query 3", "query 4"]}}"""

LIVE_FORECAST_PROMPT = """Forecast this question. It is currently OPEN and UNRESOLVED.

QUESTION: {question}
DOMAIN: {domain}
CLOSES: {close_date}

DESCRIPTION / RESOLUTION CRITERIA:
{description}

Today's date: {today}
Days until close: {days_left}

{community_info}

Think carefully:
1. What is the base rate for questions like this?
2. What do you know about the current state of this topic (up to your knowledge cutoff)?
3. How much time remains? Could things change?
4. Stay calibrated — avoid overconfidence.

Respond with JSON:
{{"probability": <float 0.05-0.95>, "confidence": "low|medium|high", "base_rate_estimate": <float>, "rationale": "<2-3 sentences explaining your reasoning>", "key_factors": ["factor1", "factor2"]}}"""

LIVE_STRUCTURED_SCORE_PROMPT = """Score the relevance and implications of the following context for this forecasting question.

QUESTION: {question}
DOMAIN: {domain}
CLOSES: {close_date}

CONTEXT (from question description):
{description}

Evaluate:
- What base rate applies to questions like this?
- What key factors will determine the outcome?
- What direction does current evidence point?
- How uncertain is the outcome?

Respond with JSON:
{{"base_rate": <float 0.3-0.7>, "key_factors": [{{"factor": "...", "direction": "positive|negative|neutral", "strength": <0-1>}}], "overall_direction": "positive|negative|mixed|neutral", "uncertainty": "low|medium|high"}}"""

LIVE_STRUCTURED_SYNTH_PROMPT = """You are synthesizing a forecast using the superforecaster method.

QUESTION: {question}
DOMAIN: {domain}
CLOSES: {close_date}
DAYS LEFT: {days_left}

ANALYSIS:
- Base rate: {base_rate:.0%}
- Key factors: {factors}
- Overall direction: {direction}
- Uncertainty: {uncertainty}

{community_info}

Starting from base rate {base_rate:.0%}, adjust based on the analysis.
Strong factors shift 5-15pp, moderate 2-5pp, weak 0-2pp.
Never shift more than 30pp without extraordinary reason.

Respond with JSON:
{{"probability": <float 0.05-0.95>, "confidence": "low|medium|high", "rationale": "<2-3 sentences>"}}"""

FORECASTBENCH_PROMPT = """Forecast this question from ForecastBench.

QUESTION: {question}
BACKGROUND: {background}
RESOLUTION CRITERIA: {criteria}
RESOLUTION DATE(S): {res_dates}
SOURCE: {source}
FREEZE VALUE: {freeze_val}

{data_section}

{evidence_section}

Produce your forecast. Consider the freeze value (baseline at question creation) and any data provided.

Respond with JSON:
{{"probability": <float 0.05-0.95>, "confidence": "low|medium|high", "rationale": "<2 sentences>"}}"""

JUDGE_LEAK_FILTER_PROMPT = """You are a temporal information filter for a forecasting system.

FORECASTING QUESTION: {question}
INFORMATION CUTOFF DATE: {cutoff_date}

Your job: review {n_items} non-news evidence items (statistics pages, Wikipedia, historical data, research) and detect any information that reveals the OUTCOME of the forecasting question after the cutoff date.

KEEP: base rates, historical patterns, methodology descriptions, pre-cutoff statistics, background context
REMOVE: post-cutoff results, resolution of the question, final outcomes, "as of [post-cutoff date]" data

For each item, respond with one of:
- "pass" — no leakage detected, keep as-is
- "redact" — contains useful context BUT also has leaking info. Provide cleaned_content with the leaking sentences/data removed.
- "block" — the item exists primarily to report the outcome. Remove entirely.

EVIDENCE TO REVIEW:
{evidence}

Respond with JSON:
{{"items": [{{"idx": 0, "verdict": "pass|redact|block", "cleaned_content": "...(only if redact)...", "reason": "brief explanation"}}]}}"""

FRED_FORECAST_PROMPT = """Forecast this FRED economic data question.

QUESTION: {question}

FREEZE VALUE (baseline at question creation): {freeze_val}
LATEST VALUE: {latest_val} (as of {latest_date})
CHANGE FROM FREEZE: {change} ({pct_change})
RECENT TREND: {trend}
RECENT VALUES: {recent_vals}
VOLATILITY (coefficient of variation): {cv}

RESOLUTION CRITERIA: {criteria}
RESOLUTION DATE(S): {res_dates}

The question asks whether this metric will have increased/decreased by the resolution date.
Current data shows the metric has moved {direction} from {freeze_val} to {latest_val}.

Given the current level, trend, and volatility, estimate the probability this resolves YES.

Respond with JSON:
{{"probability": <float 0.05-0.95>, "confidence": "low|medium|high", "rationale": "<2 sentences>"}}"""
