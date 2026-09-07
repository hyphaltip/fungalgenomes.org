#!/usr/bin/env python3
"""Stage the WRiFO roster into the flat CSV tables under wrifo/data/.

    python3 scripts/build_data.py WRiFO.xlsx [airtable_dump.txt]

The workbook is the base. A tab-separated Airtable export, if given, is merged
over it: the two sources agree on almost every row, so the merge fills gaps
rather than replacing anything, and every real disagreement is written to
data_issues.csv for a human to settle.

Reads nothing but the standard library so it runs anywhere, including CI.
Everything under data/ is generated -- edit the source workbook (or, once the
roster moves to its own repository, edit people.csv directly and drop this
script) rather than hand-patching the output.
"""
import csv, os, re, sys, unicodedata
from collections import Counter, OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xlsx_reader import read_sheet, shared_strings, date_styles, sheet_map
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
# Summary counts are also emitted as Jekyll site data so the overview page can
# render them without JavaScript. The CSVs under data/ stay the source of truth.
SITE_DATA = os.path.join(os.path.dirname(ROOT), '_data', 'wrifo.yml')

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

# Research areas whose spelling drifted from the Keywords sheet vocabulary.
AREA_FIXES = {'Biochemistry/Genomics': 'Biochemistry'}

# The Airtable base names the same career-stage scale differently. Its labels
# are clearer, but the workbook's are the ones already published, so Airtable is
# mapped onto them rather than the other way round.
AIRTABLE_STAGES = {'Early': 'Junior', 'Mid': 'Intermediate',
                   'Senior': 'Senior', 'Emeritus': 'Emeritus'}

# Region values contradicted by the institution's own country code.
REGION_FIXES = {
    ('Burgess, Treena', 'Europe'): 'Australia/NZ',   # Murdoch University (AU)
}

# Country codes contradicted by the institution's own web domain.
COUNTRY_FIXES = {
    'Ridgway, Hayley':   'NZ',   # Lincoln University, lincoln.ac.nz
    'McDougal, Rebecca': 'NZ',   # Scion Research, scionresearch.com
    'Schmoll, Monika':   'AT',   # Austrian Institute of Technology, "(AU)"
}

issues = []


def note(table, row_id, field, problem):
    issues.append({'table': table, 'id': row_id, 'field': field,
                   'problem': problem})


# --- helpers -----------------------------------------------------------------

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
    return inst, ''


def clean_authors(raw):
    """Strip the superscript affiliation markers that paste in as '1,2,*'."""
    out = []
    for part in ' '.join(raw.split()).split(','):
        part = part.strip().strip('*').strip()
        part = re.sub(r'^\d+\s*', '', part)
        part = re.sub(r'\s*\d+$', '', part).strip()
        if part and not re.fullmatch(r'[\d*]+', part):
            out.append(part)
    return ', '.join(out)


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


def looks_unstructured(row):
    """A pasted 'Name, Institution, topic' line in the Name column only."""
    return bool(row[0].strip()) and not any(c.strip() for c in row[1:])


def parse_unstructured(text):
    text = text.strip().lstrip('-').strip()
    bits = [b.strip() for b in text.split(',')]
    name = bits[0] if bits else text
    institution = bits[1] if len(bits) > 1 else ''
    notes = ', '.join(bits[2:]) if len(bits) > 2 else ''
    return name, institution, notes


# --- table builders ----------------------------------------------------------

def merge_person(prior, institution, region, areas, kw_source, website,
                 website_2, stage):
    """Fold a duplicate row into the record already kept for that person."""
    for field, value in (('institution', institution), ('region', region),
                         ('research_area_1', areas[0]),
                         ('research_area_2', areas[1]),
                         ('website', website), ('website_2', website_2),
                         ('career_stage', stage)):
        if value and not prior[field]:
            prior[field] = value
    prior['keywords'] = norm_keywords('; '.join(
        x for x in (prior['keywords'], kw_source) if x))


