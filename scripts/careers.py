"""Curated public professional evidence + bounded source health checks.

No login, contact collection, LinkedIn automation, LLM, or inferred degrees.
Automated checks do not promote a page into a newly reviewed career outcome.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import argparse
import html
import json
import re
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def summarize(profiles, cohort="dual"):
    selected = [p for p in profiles if p["cohort"] != "adjacent" and (cohort == "dual" or p["cohort"] == cohort)]
    counts = Counter(p["field"] if p["current_confirmed"] else "unknown" for p in selected)
    roles = Counter(p["role"] for p in selected if p["current_confirmed"])
    return {"sample_n": len(selected), "confirmed_n": sum(p["current_confirmed"] for p in selected),
            "counts": {key: counts[key] for key in ["traffic", "insurance", "av", "other", "unknown"]},
            "roles": roles.most_common(), "show_percentages": len(selected) >= 10}


def build_careers(refresh=False):
    data = json.loads((ROOT / "data/people.json").read_text(encoding="utf-8"))
    health_path = ROOT / "data/people-health.json"
    health = json.loads(health_path.read_text(encoding="utf-8")) if health_path.exists() else {}
    if refresh:
        at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for person in data["profiles"]:
            for source in person["sources"]:
                if source.get("check") is False or "linkedin.com" in source["url"]:
                    continue
                try:
                    req = Request(source["url"], headers={"User-Agent": "CareerRadar/2.0 (public-professional-source-health)"})
                    with urlopen(req, timeout=20) as response:
                        text = html.unescape(re.sub(r"<[^>]+>", " ", response.read(1500000).decode("utf-8", errors="replace")))
                    matched = all(marker.lower() in text.lower() for marker in source.get("markers", []))
                    health[source["url"]] = {"checked_at": at, "status": "reachable_keywords_present" if matched else "needs_review"}
                except Exception as exc:
                    health[source["url"]] = {"checked_at": at, "status": "unavailable", "error": type(exc).__name__}
        health_path.write_text(json.dumps(health, ensure_ascii=False, indent=2), encoding="utf-8")
    data["source_health"] = health
    data["summary"] = summarize(data["profiles"])
    template = ROOT / "web/careers.template.html"
    if template.exists():
        embedded = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
        (ROOT / "careers.html").write_text(template.read_text(encoding="utf-8").replace("__PEOPLE__", embedded), encoding="utf-8")
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    result = build_careers(args.refresh)
    print(json.dumps(result["summary"], ensure_ascii=False))
