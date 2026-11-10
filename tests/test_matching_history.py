from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from matching import background_match, job_kind
from history import record_snapshot
from collect import open_db
from careers import summarize
import json


class MatchingHistoryTests(unittest.TestCase):
    def test_relevance_and_unknown_type(self):
        common = {"track": "av", "skills": [{"name": "Statistics"}]}
        self.assertEqual(background_match({**common, "title": "Research Scientist, Safety Evaluation"})["level"], "core")
        self.assertEqual(background_match({"track": "av", "title": "Software Engineer, Perception", "skills": []})["level"], "adjacent")
        self.assertEqual(job_kind({"title": "Traffic Engineer", "employment": "Not specified"}), "unspecified")
        self.assertEqual(job_kind({"title": "PhD Research Intern", "employment": "Full time"}), "intern")
        self.assertEqual(job_kind({"title": "Research Scientist", "employment": "Contract"}), "other")

    def test_historical_coverage_is_not_backfilled_as_zero(self):
        db = open_db(Path(":memory:"))
        self.addCleanup(db.close)
        job = {"title": "Transportation Intern", "track": "traffic", "employment": "Internship", "metros": ["Seattle", "Seattle"], "skills": []}
        snapshot = {"schema_version": 1, "metros": ["Seattle"], "generated_at": "2026-10-31T12:00:00+00:00", "jobs": [job], "sources": []}
        record_snapshot(db, snapshot, "test")
        row = json.loads(db.execute("SELECT payload FROM snapshots").fetchone()[0])
        self.assertFalse(row["traffic_jobs_collected"])
        self.assertEqual(row["counts"]["all"]["intern"]["Seattle"]["traffic"], 1)

    def test_adjacent_and_unknown_people_not_mixed(self):
        rows = [{"cohort": "transport_stats", "field": "traffic", "current_confirmed": True, "role": "Scientist"},
                {"cohort": "transport_stats", "field": "insurance", "current_confirmed": False, "role": "Old role"},
                {"cohort": "adjacent", "field": "av", "current_confirmed": True, "role": "Engineer"}]
        result = summarize(rows)
        self.assertEqual(result["sample_n"], 2)
        self.assertEqual(result["counts"]["unknown"], 1)
        self.assertEqual(result["counts"]["av"], 0)
        self.assertFalse(result["show_percentages"])