def build_people(sheets):
    people, unsorted_rows = [], []
    by_id, seen_ids = {}, Counter()
    for roster, sheet in (('faculty', 'Faculty'), ('postdoc', 'Postdocs')):
        rows = sheets[sheet]
        for lineno, row in enumerate(rows[1:], start=2):
            row = row + [''] * (9 - len(row))
            if not any(c.strip() for c in row):
                continue
            if looks_unstructured(row):
                name, inst, notes = parse_unstructured(row[0])
                unsorted_rows.append({'name': name, 'institution': inst,
                                      'notes': notes, 'source': sheet})
                continue

            name = ' '.join(row[0].split())
            if not name:
                note(roster, '%s!%d' % (sheet, lineno), 'name', 'row has no name')
                continue

            institution, country = split_country(row[1])
            # Fields we deliberately corrected are pinned: a second source
            # repeating the original error should not reopen the question.
            pinned = set()
            if name in COUNTRY_FIXES:
                country = COUNTRY_FIXES[name]
                pinned.add('country')
            region = row[2].strip()
            if (name, region) in REGION_FIXES:
                region = REGION_FIXES[(name, region)]
                pinned.add('region')
            if region and region not in REGIONS:
                note(roster, name, 'region', 'not in the region vocabulary: %r' % region)

            areas = []
            for col in (3, 4):
                a = AREA_FIXES.get(row[col].strip(), row[col].strip())
                # One row has a keyword list pasted into Research Area 2.
                if a and (';' in a or len(a) > 40):
                    note(roster, name, 'research_area_%d' % (col - 2),
                         'free text moved to keywords: %r' % a)
                    a = ''
                areas.append(a)

            kw_source = '; '.join(x for x in [row[5].strip()] +
                                  [row[c].strip() for c in (3, 4)
                                   if row[c].strip() not in areas] if x)
            stage = row[7].strip()
            if stage and stage not in CAREER_STAGES:
                note(roster, name, 'career_stage', 'unknown stage: %r' % stage)

            if country and region and COUNTRY_REGION.get(country, region) != region:
                note(roster, name, 'region',
                     'listed as %s but institution is in %s' % (region, country))

            website, website_2, leftover = split_urls(row[6], row[8])

            pid = slugify(name) or 'person'
            prior = by_id.get(pid)
            if prior is not None:
                # Same name entered twice. If the institution agrees it is one
                # person double-listed, so fold the rows together; otherwise
                # they are namesakes and both records are kept.
                if (not prior['institution'] or not institution or
                        prior['institution'].lower() == institution.lower()):
                    merge_person(prior, institution, region, areas,
                                 kw_source, website, website_2, stage)
                    note(roster, name, 'id', 'listed on two rows; merged')
                    continue
                seen_ids[pid] += 1
                pid = '%s-%d' % (pid, seen_ids[pid] + 1)
                note(roster, name, 'id',
                     'name shared with a different institution; id is %s' % pid)

            record = {
                'id': pid,
                'name': name,
                'sort_name': sort_key(name),
                'institution': institution,
                'country': country,
                'region': region,
                'research_area_1': areas[0],
                'research_area_2': areas[1],
                'keywords': norm_keywords(kw_source),
                'website': website,
                'website_2': website_2,
                'career_stage': stage,
                'roster': roster,
                'notes': ' '.join(leftover.split()),
                'source': 'wrifo-workbook',
                'pinned': pinned,
            }
            by_id[pid] = record
            people.append(record)

    people.sort(key=lambda p: (p['sort_name'], p['institution']))
    return people, unsorted_rows


def site_key(url):
    """Host and path only, so http/https, www. and a trailing / do not count."""
    return re.sub(r'^https?://(www\.)?', '',
                  url.translate(INVISIBLE).strip()).rstrip('/').lower()


def same_site(a, b):
    return site_key(a) == site_key(b)


