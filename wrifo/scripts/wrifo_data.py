#!/usr/bin/env python3
"""Schema, vocabularies and shared helpers for the WRIFO tables.

`data/people.csv` is the source of truth for the roster. Two scripts write it
and they must agree on its shape, so the definitions live here:

    scripts/build_data.py   one-time seed from the original workbook + Airtable
    scripts/ingest_form.py  the ongoing pipeline from the Google Form

Standard library only.
"""
import csv, os, re, unicodedata
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
# Summary counts are also emitted as Jekyll site data so the overview page can
# render them without JavaScript. The CSVs under data/ stay the source of truth.
SITE_DATA = os.path.join(os.path.dirname(ROOT), '_data', 'wrifo.yml')

PEOPLE_CSV = os.path.join(DATA, 'people.csv')
INCOMING_CSV = os.path.join(DATA, 'incoming.csv')
INGEST_LOG = os.path.join(DATA, 'ingest_log.csv')

# The column order of data/people.csv.
PEOPLE_FIELDS = ['id', 'name', 'sort_name', 'institution', 'country', 'region',
                 'research_area_1', 'research_area_2', 'keywords', 'website',
                 'website_2', 'career_stage', 'roster', 'notes', 'source']

# The review queue: people.csv, plus what a curator needs to see, plus the key
# that ties the row back to its response in the log. Curating a row may change
# anything about the person -- including the name -- so the key travels with it.
INCOMING_FIELDS = PEOPLE_FIELDS + ['submitted_at', 'action', 'problems',
                                   'response_key']


# --- controlled vocabularies -------------------------------------------------

# Trailing "(XX)" codes seen in the Institution column, mapped to ISO 3166-1
# alpha-2. The workbook was filled in by hand over several years, so the same
# country turns up under several spellings.
COUNTRY_ALIASES = {
    'US': 'US', 'USA': 'US', 'UK': 'GB', 'GB': 'GB',
    'AU': 'AU', 'AUS': 'AU', 'NZ': 'NZ',
    'CA': 'CA', 'CANADA': 'CA', 'BC': 'CA',
    'MX': 'MX', 'MEX': 'MX',
    'ZA': 'ZA', 'RSA': 'ZA',
    'CO': 'CO', 'COL': 'CO',
    'DE': 'DE', 'GE': 'DE',          # "(GE)" is used for Germany, not Georgia
    'ES': 'ES', 'USAL': 'ES',        # Universidad de Salamanca's own acronym
    'IL': 'IL', 'IS': 'IL',          # "(IS)" is Israel here, not Iceland
    'TH': 'TH', 'THAILAND': 'TH',
    'FR': 'FR', 'IT': 'IT', 'NL': 'NL', 'SE': 'SE', 'NO': 'NO', 'DK': 'DK',
    'FI': 'FI', 'AT': 'AT', 'CH': 'CH', 'BE': 'BE', 'PT': 'PT', 'PL': 'PL',
    'SI': 'SI', 'EE': 'EE', 'IE': 'IE', 'CN': 'CN', 'TW': 'TW', 'IN': 'IN',
    'BR': 'BR', 'CR': 'CR', 'PR': 'PR',
}
# Parentheticals that are institutional acronyms rather than country codes.
NOT_A_COUNTRY = {'NIOO-KNAW': 'NL', 'BIOTEC': None, 'CSIR- IICB': 'IN'}

REGIONS = ['Africa', 'Asia', 'Australia/NZ', 'Europe',
           'North America', 'South America']

