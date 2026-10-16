"""Public employer APIs -> compact SQLite ledger -> static JSON. Python stdlib only."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
import hashlib
import html
import json
from pathlib import Path
import re
import sqlite3
import time
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
TRACKS = {"traffic": "交通工程实习", "insurance": "保险研发", "av": "自动驾驶研究"}
METROS = {
    "Seattle": ["seattle", "bellevue", "redmond", "kirkland", "tacoma", "everett"],
    "Portland": ["portland", "beaverton", "hillsboro"],
    "Los Angeles": ["los angeles", "santa monica", "pasadena", "irvine", "long beach", "orange county", "culver city"],
    "San Francisco": ["san francisco", "san jose", "mountain view", "palo alto", "menlo park", "foster city", "san mateo", "sunnyvale", "oakland", "berkeley", "redwood city", "fremont", "bay area", "walnut creek", "santa clara"],
    "Raleigh": ["raleigh", "durham", "cary", "morrisville", "research triangle"],
    "New York": ["new york", "nyc", "brooklyn", "jersey city", "manhattan", "newark", "hoboken"],
    "Washington DC": ["washington, dc", "washington dc", "washington, d.c.", "district of columbia", "arlington, va", "alexandria, va", "bethesda", "mclean", "reston", "tysons", "rockville", "chevy chase"]
}
SKILL_RULES = json.loads((ROOT / "config/skills.json").read_text(encoding="utf-8"))
INTERN = re.compile(r"\b(?:intern(?:ship)?s?|co[ -]?op)\b", re.I)
RESEARCH = re.compile(r"research|scientist|machine learning|applied science|\br\s*&\s*d\b", re.I)
INSURANCE = re.compile(r"research|scientist|\br\s*&\s*d\b|actuar|(?:risk|predictive|pricing|catastrophe).*model|model.*(?:risk|pricing)|machine learning", re.I)
AV = re.compile(r"research|scientist|machine learning|perception|prediction|motion planning|behavior planning|simulation|robotics|foundation model", re.I)
TRAFFIC = re.compile(r"traffic|transportation|transport planning|transport engineer|mobility", re.I)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def plain(value):
    value = html.unescape(html.unescape(str(value or "")))
    value = re.sub(r"</?(?:p|div|li|h[1-6]|br|section|ul|ol)\b[^>]*>", "\n", value, flags=re.I)
    return re.sub(r"[ \t]+", " ", re.sub(r"<[^>]+>", "", value)).strip()


def request_json(url, payload=None):
    for attempt in range(3):
        try:
            data = json.dumps(payload).encode() if payload is not None else None
            req = Request(url, data=data, headers={"User-Agent": "CareerRadar/1.0 (+public-job-research)", "Accept": "application/json", **({"Content-Type": "application/json"} if data else {})})
            with urlopen(req, timeout=35) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
            time.sleep(min(int(exc.headers.get("Retry-After", "2")) if exc.headers.get("Retry-After", "").isdigit() else 2, 15))
        except (OSError, ValueError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def match_metros(location):
    loc = location.lower()
    # Exclude unambiguous international or wrong-state homonyms.
    if re.search(r"\b(?:canada|germany|india|israel|united kingdom|australia|singapore|toronto|vancouver,? (?:bc|british))\b", loc):
        return []
    metros = [city for city, aliases in METROS.items() if any(re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", loc) for alias in aliases)]
    if re.search(r"portland,?\s*(?:me\b|maine)", loc):
        metros = [m for m in metros if m != "Portland"]
    if re.search(r"\b(?:remote|united states.*remote|us.remote)\b", loc) and not metros:
        # Remote without a country is accepted only on these US employer boards;
        # UI keeps this bucket off by default, and preserves original wording.
        return ["US Remote"] if not re.search(r"europe|emea|apac|latam|uk\b", loc) else []
    return metros


def eligible(source, title, employment=""):
    track = source["track"]
    if track == "traffic":
        if re.search(r"structural|bridge", title, re.I) and not re.search(r"traffic", title, re.I):
            return False
        return bool(TRAFFIC.search(title) and INTERN.search(title + " " + employment))
    if source.get("intern_only") and not INTERN.search(title + " " + employment):
        return False
    if track == "insurance":
        if re.search(r"market(?:ing)? research|user research|ux research|consumer insights", title, re.I):
            return False
        return bool(INSURANCE.search(title))
    return bool(RESEARCH.search(title) or (re.search(r"engineer", title, re.I) and AV.search(title)))


def extract_skills(text):
    result = []
    for skill, patterns in SKILL_RULES.items():
        pattern = re.compile("|".join(patterns), re.I)
        hits = list(pattern.finditer(text))
        if not hits:
            continue
        # Evidence stays attached; matching is a mention signal, not an LLM inference.
        hit = hits[0]
        start = max(text.rfind("\n", 0, hit.start()), text.rfind(". ", 0, hit.start())) + 1
        sentence = text[start:hit.end() + 160].split("\n")[0].strip()
        before = text[max(0, hit.start() - 700):hit.start()].lower()
        headings = list(re.finditer(r"preferred|nice.to.have|bonus|minimum qualifications|required qualifications|requirements|what you.bring|qualifications", before))
        heading = headings[-1].group() if headings else ""
        level = "preferred" if re.search(r"preferred|nice|bonus", heading) else "required" if heading else "mentioned"
        if re.search(r"not required|no .*required", sentence, re.I):
            level = "mentioned"
        result.append({"name": skill, "level": level, "evidence": sentence[:220]})
    return result


def normalize(source, external_id, title, location, description, url, posted_at=None, updated_at=None, employment=""):
    if not eligible(source, title, employment):
        return None
    metros = match_metros(location)
    if not metros or urlparse(url).scheme != "https":
        return None
    text = plain(description)
    return {"id": hashlib.sha256((source["id"] + ":" + str(external_id)).encode()).hexdigest()[:24],
            "source_id": source["id"], "external_id": str(external_id), "company": source["company"], "title": plain(title),
            "track": source["track"], "location": location, "metros": metros, "url": url,
            "posted_at": posted_at, "source_updated_at": updated_at,
            "employment": "Internship" if INTERN.search(title + " " + employment) else employment or "Not specified",
            "skills": extract_skills(text), "description_hash": hashlib.sha256(text.encode()).hexdigest()}


def fetch_source(source):
    provider, board = source["provider"], source["board"]
    records = []
    scanned = 0
    if provider == "greenhouse":
        data = request_json(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true")
        if not isinstance(data.get("jobs"), list):
            raise ValueError("Invalid Greenhouse jobs payload")
        for job in data["jobs"]:
            scanned += 1
            loc = job.get("location", {}).get("name", "")
            records.append(normalize(source, job["id"], job["title"], loc, job.get("content", ""), job["absolute_url"], updated_at=job.get("updated_at")))
    elif provider == "ashby":
        data = request_json(f"https://api.ashbyhq.com/posting-api/job-board/{board}")
        if not isinstance(data.get("jobs"), list):
            raise ValueError("Invalid Ashby jobs payload")
        for job in data["jobs"]:
            scanned += 1
            if job.get("isListed") is False:
                continue
            loc = "; ".join([job.get("location", "")] + [x.get("location", "") for x in job.get("secondaryLocations", [])])
            records.append(normalize(source, job["id"], job["title"], loc, job.get("descriptionPlain", "") or job.get("descriptionHtml", ""), job["jobUrl"], posted_at=job.get("publishedAt"), employment=job.get("employmentType", "")))
    elif provider == "lever":
        offset = 0
        while True:
            data = request_json(f"https://api.lever.co/v0/postings/{board}?" + urlencode({"mode": "json", "limit": 100, "skip": offset}))
            if not isinstance(data, list):
                raise ValueError("Invalid Lever postings payload")
            for job in data:
                scanned += 1
                cat = job.get("categories", {})
                loc = "; ".join(cat.get("allLocations") or [cat.get("location", "")])
                description = job.get("descriptionPlain", "") + "\n" + "\n".join(x.get("text", "") + "\n" + plain(x.get("content", "")) for x in job.get("lists", []))
                # Lever createdAt is posting record creation, not guaranteed publication.
                records.append(normalize(source, job["id"], job["text"], loc, description, job["hostedUrl"], employment=cat.get("commitment", "")))
            if len(data) < 100:
                break
            offset += 100
            if offset > 20000:
                raise ValueError("Lever pagination limit reached; preserve previous snapshot")
    elif provider == "smartrecruiters":
        seen = set()
        for query in source.get("queries", [""]):
            offset = 0
            while True:
                data = request_json(f"https://api.smartrecruiters.com/v1/companies/{board}/postings?" + urlencode({"limit": 100, "offset": offset, "q": query}))
                if not isinstance(data.get("content"), list) or "totalFound" not in data:
                    raise ValueError("Invalid SmartRecruiters postings payload")
                for job in data["content"]:
                    if job["id"] in seen:
                        continue
                    seen.add(job["id"])
                    scanned += 1
                    employment = job.get("typeOfEmployment", {}).get("label", "")
                    loc = ", ".join(str(job.get("location", {}).get(k, "")) for k in ["city", "region", "country"])
                    if not eligible(source, job["name"], employment) or not match_metros(loc):
                        continue
                    detail = request_json(f"https://api.smartrecruiters.com/v1/companies/{board}/postings/{job['id']}")
                    description = "\n".join(x.get("text", "") for x in detail.get("jobAd", {}).get("sections", {}).values())
                    records.append(normalize(source, job["id"], job["name"], loc, description, detail.get("postingUrl") or f"https://jobs.smartrecruiters.com/{board}/{job['id']}", posted_at=detail.get("releasedDate"), employment=employment))
                offset += len(data["content"])
                if offset >= data["totalFound"]:
                    break
                if not data["content"] or offset > 20000:
                    raise ValueError("Incomplete SmartRecruiters pagination")
    elif provider == "workday":
        base = f"https://{source['host']}/wday/cxs/{source['tenant']}/{board}"
        seen = set()
        for query in source.get("queries", [""]):
            offset = 0
            while True:
                data = request_json(base + "/jobs", {"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": query})
                if not isinstance(data.get("jobPostings"), list) or "total" not in data:
                    raise ValueError("Invalid Workday postings payload")
                for job in data["jobPostings"]:
                    path = job["externalPath"]
                    if path in seen:
                        continue
                    seen.add(path)
                    scanned += 1
                    if not eligible(source, job["title"]):
                        continue
                    detail = request_json(base + path)["jobPostingInfo"]
                    loc = "; ".join([detail.get("location", "")] + detail.get("additionalLocations", []))
                    records.append(normalize(source, detail.get("jobReqId", path), job["title"], loc, detail.get("jobDescription", ""), detail.get("externalUrl") or f"https://{source['host']}/en-US/{board}{path}", posted_at=detail.get("startDate"), employment=detail.get("timeType", "")))
                offset += len(data["jobPostings"])
                if offset >= data["total"]:
                    break
                if not data["jobPostings"] or offset > 10000:
                    raise ValueError("Incomplete Workday pagination")
    else:
        raise ValueError(f"Unsupported provider: {provider}")
    # One source is applied atomically only after every page/detail succeeds.
    return [r for r in records if r], scanned


def open_db(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript("""
    CREATE TABLE IF NOT EXISTS jobs (
      id TEXT PRIMARY KEY, source_id TEXT NOT NULL, url TEXT NOT NULL,
      posted_at TEXT, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
      active INTEGER NOT NULL DEFAULT 1, missing_runs INTEGER NOT NULL DEFAULT 0,
      payload TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS jobs_source ON jobs(source_id,active);
    CREATE TABLE IF NOT EXISTS source_status (
      id TEXT PRIMARY KEY, last_success TEXT, last_attempt TEXT, error TEXT,
      scanned INTEGER DEFAULT 0, matched INTEGER DEFAULT 0);
    """)
    return db


def apply_success(db, source_id, jobs, timestamp, scanned):
    with db:
        # Two complete successful misses before closing; errors never retire jobs.
        db.execute("UPDATE jobs SET missing_runs=missing_runs+1 WHERE source_id=?", (source_id,))
        for job in jobs:
            db.execute("""INSERT INTO jobs(id,source_id,url,posted_at,first_seen,last_seen,payload)
              VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
              url=excluded.url,posted_at=coalesce(excluded.posted_at,jobs.posted_at),
              last_seen=excluded.last_seen,active=1,missing_runs=0,payload=excluded.payload""",
                       (job["id"], source_id, job["url"], job["posted_at"], timestamp, timestamp, json.dumps(job, ensure_ascii=False)))
        db.execute("UPDATE jobs SET active=0 WHERE source_id=? AND missing_runs>=2", (source_id,))
        db.execute("""INSERT INTO source_status(id,last_success,last_attempt,error,scanned,matched)
          VALUES(?,?,?,NULL,?,?) ON CONFLICT(id) DO UPDATE SET
          last_success=excluded.last_success,last_attempt=excluded.last_attempt,error=NULL,
          scanned=excluded.scanned,matched=excluded.matched""", (source_id, timestamp, timestamp, scanned, len(jobs)))


def export(db, sources, timestamp, destination):
    jobs, urls = [], set()
    configured = {s["id"]: s for s in sources}
    for row in db.execute("SELECT * FROM jobs WHERE active=1 ORDER BY first_seen DESC,id"):
        if row["source_id"] not in configured:
            continue
        job = json.loads(row["payload"])
        if not eligible(configured[row["source_id"]], job["title"], job["employment"]):
            continue
        if job["url"] in urls:
            continue
        urls.add(job["url"])
        job.update(first_seen=row["first_seen"], last_seen=row["last_seen"], posted_at=row["posted_at"], pending_closure=bool(row["missing_runs"]))
        job.pop("description_hash", None)
        jobs.append(job)
    statuses = {row["id"]: dict(row) for row in db.execute("SELECT * FROM source_status")}
    result = {"schema_version": 1, "generated_at": timestamp, "refresh_hours": 12, "tracks": TRACKS,
              "metros": list(METROS), "jobs": jobs,
              "sources": [{**s, **statuses.get(s["id"], {})} for s in sources]}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    # Also embed a snapshot for direct file:// opening and graceful network fallback.
    template = (ROOT / "web/index.template.html").read_text(encoding="utf-8")
    embedded = json.dumps(result, ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    (ROOT / "index.html").write_text(template.replace("__SNAPSHOT__", embedded), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-only", action="store_true")
    parser.add_argument("--db", type=Path, default=ROOT / "data/jobs.sqlite")
    parser.add_argument("--sources", type=Path, default=ROOT / "config/sources.json")
    args = parser.parse_args()
    sources = json.loads(args.sources.read_text(encoding="utf-8"))
    db = open_db(args.db)
    timestamp, successes = now(), 0
    if not args.export_only:
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(fetch_source, s): s for s in sources}
            for future in as_completed(futures):
                source = futures[future]
                try:
                    jobs, scanned = future.result()
                    apply_success(db, source["id"], jobs, timestamp, scanned)
                    successes += 1
                    print(f"OK {source['id']}: scanned={scanned}, matched={len(jobs)}", flush=True)
                except Exception as exc:
                    message = f"{type(exc).__name__}: {exc}"[:400]
                    with db:
                        db.execute("""INSERT INTO source_status(id,last_attempt,error) VALUES(?,?,?)
                          ON CONFLICT(id) DO UPDATE SET last_attempt=excluded.last_attempt,error=excluded.error""", (source["id"], timestamp, message))
                    print(f"WARN {source['id']}: {message}", flush=True)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=180)).isoformat()
        with db:
            db.execute("DELETE FROM jobs WHERE active=0 AND last_seen<?", (cutoff,))
        db.execute("VACUUM")
    result = export(db, sources, timestamp, ROOT / "data/jobs.json")
    db.close()
    print(f"Exported {len(result['jobs'])} active jobs; {successes}/{len(sources)} sources refreshed.")
    # JSON/status still exported on total failure; workflow persists diagnostics before failing.
    if not args.export_only and not successes:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
