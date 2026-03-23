from __future__ import annotations

import json
import os
import time
from pathlib import Path

from forecast.config import DOMAIN_KEYWORDS


def load_seed_questions(data_dir: str = "data/seeds") -> tuple[list[dict], dict[int, list[dict]]]:
    base = Path(data_dir)
    with open(base / "seed_historical_questions.json") as f:
        questions = json.load(f)

    evidence_by_q: dict[int, list[dict]] = {}
    ev_file = base / "seed_historical_evidence.json"
    if ev_file.exists():
        with open(ev_file) as f:
            for ev in json.load(f):
                idx = ev.get("question_index", 0)
                evidence_by_q.setdefault(idx, []).append(ev)

    return questions, evidence_by_q


def load_questions_from_file(path: str) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def filter_questions(
    questions: list[dict],
    evidence_by_q: dict[int, list[dict]],
    domain: str | None = None,
    difficulty: str | None = None,
    limit: int | None = None,
) -> tuple[list[dict], dict[int, list[dict]]]:
    if domain:
        idxs = [i for i, q in enumerate(questions) if q.get("domain") == domain]
        questions = [questions[i] for i in idxs]
        evidence_by_q = {ni: evidence_by_q.get(oi, []) for ni, oi in enumerate(idxs)}

    if difficulty:
        idxs = [i for i, q in enumerate(questions) if q.get("difficulty") == difficulty]
        questions = [questions[i] for i in idxs]
        evidence_by_q = {ni: evidence_by_q.get(oi, []) for ni, oi in enumerate(idxs)}

    if limit:
        questions = questions[:limit]
        evidence_by_q = {k: v for k, v in evidence_by_q.items() if k < limit}

    return questions, evidence_by_q