# The region a country code implies, used only to flag disagreements in
# data_issues.csv -- never to overwrite what the workbook says. IL sits under
# Europe because that is the convention the workbook has always used.
COUNTRY_REGION = {
    'ZA': 'Africa',
    'CN': 'Asia', 'TW': 'Asia', 'IN': 'Asia', 'TH': 'Asia',
    'AU': 'Australia/NZ', 'NZ': 'Australia/NZ',
    'GB': 'Europe', 'FR': 'Europe', 'DE': 'Europe', 'ES': 'Europe',
    'IT': 'Europe', 'NL': 'Europe', 'SE': 'Europe', 'NO': 'Europe',
    'DK': 'Europe', 'FI': 'Europe', 'AT': 'Europe', 'CH': 'Europe',
    'BE': 'Europe', 'PT': 'Europe', 'PL': 'Europe', 'SI': 'Europe',
    'EE': 'Europe', 'IE': 'Europe', 'IL': 'Europe',
    'US': 'North America', 'CA': 'North America', 'MX': 'North America',
    'PR': 'North America', 'CR': 'North America',
    'BR': 'South America', 'CO': 'South America',
}

CAREER_STAGES = OrderedDict([
    ('PhD',          'Doctoral researcher'),
    ('Postdoc',      'Postdoctoral researcher'),
    ('Junior',       'Assistant professor or equivalent'),
    ('Intermediate', 'Associate professor or equivalent'),
    ('Senior',       'Full professor or equivalent'),
    ('Emeritus',     'Emeritus'),
])

# The research area vocabulary, as the workbook's Keywords sheet defined it.
# Fixed on purpose: the directory's facets are only useful while it stays small.
RESEARCH_AREAS = ['Biochemistry', 'Biotechnology', 'Cell biology',
                  'Development', 'Ecology', 'Evolution', 'Genetics/Genomics',
                  'Immunology', 'Medical Mycology', 'Plant Pathology',
                  'Signaling', 'Taxonomy']

# Spellings that drifted from the vocabulary above.
AREA_FIXES = {'Biochemistry/Genomics': 'Biochemistry'}

# --- text and URL helpers ----------------------------------------------------

def slugify(text):
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii').lower()
    return re.sub(r'[^a-z0-9]+', '-', text).strip('-')


def sort_key(name):
    """Fold accents so 'Sanchez' and 'Sánchez' sort together."""
    return unicodedata.normalize('NFKD', name).encode('ascii', 'ignore') \
        .decode('ascii').lower().strip()

INVISIBLE = dict.fromkeys(map(ord, '\u200b\u200c\u200d\u2060\ufeff'), None)


def clean_url(url):
    """Unwrap Outlook safelinks, drop stray trailing punctuation."""
    # Some cells were pasted from rich text and carry zero-width spaces, which
    # make two identical URLs compare unequal.
    url = url.translate(INVISIBLE).strip().rstrip(';,. ')
    m = re.search(r'safelinks\.protection\.outlook\.com/\?url=([^&]+)', url)
    if m:
        from urllib.parse import unquote
        url = unquote(m.group(1))
    if url and not re.match(r'^(https?|mailto):', url):
        url = 'http://' + url
    return url


# A full URL, or a bare hostname like "doeringlab.com" that was typed without a
# scheme. A bare name has to end in a known TLD or carry a path, so that prose
# in the same cell ("E. coli", "etc.") is not mistaken for an address.
TLDS = ('com|org|net|edu|gov|int|info|io|co|ac|eu|uk|de|fr|nl|se|es|it|ca|au|nz'
        '|ch|at|dk|no|fi|be|pt|pl|cz|si|ee|ie|jp|cn|tw|in|br|mx|za|il|kr|ru|tr')
URL_RE = re.compile(
    r'(?:https?://|www\.)[^\s,;]+'
    r'|(?<![\w@.])[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*'
    r'(?:\.(?:%s))(?![a-z])(?:/[^\s,;]*)?' % TLDS,
    re.I)


def split_urls(*fields):
    """Several cells hold two lab URLs; return (primary, secondary, leftover)."""
    urls, leftover = [], []
    for field in fields:
        field = field.translate(INVISIBLE).strip()
        if not field:
            continue
        for m in URL_RE.findall(field):
            u = clean_url(m)
            if u and u not in urls:
                urls.append(u)
        rest = URL_RE.sub('', field).strip(' ,;')
        if rest:
            leftover.append(rest)
    return (urls[0] if urls else '',
            '; '.join(urls[1:]),
            ' '.join(leftover))

