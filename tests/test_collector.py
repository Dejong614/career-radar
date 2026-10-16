import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("collector", Path(__file__).parents[1] / "scripts/collect.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


class CollectorTests(unittest.TestCase):
    def test_scope(self):
        self.assertTrue(c.eligible({"track": "traffic"}, "Transportation Engineering Intern"))
        self.assertFalse(c.eligible({"track": "traffic"}, "Traffic Engineer"))
        self.assertFalse(c.eligible({"track": "traffic"}, "Software Engineering Intern"))
        self.assertFalse(c.eligible({"track": "traffic"}, "Structural Engineering Intern - Bridge & Transportation Structures"))
        self.assertTrue(c.eligible({"track": "insurance"}, "Research & Development Analyst"))
        self.assertFalse(c.eligible({"track": "insurance"}, "Sales Development Representative"))
        self.assertFalse(c.eligible({"track": "insurance"}, "Director Market Research"))
        self.assertFalse(c.eligible({"track": "av"}, "Technical Program Manager, Perception"))
        self.assertTrue(c.eligible({"track": "av"}, "Software Engineer, Perception"))

    def test_metros_and_homonyms(self):
        self.assertEqual(c.match_metros("Portland, Maine"), [])
        self.assertEqual(c.match_metros("Portland, Oregon"), ["Portland"])
        self.assertEqual(c.match_metros("Washington, DC; Bethesda, MD"), ["Washington DC"])
        self.assertEqual(c.match_metros("Washington State"), [])
        self.assertEqual(c.match_metros("Foster City, CA / Seattle, WA"), ["Seattle", "San Francisco"])
        self.assertEqual(c.match_metros("Remote - Canada"), [])

    def test_skill_dedup_and_boundaries(self):
        skills = c.extract_skills("Minimum Qualifications\nPython, SQL, Python, C++ and PyTorch.\nPreferred\nGIS and VISSIM.")
        self.assertEqual(len([s for s in skills if s["name"] == "Python"]), 1)
        self.assertEqual(next(s for s in skills if s["name"] == "GIS / ArcGIS")["level"], "preferred")
        self.assertTrue(any(s["name"] == "C++" for s in skills))
        self.assertFalse(any(s["name"] == "R" for s in c.extract_skills("Research in radar and urban mobility.")))

    def test_two_misses_close_and_reappearance_preserves_first_seen(self):
        temporary_root = Path(__file__).parents[1] / "work"
        temporary_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temporary_root) as tmp:
            db = c.open_db(Path(tmp) / "jobs.sqlite")
            job = c.normalize({"id": "test", "company": "Employer", "track": "traffic"}, "123", "Traffic Intern", "Seattle, WA", "Python required", "https://example.com/jobs/123")
            c.apply_success(db, "test", [job], "2026-01-01T00:00:00+00:00", 1)
            # Failed sources do not call apply_success, so they cannot close anything.
            c.apply_success(db, "test", [], "2026-01-01T12:00:00+00:00", 0)
            self.assertEqual(db.execute("SELECT active FROM jobs").fetchone()[0], 1)
            c.apply_success(db, "test", [], "2026-01-02T00:00:00+00:00", 0)
            self.assertEqual(db.execute("SELECT active FROM jobs").fetchone()[0], 0)
            c.apply_success(db, "test", [job], "2026-01-03T00:00:00+00:00", 1)
            row = db.execute("SELECT active,first_seen,last_seen FROM jobs").fetchone()
            self.assertEqual(row[0], 1)
            self.assertEqual(row[1], "2026-01-01T00:00:00+00:00")
            self.assertEqual(row[2], "2026-01-03T00:00:00+00:00")
            db.close()


if __name__ == "__main__":
    unittest.main()
