import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import collect as c
import employer_sources as e


class EmployerTests(unittest.TestCase):
    def source(self, provider, track='traffic'):
        return dict(id='test', company='Test', provider=provider, track=track, board='public', homepage='https://jobs.example.com/jobs')

    def test_structured_description_controls_and_type(self):
        posting = {'@type':'JobPosting', 'title':'Civil Engineering Intern', 'description':'Required: Python\nVISSIM',
                   'employmentType':'FULL_TIME', 'jobLocation':{'address':{'addressLocality':'Seattle','addressRegion':'WA','addressCountry':'US'}},
                   'datePosted':'2026-11-01', 'validThrough':'2027-11-01'}
        text = '<script type="application/ld+json">' + json.dumps(posting).replace('\\n','\n') + '</script>'
        job = e.from_structured(self.source('icims'), '1', text, 'https://jobs.example.com/1', c.normalize, 'Transportation')
        self.assertEqual(job['kind'], 'intern')
        self.assertEqual(job['discipline'], 'Transportation')
        self.assertEqual(job['posted_at'], '2026-11-01')
        self.assertIsNone(job['application_deadline'])  # indexing expiry != employer deadline
        self.assertIn('Python', [s['name'] for s in job['skills']])

    def test_oracle_incomplete_pagination_cannot_be_success(self):
        source = {**self.source('oracle'), 'host':'jobs.example.com', 'us_location_id':'1', 'queries':['traffic']}
        responses = [{'items':[{'requisitionList':[{'Id':'1','Title':'Traffic Engineer','PrimaryLocationCountry':'US'}], 'TotalJobsCount':2}]},
                     {'items':[{'requisitionList':[], 'TotalJobsCount':2}]}]
        with self.assertRaisesRegex(ValueError, 'Incomplete Oracle'):
            e.fetch_oracle(source, c.normalize, c.eligible, c.match_metros, lambda url: responses.pop(0))

    def test_icims_invisible_next_is_terminal(self):
        text = '<ul><li class="iCIMS_JobCardItem"><div class="left">US-TX-Dallas</div><h3>Traffic Engineer</h3><a href="https://jobs.example.com/jobs/1/x/job">View</a></li></ul><a class="glyph invisible" href="https://jobs.example.com/jobs/search?pr=">Next page of results</a>'
        with patch.object(e, 'read_text', return_value=text) as read:
            jobs, scanned = e.fetch_icims(self.source('icims'), c.normalize, c.eligible, c.match_metros)
        self.assertEqual((jobs, scanned), ([], 1))
        self.assertEqual(read.call_count, 1)

    def test_gm_remote_region_is_not_dc_office(self):
        text = '<source><job><title>Software Engineer, Autonomy Evaluation</title><requisitionid>1</requisitionid><city>Remote</city><state>District of Columbia</state><country>United States</country><url>https://jobs.example.com/1</url><description>Python Statistics</description><jobtype>Full time</jobtype><remotetype>Fully remote</remotetype></job></source>'
        source = {**self.source('gmxml', 'av'), 'feed_url':'https://jobs.example.com/feed'}
        with patch.object(e, 'read_text', return_value=text):
            jobs, _ = e.fetch_gm(source, c.normalize, c.eligible, c.match_metros)
        self.assertEqual(jobs[0]['metros'], ['US Remote'])
        self.assertIn('District of Columbia', jobs[0]['remote_eligibility'])

    def test_didi_matching_detail_is_required(self):
        source = {**self.source('didi','av'), 'api_url':'https://jobs.example.com'}
        responses = [{'success':True, 'result':[{'id':'1','jobTitle':'Research Scientist','address':'San Jose - United States'}]}, {'success':False}]
        with self.assertRaisesRegex(ValueError, 'Missing DiDi'):
            e.fetch_didi(source, c.normalize, c.eligible, c.match_metros, lambda *args: responses.pop(0))


if __name__ == '__main__': unittest.main()