def split_country(institution):
    """Pull a trailing country code out of the institution string."""
    inst = institution.strip().rstrip(',')
    m = re.search(r'\s*\(([^()]+)\)\s*$', inst)
    if not m:
        return inst, ''
    token = m.group(1).strip()
    key = token.upper()
    if key in COUNTRY_ALIASES:
        return inst[:m.start()].strip(), COUNTRY_ALIASES[key]
    if token in NOT_A_COUNTRY:
        # Acronym, not a country -- leave it on the institution name.
        return inst, NOT_A_COUNTRY[token] or ''
    if re.fullmatch(r'[A-Z]{2}', token):
        # An unlisted two-letter code, e.g. "(NG)". The aliases above are
        # checked first, so this only ever sees genuine ISO codes.
        return inst[:m.start()].strip(), token
    return inst, ''

def norm_keywords(raw):
    """Keywords arrive semicolon- or comma-separated; emit semicolon-separated."""
    parts = re.split(r'[;,]', raw)
    seen, out = set(), []
    for p in parts:
        p = ' '.join(p.split()).strip(' .')
        if p and p.lower() not in seen:
            seen.add(p.lower())
            out.append(p)
    return '; '.join(out)

def site_key(url):
    """Host and path only, so http/https, www. and a trailing / do not count."""
    return re.sub(r'^https?://(www\.)?', '',
                  url.translate(INVISIBLE).strip()).rstrip('/').lower()


def same_site(a, b):
    return site_key(a) == site_key(b)

# --- reading and writing the tables ------------------------------------------

def yaml_str(value):
    return '"%s"' % str(value).replace('\\', '\\\\').replace('"', '\\"')


def read_table(path, default=()):
    if not os.path.exists(path):
        return list(default)
    with open(path, newline='', encoding='utf-8') as fh:
        return list(csv.DictReader(fh))


