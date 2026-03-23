from __future__ import annotations

DOMAIN_BASE_RATES: dict[str, float] = {
    "macro": 0.55,
    "politics": 0.48,
    "technology": 0.40,
    "business": 0.52,
    "science": 0.45,
    "housing": 0.50,
    "energy": 0.50,
    "health": 0.50,
    "geopolitics": 0.45,
    "other": 0.50,
}

SOURCE_QUALITY: dict[str, float] = {
    "reuters.com": 0.95,
    "apnews.com": 0.95,
    "bls.gov": 0.98,
    "fred.stlouisfed.org": 0.98,
    "census.gov": 0.97,
    "federalreserve.gov": 0.98,
    "nature.com": 0.93,
    "science.org": 0.93,
    "economist.com": 0.88,
    "ft.com": 0.88,
    "bloomberg.com": 0.87,
    "wsj.com": 0.87,
    "nytimes.com": 0.82,
    "washingtonpost.com": 0.82,
    "bbc.com": 0.85,
    "arxiv.org": 0.80,
    "cnbc.com": 0.75,
    "theguardian.com": 0.78,
}

SOURCE_CREDIBILITY: dict[str, float] = {
    "official_data": 0.95,
    "research": 0.85,
    "expert": 0.70,
    "news": 0.55,
    "model_output": 0.60,
}

MODEL_COSTS: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {"input": 0.003, "output": 0.015},
    "claude-haiku-4-5-20251001": {"input": 0.0008, "output": 0.004},
    "claude-opus-4-6": {"input": 0.015, "output": 0.075},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4o": {"input": 0.0025, "output": 0.01},
}

PROB_FLOOR: float = 0.03
PROB_CEILING: float = 0.97

MAX_EVIDENCE_SHIFT: float = 0.3

CALIBRATION_SHRINKAGE: float = 0.05

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "macro": ["gdp", "inflation", "cpi", "unemployment", "interest rate", "fed ", "recession", "economy"],
    "politics": ["election", "president", "congress", "vote", "political", "legislation", "party"],
    "technology": ["ai ", "artificial intelligence", "gpt", "model", "tech", "software", "quantum", "spacex"],
    "science": ["climate", "vaccine", "study", "research", "scientific", "temperature", "species"],
    "business": ["company", "stock", "market cap", "revenue", "ipo", "acquisition", "ceo"],
    "geopolitics": ["war", "military", "nato", "china", "russia", "ukraine", "conflict", "sanctions"],
    "health": ["covid", "pandemic", "disease", "mortality", "health", "fda", "drug"],
    "energy": ["oil", "opec", "energy", "solar", "nuclear", "renewable", "emissions"],
}

POSITIVE_WORDS: set[str] = {
    "increase",
    "rise",
    "grow",
    "exceed",
    "above",
    "higher",
    "gain",
    "surge",
    "approve",
    "pass",
    "succeed",
    "expand",
    "yes",
}

NEGATIVE_WORDS: set[str] = {
    "decrease",
    "fall",
    "decline",
    "below",
    "lower",
    "drop",
    "reduce",
    "fail",
    "reject",
    "contract",
    "no",
    "miss",
}