def classify_domain(text: str) -> str:
    text_lower = text.lower()
    scores = {d: sum(1 for kw in kws if kw in text_lower) for d, kws in DOMAIN_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "other"


def download_forecastbench_questions(date: str = "latest") -> dict:

    if date == "latest":
        sets = _list_forecastbench_sets()
        llm = [s for s in sets["question_sets"] if "llm" in s]
        if not llm:
            raise RuntimeError("No LLM question sets found")
        filename = llm[-1]
    else:
        filename = f"{date}-llm.json"

    return _download_forecastbench_file("question_sets", filename)


def download_forecastbench_resolutions(date: str = "latest") -> dict:
    if date == "latest":
        sets = _list_forecastbench_sets()
        r = sets["resolution_sets"]
        if not r:
            raise RuntimeError("No resolution sets found")
        filename = r[-1]
    else:
        filename = f"{date}_resolution_set.json"

    return _download_forecastbench_file("resolution_sets", filename)


def _list_forecastbench_sets() -> dict:
    import httpx

    base = "https://api.github.com/repos/forecastingresearch/forecastbench-datasets/contents/datasets"
    resp = httpx.get(f"{base}/question_sets", timeout=15)
    q_sets = [item["name"] for item in resp.json() if item["name"].endswith(".json")]
    resp2 = httpx.get(f"{base}/resolution_sets", timeout=15)
    r_sets = [item["name"] for item in resp2.json() if item["name"].endswith(".json")]
    return {"question_sets": sorted(q_sets), "resolution_sets": sorted(r_sets)}


def _download_forecastbench_file(set_type: str, filename: str) -> dict:
    import httpx

    fb_base = "https://raw.githubusercontent.com/forecastingresearch/forecastbench-datasets/main/datasets"
    url = f"{fb_base}/{set_type}/{filename}"
    print(f"Downloading {set_type}: {filename}")
    resp = httpx.get(url, timeout=60, follow_redirects=True)
    resp.raise_for_status()
    text = resp.text
    if text.startswith("version https://git-lfs"):
        api_url = f"https://api.github.com/repos/forecastingresearch/forecastbench-datasets/contents/datasets/{set_type}/{filename}"
        resp2 = httpx.get(api_url, timeout=15)
        dl = resp2.json().get("download_url", "")
        if dl:
            resp = httpx.get(dl, timeout=60, follow_redirects=True)
        else:
            raise RuntimeError(f"Cannot download LFS file: {filename}")
    return resp.json()


def match_resolutions(questions: list[dict], resolutions: list[dict]) -> list[dict]:
    res_by_id = {r["id"]: r for r in resolutions}
    matched = []
    for q in questions:
        r = res_by_id.get(q["id"])
        if r and r.get("resolved") and r.get("resolved_to") is not None:
            q["resolved_value"] = float(r["resolved_to"])
            q["resolution_date"] = r.get("resolution_date", "")
            q["is_resolved"] = True
            matched.append(q)
    return matched


def fetch_metaculus_questions(
    limit: int,
    search: str = "",
    order_by: str = "-activity",
) -> list[dict]:
    import httpx

    metaculus_api = "https://www.metaculus.com/api2"
    params: dict = {
        "limit": min(limit, 100),
        "offset": 0,
        "status": "open",
        "order_by": order_by,
        "forecast_type": "binary",
        "type": "forecast",
        "include_description": "true",
    }
    if search:
        params["search"] = search

    metaculus_token = os.environ.get("METACULUS_API_KEY", "")
    headers: dict[str, str] = {"Accept": "application/json"}
    if metaculus_token:
        headers["Authorization"] = f"Token {metaculus_token}"

    questions: list[dict] = []
    client = httpx.Client(timeout=30.0, headers=headers, follow_redirects=True)

    try:
        while len(questions) < limit:
            params["offset"] = len(questions)
            params["limit"] = min(100, limit - len(questions))
            resp = client.get(f"{metaculus_api}/questions/", params=params)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            if not results:
                break
            for raw in results:
                q = _parse_metaculus_question(raw)
                if q:
                    questions.append(q)
            if not data.get("next"):
                break
            time.sleep(0.3)
    finally:
        client.close()

    return questions[:limit]


def _parse_metaculus_question(raw: dict) -> dict | None:
    try:
        title = raw.get("title", "")
        if not title:
            return None

        possibilities = raw.get("possibilities", {})
        if possibilities.get("type") == "continuous":
            return None

        community_pred = None
        pred_data = raw.get("community_prediction", {})
        if isinstance(pred_data, dict):
            community_pred = pred_data.get("full", {}).get("q2")
        elif isinstance(pred_data, (int, float)):
            community_pred = float(pred_data)

        text = (title + " " + (raw.get("description", "") or "")).lower()
        domain = classify_domain(text)
        description = raw.get("description", "") or ""

        return {
            "metaculus_id": raw.get("id"),
            "question_text": title,
            "description": description[:1000],
            "domain": domain,
            "question_type": "binary",
            "open_date": raw.get("publish_time", ""),
            "close_date": raw.get("close_time", ""),
            "community_prediction": community_pred,
            "num_predictions": raw.get("number_of_predictions", 0),
            "url": f"https://www.metaculus.com/questions/{raw.get('id', 0)}/",
        }
    except Exception:
        return None


def get_forecastbench_leaderboard() -> list[dict]:
    import httpx

    try:
        resp = httpx.get(
            "https://api.github.com/repos/forecastingresearch/forecastbench-datasets/contents/leaderboards/csv",
            timeout=15,
        )
        files = [f for f in resp.json() if f["name"].endswith(".csv")]
        if not files:
            return []
        latest = sorted(files, key=lambda f: f["name"])[-1]
        resp2 = httpx.get(latest["download_url"], timeout=15, follow_redirects=True)
        lines = resp2.text.strip().split("\n")
        if len(lines) < 2:
            return []
        headers = [h.strip().strip('"') for h in lines[0].split(",")]
        return [dict(zip(headers, [v.strip().strip('"') for v in line.split(",")], strict=False)) for line in lines[1:]]
    except Exception:
        return []


def fetch_fred_series(series_id: str, api_key: str = "", limit: int = 30) -> list[dict]:
    import httpx

    key = api_key or os.environ.get("FRED_API_KEY", "")
    if not key:
        return []
    try:
        resp = httpx.get(
            "https://api.stlouisfed.org/fred/series/observations",
            params={
                "series_id": series_id,
                "api_key": key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": limit,
            },
            timeout=10,
        )
        if resp.status_code != 200:
            return []
        obs = resp.json().get("observations", [])
        return [{"date": o["date"], "value": o["value"]} for o in obs if o["value"] != "."]
    except Exception:
        return []