def write_table(path, fieldnames, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def read_people():
    return read_table(PEOPLE_CSV)


def write_people(people):
    people.sort(key=lambda p: (p.get('sort_name', ''), p.get('institution', '')))
    return write_table(PEOPLE_CSV, PEOPLE_FIELDS, people)


def blank_person(**kw):
    person = dict.fromkeys(PEOPLE_FIELDS, '')
    person.update(kw)
    return person


def validate(person):
    """Return a list of human-readable problems with one person's fields.

    Used to triage form submissions before they reach the directory; it reports
    rather than corrects, because every one of these needs a judgement call.
    """
    problems = []
    if not person.get('name'):
        problems.append('no name')
    elif ',' not in person['name']:
        problems.append('name is not "Last, First"')
    if not person.get('institution'):
        problems.append('no institution')
    region = person.get('region', '')
    if not region:
        problems.append('no region')
    elif region not in REGIONS:
        problems.append('region %r is not in the vocabulary' % region)
    for n in ('1', '2'):
        area = person.get('research_area_' + n, '')
        if area and area not in RESEARCH_AREAS:
            problems.append('research area %r is not in the vocabulary' % area)
    if not person.get('research_area_1'):
        problems.append('no research area')
    stage = person.get('career_stage', '')
    if not stage:
        problems.append('no career stage')
    elif stage not in CAREER_STAGES:
        problems.append('career stage %r is not in the vocabulary' % stage)
    website = person.get('website', '')
    if not website:
        problems.append('no website')
    elif re.search(r'linkedin\.com|twitter\.com|x\.com/|facebook\.com', website, re.I):
        problems.append('website is a social profile, not a lab page')
    return problems


def refresh_derived(people=None, resources=None, unsorted=None, issues=None):
    """Rewrite every table derived from people.csv, plus the Jekyll site data.

    Call this after anything changes people.csv. The vocabulary tables carry
    counts, so they go stale the moment a person is added.
    """
    people = read_people() if people is None else people
    resources = read_table(os.path.join(DATA, 'resources.csv')) \
        if resources is None else resources
    unsorted = read_table(os.path.join(DATA, 'unsorted.csv')) \
        if unsorted is None else unsorted
    issues = read_table(os.path.join(DATA, 'data_issues.csv')) \
        if issues is None else issues

    area_counts = Counter()
    for p in people:
        for key in ('research_area_1', 'research_area_2'):
            if p.get(key):
                area_counts[p[key]] += 1
    # Anything outside the vocabulary still gets counted, so a value that slipped
    # through curation is visible rather than silently dropped from the facets.
    areas = [{'area': a, 'n_people': area_counts[a]}
             for a in RESEARCH_AREAS + sorted(set(area_counts) - set(RESEARCH_AREAS))]
    write_table(os.path.join(DATA, 'research_areas.csv'),
                ['area', 'n_people'], areas)

    region_counts = Counter(p['region'] for p in people if p.get('region'))
    regions = [{'region': r, 'n_people': region_counts[r]}
               for r in REGIONS + sorted(set(region_counts) - set(REGIONS))]
    write_table(os.path.join(DATA, 'regions.csv'), ['region', 'n_people'], regions)

    stage_counts = Counter(p['career_stage'] for p in people if p.get('career_stage'))
    stages = [{'stage': k, 'description': d, 'n_people': stage_counts[k]}
              for k, d in CAREER_STAGES.items()]
    write_table(os.path.join(DATA, 'career_stages.csv'),
                ['stage', 'description', 'n_people'], stages)

    write_site_data(people, areas, regions, stages, resources, unsorted, issues)
    return {'people': len(people), 'areas': len(areas), 'regions': len(regions)}


def write_site_data(people, areas, regions, stages, resources, unsorted, issues):
    os.makedirs(os.path.dirname(SITE_DATA), exist_ok=True)
    lines = ['# Generated by wrifo/scripts/ -- do not edit by hand.',
             'counts:',
             '  people: %d' % len(people),
             '  faculty: %d' % sum(1 for p in people if p.get('roster') == 'faculty'),
             '  postdocs: %d' % sum(1 for p in people if p.get('roster') == 'postdoc'),
             '  countries: %d' % len({p['country'] for p in people if p.get('country')}),
             '  institutions: %d' % len({p['institution'].lower()
                                         for p in people if p.get('institution')}),
             '  regions: %d' % len({p['region'] for p in people if p.get('region')}),
             '  resources: %d' % len(resources),
             '  unsorted: %d' % len(unsorted),
             '  issues: %d' % len(issues),
             'research_areas:']
    for a in areas:
        lines.append('  - area: %s' % yaml_str(a['area']))
        lines.append('    n_people: %s' % a['n_people'])
    lines.append('regions:')
    for r in regions:
        lines.append('  - region: %s' % yaml_str(r['region']))
        lines.append('    n_people: %s' % r['n_people'])
    lines.append('career_stages:')
    for st in stages:
        lines.append('  - stage: %s' % yaml_str(st['stage']))
        lines.append('    description: %s' % yaml_str(st['description']))
        lines.append('    n_people: %s' % st['n_people'])
    lines.append('resources:')
    for r in resources:
        lines.append('  - title: %s' % yaml_str(r['title']))
        lines.append('    authors: %s' % yaml_str(r['authors']))
        lines.append('    doi: %s' % yaml_str(r['doi']))
        lines.append('    url: %s' % yaml_str(r['url']))
    lines.append('unsorted:')
    for u in unsorted:
        lines.append('  - name: %s' % yaml_str(u['name']))
        lines.append('    institution: %s' % yaml_str(u['institution']))
        lines.append('    notes: %s' % yaml_str(u['notes']))
    with open(SITE_DATA, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')
