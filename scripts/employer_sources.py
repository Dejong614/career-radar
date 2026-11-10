"""Public employer HTML, XML and Oracle feeds. No login or third-party packages."""
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import json
import re
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def text(self):
        return ' '.join(c.text() if isinstance(c, Node) else c for c in self.children)

    def find(self, tag=None, cls=None):
        result = []
        for child in self.children:
            if isinstance(child, Node):
                if (tag is None or child.tag == tag) and (cls is None or cls in child.attrs.get('class', '').split()):
                    result.append(child)
                result.extend(child.find(tag, cls))
        return result


class Document(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                self.stack = self.stack[:i]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def read_text(url):
    req = Request(url, headers={'User-Agent': 'CareerRadar/1.1 (+public-job-research)', 'Accept': 'text/html,application/xml'})
    with urlopen(req, timeout=35) as response:
        return response.read().decode('utf-8-sig')


def structured_jobs(text):
    result = []
    def visit(value):
        if isinstance(value, list):
            for item in value: visit(item)
        elif isinstance(value, dict):
            if value.get('@type') == 'JobPosting': result.append(value)
            if '@graph' in value: visit(value['@graph'])
    for script in Document(text).root.find('script'):
        if script.attrs.get('type') == 'application/ld+json':
            # Some employer JSON-LD embeds literal newlines inside descriptions.
            visit(json.loads(script.text(), strict=False))
    return result


def job_location(job):
    locations = job.get('jobLocation') or []
    if isinstance(locations, dict): locations = [locations]
    parts = []
    for loc in locations:
        address = loc.get('address') or {}
        parts.append(', '.join(str(address.get(k) or '') for k in ['addressLocality', 'addressRegion', 'addressCountry']))
    if job.get('jobLocationType') == 'TELECOMMUTE' and not parts:
        # Never assume unspecified international remote is US remote.
        areas = job.get('applicantLocationRequirements') or []
        if isinstance(areas, dict): areas = [areas]
        parts = ['Remote - ' + str(a.get('name', '')) for a in areas]
    return '; '.join(parts)


def from_structured(source, external_id, text, url, normalize, context=''):
    jobs = structured_jobs(text)
    if len(jobs) != 1:
        raise ValueError('Expected one employer JobPosting; retain prior source data')
    job = jobs[0]
    employment = job.get('employmentType') or ''
    if isinstance(employment, list): employment = ' '.join(employment)
    employment = employment.replace('_', ' ')
    return normalize(source, external_id, job['title'], job_location(job), job.get('description', ''), url,
                     posted_at=job.get('datePosted'), employment=employment, context=context)
    # Schema validThrough is indexing validity, not a confirmed application deadline.


def require_same_site(url, host):
    if urlparse(url).scheme != 'https' or urlparse(url).hostname != host:
        raise ValueError('Unexpected pagination host; retain prior source data')
    return url


def fetch_kittelson(source, normalize, eligible, match_metros):
    page = Document(read_text(source['homepage'])).root
    cards = page.find('article', 'article--detail')
    if not cards: raise ValueError('Kittelson listing structure changed')
    offices_text = read_text(source['offices_url'])
    offices = re.findall(r"title:\s*'([^']+)'", offices_text)
    if not {'Portland', 'Raleigh', 'Oakland'} <= set(offices):
        raise ValueError('Kittelson office list changed')
    records = []
    # Orange is explicitly the California office, not an inferred city homonym.
    def office_names(value):
        return value.replace('Orange', 'Orange, CA').replace('Washington, D.C.', 'Washington, DC')
    for card in cards:
        title = card.find('h3')[0].text().strip()
        if not eligible(source, title): continue
        office = next((n.text().split('Office:', 1)[1].strip() for n in card.find('h4') if 'Office:' in n.text()), '')
        loc = '; '.join(office_names(x) for x in offices if match_metros(office_names(x))) if office == 'All' else office_names(office)
        if not match_metros(loc): continue
        link = next(n.attrs['href'] for n in card.find('a') if '/careers/' in n.attrs.get('href', ''))
        detail = Document(read_text(link)).root.find('article')
        if len(detail) != 1: raise ValueError('Kittelson detail structure changed')
        records.append(normalize(source, card.attrs['id'], title, loc, detail[0].text(), link))
    return [r for r in records if r], len(cards)


def fetch_icims(source, normalize, eligible, match_metros):
    seen, rows = set(), {}
    for query in source.get('queries', ['']):
        url = source['homepage'].rstrip('/') + '/search?' + urlencode({'in_iframe': 1, 'ss': 1, 'searchKeyword': query})
        pages = set()
        while url:
            require_same_site(url, urlparse(source['homepage']).hostname)
            if url in pages or len(pages) >= 100: raise ValueError('Incomplete iCIMS pagination')
            pages.add(url)
            doc = Document(read_text(url)).root
            cards = doc.find('li', 'iCIMS_JobCardItem')
            if not cards and not re.search(r'no (?:jobs|results|positions)', doc.text(), re.I):
                raise ValueError('iCIMS listing structure changed')
            for card in cards:
                title = card.find('h3')[0].text().strip()
                link = next(a.attrs['href'] for a in card.find('a') if '/job' in a.attrs.get('href', ''))
                job_id = re.search(r'/jobs/(\d+)/', link).group(1)
                seen.add(job_id)
                fields = {n.find('dt')[0].text().strip(): n.find('dd')[0].text().strip() for n in card.find('div', 'iCIMS_JobHeaderTag') if n.find('dt') and n.find('dd')}
                context = fields.get('Discipline/Focus', '')
                location = card.find('div', 'left')[0].text().replace('Location : Location', '').strip()
                # iCIMS location is US-WA-Seattle; normalize punctuation, preserve text.
                location = re.sub(r'\bUS-([A-Z]{2})-([^;]+)', r'\2, \1, US', location)
                if eligible(source, title + ' ' + context) and match_metros(location):
                    rows[job_id] = (link, context)
            next_links = [a for a in doc.find('a') if 'Next page of results' in a.text() and not {'disabled', 'invisible'} & set(a.attrs.get('class', '').split())]
            url = next_links[0].attrs['href'] if next_links else None
    def detail(item):
        job_id, (link, context) = item
        return from_structured(source, job_id, read_text(link), link.split('?')[0], normalize, context)
    with ThreadPoolExecutor(max_workers=4) as pool: records = list(pool.map(detail, rows.items()))
    return [r for r in records if r], len(seen)


def fetch_oracle(source, normalize, eligible, match_metros, request_json):
    base = 'https://' + source['host'] + '/hcmRestApi/resources/latest/'
    rows, seen = {}, set()
    for query in source.get('queries', ['']):
        offset = 0
        while True:
            finder = f"findReqs;siteNumber={source['board']},keyword={query},selectedLocationsFacet={source['us_location_id']},limit=100,offset={offset}"
            payload = request_json(base + 'recruitingCEJobRequisitions?' + urlencode({'onlyData': 'true', 'expand': 'requisitionList', 'finder': finder}))
            if len(payload.get('items', [])) != 1: raise ValueError('Invalid Oracle search envelope')
            search = payload['items'][0]
            batch = search.get('requisitionList')
            if not isinstance(batch, list) or 'TotalJobsCount' not in search: raise ValueError('Invalid Oracle job list')
            fresh = set()
            for job in batch:
                fresh.add(job['Id'])
                seen.add(job['Id'])
                if job.get('PrimaryLocationCountry') == 'US' and eligible(source, job['Title']): rows[job['Id']] = job
            if offset and batch and not fresh - page_seen: raise ValueError('Oracle repeated page')
            page_seen = fresh if not offset else page_seen | fresh
            offset += len(batch)
            if offset >= search['TotalJobsCount']: break
            if not batch or offset > 10000: raise ValueError('Incomplete Oracle pagination')
    def detail(item):
        job_id, listing = item
        payload = request_json(base + 'recruitingCEJobRequisitionDetails?' + urlencode({'onlyData': 'true', 'expand': 'all', 'finder': 'ById;Id=' + str(job_id)}))
        if len(payload.get('items', [])) != 1: raise ValueError('Missing Oracle detail')
        job = payload['items'][0]
        location = '; '.join([job.get('PrimaryLocation', '')] + [x.get('Name') or x.get('LocationName') or x.get('SecondaryLocation') or '' for x in job.get('secondaryLocations', [])])
        description = '\n'.join(job.get(k) or '' for k in ['ExternalDescriptionStr', 'ExternalQualificationsStr', 'ExternalResponsibilitiesStr'])
        return normalize(source, job_id, job['Title'], location, description,
                         f"https://{source['host']}/hcmUI/CandidateExperience/en/sites/{source['board']}/job/{job_id}",
                         posted_at=job.get('ExternalPostedStartDate'), employment=job.get('JobSchedule') or '')
    with ThreadPoolExecutor(max_workers=4) as pool: records = list(pool.map(detail, rows.items()))
    return [r for r in records if r], len(seen)


def fetch_progressive(source, normalize, eligible, match_metros):
    url, pages, rows, scanned = source['homepage'], set(), {}, set()
    while url:
        require_same_site(url, 'careers.progressive.com')
        if url in pages or len(pages) >= 100: raise ValueError('Incomplete Progressive pagination')
        pages.add(url)
        doc = Document(read_text(url)).root
        cards = doc.find('li', 'jobs-section__item')
        if not cards: raise ValueError('Progressive job listing structure changed')
        for card in cards:
            links = [a for a in card.find('a') if re.search(r'/jobs/\d+-', a.attrs.get('href', ''))]
            if not links: raise ValueError('Progressive listing missing job URL')
            link = links[0].attrs['href']
            job_id = re.search(r'/jobs/(\d+)-', link).group(1)
            scanned.add(job_id)
            if eligible(source, links[0].text()): rows[job_id] = link
        next_links = [a for a in doc.find('a') if 'next_page' in a.attrs.get('class', '').split()]
        url = urljoin(url, next_links[0].attrs['href']) if next_links else None
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(lambda item: from_structured(source, item[0], read_text(item[1]), item[1], normalize), rows.items()))
    return [r for r in records if r], len(scanned)