def merge_airtable(people, path):
    """Overlay a tab-separated Airtable export onto the workbook rows.

    Columns: name, institution, country, region, area 1, area 2, keywords,
    website, career stage.
    """
    by_id = {p['id']: p for p in people}
    added = 0
    with open(path, newline='', encoding='utf-8') as fh:
        for raw in csv.reader(fh, delimiter='\t'):
            if not raw or not raw[0].strip():
                continue
            raw = [c.strip() for c in raw] + [''] * (9 - len(raw))
            name = ' '.join(raw[0].split())
            institution, country = split_country(raw[1])
            country = raw[2].strip().upper() or country
            country = COUNTRY_ALIASES.get(country, country)
            stage = AIRTABLE_STAGES.get(raw[8].strip(), raw[8].strip())
            incoming = {
                'institution': institution,
                'country': country,
                'region': raw[3],
                'research_area_1': AREA_FIXES.get(raw[4], raw[4]),
                'research_area_2': AREA_FIXES.get(raw[5], raw[5]),
                'keywords': norm_keywords(raw[6]),
                'website': raw[7],
                'career_stage': stage,
            }

            pid = slugify(name)
            person = by_id.get(pid)
            if person is None:
                site, site_2, _ = split_urls(incoming['website'])
                person = dict(incoming, id=pid, name=name,
                              sort_name=sort_key(name), website=site,
                              website_2=site_2, roster='faculty', notes='',
                              source='airtable', pinned=set())
                by_id[pid] = person
                people.append(person)
                added += 1
                continue

            for field, value in incoming.items():
                if not value or field in person.get('pinned', ()):
                    continue
                current = person[field]
                if not current:
                    if field == 'website':
                        person['website'], extra, _ = split_urls(value)
                        person['website_2'] = '; '.join(
                            filter(None, [person['website_2'], extra]))
                    else:
                        person[field] = value
                elif field == 'website':
                    # The Airtable cell sometimes holds several URLs; only
                    # disagree when it names a different page entirely.
                    have = {site_key(u) for u in
                            [person['website']] + person['website_2'].split('; ')
                            if u}
                    incoming_urls = [clean_url(m) for m in URL_RE.findall(value)]
                    extra = [u for u in incoming_urls if site_key(u) not in have]
                    if extra and any(site_key(u) in have for u in incoming_urls):
                        person['website_2'] = '; '.join(
                            filter(None, person['website_2'].split('; ') + extra))
                    elif extra:
                        note('people', name, field,
                             'workbook has %s, Airtable has %s'
                             % (current, ', '.join(extra)))
                elif field == 'keywords':
                    # Keyword lists are additive, so union them.
                    person[field] = norm_keywords(current + '; ' + value)
                elif current != value:
                    note('people', name, field,
                         'workbook says %r, Airtable says %r' % (current, value))
            if 'airtable' not in person['source']:
                person['source'] += '; airtable'

    seen = {slugify(' '.join(r[0].split()))
            for r in csv.reader(open(path, newline='', encoding='utf-8'),
                                delimiter='\t') if r and r[0].strip()}
    missing = [p for p in people
               if p['roster'] == 'faculty' and p['id'] not in seen]
    for p in missing:
        note('people', p['name'], 'source', 'in the workbook but not in Airtable')

    people.sort(key=lambda p: (p['sort_name'], p['institution']))
    print('  merged Airtable: %d rows added, %d workbook-only rows flagged'
          % (added, len(missing)))
    return people


def build_unsorted(sheets, extra):
    rows = list(extra)
    for row in sheets['To sort'][0:]:
        if not row or not row[0].strip():
            continue
        name, inst, notes = parse_unstructured(row[0])
        rows.append({'name': name, 'institution': inst, 'notes': notes,
                     'source': 'To sort'})
    rows.sort(key=lambda r: sort_key(r['name']))
    return rows


def build_resources(sheets):
    out = []
    for row in sheets['Published resources'][1:]:
        row = row + [''] * (4 - len(row))
        if not row[0].strip():
            continue
        link = row[2].strip()
        m = re.search(r'(10\.\d{4,9}/\S+)', link)
        doi = m.group(1).rstrip('.') if m else ''
        url = ('https://doi.org/' + doi) if doi else clean_url(link)
        out.append({'title': ' '.join(row[0].split()),
                    # Author strings carry affiliation footnote markers.
                    'authors': clean_authors(row[1]),
                    'doi': doi,
                    'url': url})
    return out


def yaml_str(value):
    return '"%s"' % str(value).replace('\\', '\\\\').replace('"', '\\"')


