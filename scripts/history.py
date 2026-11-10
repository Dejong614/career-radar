"""Observed snapshots and closure events; never manufacture pre-collection history."""
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import subprocess
from matching import background_match, job_kind

ROOT = Path(__file__).resolve().parents[1]


def schema(db):
    db.execute("CREATE TABLE IF NOT EXISTS snapshots(observed_at TEXT PRIMARY KEY, revision TEXT, payload TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS history_imports(revision TEXT PRIMARY KEY)")
    db.commit()


def record_snapshot(db, data, revision):
    schema(db)
    buckets = {scope: {kind: {city: {track: 0 for track in ["traffic", "insurance", "av"]} for city in data["metros"]} for kind in ["job", "intern", "other"]} for scope in ["focused", "core", "all"]}
    for job in data["jobs"]:
        level = background_match(job)["level"]
        kind = job_kind(job)
        kind = "job" if kind == "unspecified" else kind
        for scope in buckets:
            if scope == "focused" and level == "adjacent" or scope == "core" and level != "core":
                continue
            for city in set(job.get("metros", [])) & set(data["metros"]):
                buckets[scope][kind][city][job["track"]] += 1
    generated = data["generated_at"]
    at = datetime.fromisoformat(generated.replace("Z", "+00:00"))
    unhealthy = []
    for source in data["sources"]:
        last = source.get("last_success")
        if source.get("error") or not last or (at-datetime.fromisoformat(last.replace("Z", "+00:00"))).total_seconds() > 36*3600:
            unhealthy.append(source["company"])
    row = {"observed_at": generated, "revision": revision, "counts": buckets,
           "traffic_jobs_collected": data.get("traffic_jobs_collected", False),
           "source_issues": unhealthy, "scope_version": data.get("profile_version", "legacy-title-rules")}
    with db:
        db.execute("INSERT OR IGNORE INTO snapshots VALUES(?,?,?)", (generated, revision, json.dumps(row, ensure_ascii=False, separators=(",", ":"))))


def backfill(db):
    """Recover actual archived JSON observations and DB status transitions."""
    schema(db)
    revisions = subprocess.check_output(["git", "log", "--reverse", "--format=%H", "--", "data/jobs.json"], cwd=ROOT, text=True).splitlines()
    imported = {r[0] for r in db.execute("SELECT revision FROM history_imports")}
    new_indices = [i for i, r in enumerate(revisions) if r not in imported]
    if not new_indices:
        return
    revisions = revisions[max(0, min(new_indices)-1):]
    previous = {}
    for revision in revisions:
        try:
            raw = subprocess.check_output(["git", "show", f"{revision}:data/jobs.json"], cwd=ROOT, stderr=subprocess.DEVNULL)
            data = json.loads(raw)
            record_snapshot(db, data, revision)
            old = sqlite3.connect(":memory:")
            old.row_factory = sqlite3.Row
            old.deserialize(subprocess.check_output(["git", "show", f"{revision}:data/jobs.sqlite"], cwd=ROOT, stderr=subprocess.DEVNULL))
            # Real legacy active -> inactive transitions establish detection time,
            # not the employer's exact closing time.
            rows = old.execute("SELECT id,active,missing_runs,last_seen FROM jobs").fetchall()
            at = data["generated_at"]
            for row in rows:
                prior = previous.get(row["id"])
                if prior and prior["active"] and not row["active"]:
                    upper = prior.get("first_missing") or at
                    with db:
                        db.execute("INSERT OR IGNORE INTO job_events VALUES(?,?,'closed',?,?,'archived_snapshot')", (row["id"], at, row["last_seen"], upper))
                        db.execute("UPDATE jobs SET closed_detected_at=coalesce(closed_detected_at,?),closed_lower_bound=coalesce(closed_lower_bound,?),closed_upper_bound=coalesce(closed_upper_bound,?) WHERE id=? AND active=0", (at, row["last_seen"], upper, row["id"]))
                elif prior and not prior["active"] and row["active"]:
                    db.execute("INSERT OR IGNORE INTO job_events(job_id,occurred_at,event,basis) VALUES(?,?,'reopened','archived_snapshot')", (row["id"], at))
                previous[row["id"]] = {"active": row["active"], "first_missing": (prior or {}).get("first_missing") or at if row["missing_runs"] else None}
            old.close()
            with db:
                db.execute("INSERT OR IGNORE INTO history_imports VALUES(?)", (revision,))
        except (subprocess.CalledProcessError, sqlite3.Error, ValueError, KeyError) as exc:
            print(f"History skipped {revision[:8]}: {type(exc).__name__}", flush=True)
    print(f"History: {db.execute('SELECT count(*) FROM snapshots').fetchone()[0]} real observations.")
    with db:
        for job_id, state in previous.items():
            if state["active"] and state["first_missing"]:
                db.execute("UPDATE jobs SET first_missing_at=coalesce(first_missing_at,?) WHERE id=? AND active=1 AND missing_runs>0", (state["first_missing"], job_id))


def export_history(db):
    schema(db)
    frames = [json.loads(r[0]) for r in db.execute("SELECT payload FROM snapshots ORDER BY observed_at")]
    events = [dict(r) for r in db.execute("SELECT e.job_id,e.occurred_at,e.event,e.lower_bound,e.upper_bound,e.basis,j.payload FROM job_events e LEFT JOIN jobs j ON e.job_id=j.id WHERE e.event IN ('closed','reopened') ORDER BY e.occurred_at DESC LIMIT 200")]
    for event in events:
        job = json.loads(event.pop("payload") or "{}")
        event.update(title=job.get("title", "历史职位（元数据已到保留期）"), company=job.get("company", ""), url=job.get("url", ""), track=job.get("track", ""))
    result = {"schema_version": 1, "frames": frames, "events": events,
              "time_basis": "UTC calendar month; latest actual snapshot within each month",
              "geography_basis": "Metro aliases, not exact office geocodes; multi-city listings count once in each eligible metro",
              "profile_basis": "All history reclassified using title + stored skill names under the same current subject rules"}
    (ROOT / "data/history.json").write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    template = (ROOT / "web/history.template.html")
    if template.exists():
        embedded = json.dumps(result, ensure_ascii=False).replace("<", "\\u003c")
        page = template.read_text(encoding="utf-8").replace("__HISTORY__", embedded)
        page = page.replace("__MAP__", (ROOT / "web/us-map.svg").read_text(encoding="utf-8"))
        (ROOT / "history.html").write_text(page, encoding="utf-8")
    return result


if __name__ == "__main__":
    from collect import open_db
    db = open_db(ROOT / "data/jobs.sqlite")
    backfill(db)
    export_history(db)
    db.close()