def fetch_gm(source, normalize, eligible, match_metros):
    root = ET.fromstring(read_text(source['feed_url']))
    jobs = root.findall('job')
    if root.tag != 'source' or not jobs: raise ValueError('Invalid GM XML feed')
    records = []
    for job in jobs:
        title = job.findtext('title', '')
        if not eligible(source, title): continue
        location = ', '.join(job.findtext(k, '') for k in ['city', 'state', 'country'])
        date = job.findtext('date')
        record = normalize(source, job.findtext('requisitionid'), title, location, job.findtext('description'), job.findtext('url'),
                           posted_at=parsedate_to_datetime(date).isoformat() if date else None, employment=job.findtext('jobtype', ''))
        if record and job.findtext('remotetype', '').lower() == 'fully remote':
            record['metros'] = ['US Remote']
            record['remote_eligibility'] = location
        records.append(record)
    return [r for r in records if r], len(jobs)


def fetch_didi(source, normalize, eligible, match_metros, request_json):
    result = request_json(source['api_url'] + '/icims/searchJobList', {'country': '', 'keyValue': '', 'teamId': '', 'typeId': ''})
    if result.get('success') is not True or not isinstance(result.get('result'), list): raise ValueError('Invalid DiDi job list')
    records = []
    for job in result['result']:
        title, loc = job['jobTitle'], '; '.join([job.get('address') or '', job.get('addLocations') or ''])
        if not eligible(source, title) or not match_metros(loc): continue
        payload = request_json(source['api_url'] + '/icims/searchJob?' + urlencode({'id': job['id']}))
        detail = payload.get('result')
        if payload.get('success') is not True or not isinstance(detail, dict):
            raise ValueError('Missing DiDi job detail; retain prior data')
        description = '\n'.join(detail.get(k) or '' for k in ['teamRoleInstructions', 'teamRoleDetail', 'roleInstructions', 'roleDetail', 'eagerInstructions', 'eagerDetail'])
        if not description.strip(): raise ValueError('Empty DiDi job detail')
        records.append(normalize(source, job['id'], title, loc, description,
                                 source['homepage'].rstrip('/') + '/jobDetail:' + str(job['id']), employment=job.get('jobType') or ''))
    return records, len(result['result'])


def fetch_extra(source, normalize, eligible, match_metros, request_json):
    provider = source['provider']
    if provider == 'oracle': return fetch_oracle(source, normalize, eligible, match_metros, request_json)
    if provider == 'didi': return fetch_didi(source, normalize, eligible, match_metros, request_json)
    return {'kittelson': fetch_kittelson, 'icims': fetch_icims, 'progressive': fetch_progressive, 'gmxml': fetch_gm}[provider](source, normalize, eligible, match_metros)