def write_site_data(people, areas, regions, stages, resources, unsorted, issues):
    os.makedirs(os.path.dirname(SITE_DATA), exist_ok=True)
    lines = ['# Generated by wrifo/scripts/build_data.py -- do not edit by hand.',
             'counts:',
             '  people: %d' % len(people),
             '  faculty: %d' % sum(1 for p in people if p['roster'] == 'faculty'),
             '  postdocs: %d' % sum(1 for p in people if p['roster'] == 'postdoc'),
             '  countries: %d' % len({p['country'] for p in people if p['country']}),
             '  institutions: %d' % len({p['institution'].lower()
                                         for p in people if p['institution']}),
             '  regions: %d' % len({p['region'] for p in people if p['region']}),
             '  resources: %d' % len(resources),
             '  unsorted: %d' % len(unsorted),
             '  issues: %d' % len(issues),
             'research_areas:']
    for a in areas:
        lines.append('  - area: %s' % yaml_str(a['area']))
        lines.append('    n_people: %d' % a['n_people'])
    lines.append('regions:')
    for r in regions:
        lines.append('  - region: %s' % yaml_str(r['region']))
        lines.append('    n_people: %d' % r['n_people'])
    lines.append('career_stages:')
    for st in stages:
        lines.append('  - stage: %s' % yaml_str(st['stage']))
        lines.append('    description: %s' % yaml_str(st['description']))
        lines.append('    n_people: %d' % st['n_people'])
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
    print('  %-22s %4d people summarised'
          % (os.path.relpath(SITE_DATA, os.path.dirname(ROOT)), len(people)))


def write(name, fieldnames, rows):
    path = os.path.join(DATA, name)
    with open(path, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    print('  %-22s %4d rows' % (name, len(rows)))


def main(src, airtable=None):
    z = zipfile.ZipFile(src)
    ss, ds = shared_strings(z), date_styles(z)
    sheets = {name: read_sheet(z, path, ss, ds) for name, path in sheet_map(z)}

    os.makedirs(DATA, exist_ok=True)
    print('writing %s/' % os.path.relpath(DATA, ROOT))

    people, stray = build_people(sheets)
    if airtable and os.path.exists(airtable):
        people = merge_airtable(people, airtable)
    write('people.csv',
          ['id', 'name', 'sort_name', 'institution', 'country', 'region',
           'research_area_1', 'research_area_2', 'keywords', 'website',
           'website_2', 'career_stage', 'roster', 'notes', 'source'], people)

    # Vocabulary tables double as facet counts for the directory page.
    vocab = [r for r in sheets['Keywords'][1:] if r and r[0].strip()]
    area_counts = Counter()
    for p in people:
        for k in ('research_area_1', 'research_area_2'):
            if p[k]:
                area_counts[p[k]] += 1
    areas = [{'area': a, 'n_people': area_counts[a]}
             for a in sorted(set([r[0].strip() for r in vocab]) | set(area_counts))]
    write('research_areas.csv', ['area', 'n_people'], areas)

    region_counts = Counter(p['region'] for p in people if p['region'])
    regions = [{'region': r, 'n_people': region_counts[r]}
               for r in REGIONS + sorted(set(region_counts) - set(REGIONS))]
    write('regions.csv', ['region', 'n_people'], regions)

    stage_counts = Counter(p['career_stage'] for p in people if p['career_stage'])
    stages = [{'stage': k, 'description': d, 'n_people': stage_counts[k]}
              for k, d in CAREER_STAGES.items()]
    write('career_stages.csv', ['stage', 'description', 'n_people'], stages)

    resources = build_resources(sheets)
    write('resources.csv', ['title', 'authors', 'doi', 'url'], resources)

    unsorted = build_unsorted(sheets, stray)
    write('unsorted.csv', ['name', 'institution', 'notes', 'source'], unsorted)

    write('data_issues.csv', ['table', 'id', 'field', 'problem'], issues)

    write_site_data(people, areas, regions, stages, resources, unsorted, issues)


if __name__ == '__main__':
    args = sys.argv[1:]
    main(args[0] if args else os.path.join(ROOT, 'WRiFO.xlsx'),
         args[1] if len(args) > 1 else os.path.join(ROOT, 'airtable_dump.txt'))
