#!/usr/bin/env python3
"""One-time seed of data/people.csv from the original workbook and Airtable.

    python3 scripts/build_data.py WRiFO.xlsx [airtable_dump.txt]
    python3 scripts/build_data.py --from-sources   # the dumps in sources/

**This script overwrites data/people.csv.** It exists to reconstruct the
directory from the upstream sources it was first assembled from, and it knows
nothing about anything added since. `data/people.csv` is now the source of
truth; new people arrive through scripts/ingest_form.py. Do not run this to
"refresh" the data -- it will discard every form submission.

The two upstream sources agree on almost every row, so the merge fills gaps
rather than replacing anything, and every real disagreement is written to
data_issues.csv for a human to settle.
"""
import argparse, csv, os, re, sys, zipfile
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wrifo_data as W
from wrifo_data import (AREA_FIXES, CAREER_STAGES, COUNTRY_ALIASES, DATA,
                        REGIONS, ROOT, URL_RE, clean_url, norm_keywords,
                        site_key, slugify, sort_key, split_country, split_urls)
from xlsx_reader import read_sheet, shared_strings, date_styles, sheet_map

# Sheet name -> the file in sources/ holding its verbatim dump.
SOURCE_FILES = {
    'Faculty': 'sheet-faculty.csv',
    'Postdocs': 'sheet-postdocs.csv',
    'Published resources': 'sheet-published-resources.csv',
    'Keywords': 'sheet-keywords.csv',
    'To sort': 'sheet-to-sort.csv',
}

# The Airtable base names the same career-stage scale differently. Its labels
# are clearer, but the workbook's are the ones already published, so Airtable is
# mapped onto them rather than the other way round.
AIRTABLE_STAGES = {'Early': 'Junior', 'Mid': 'Intermediate',
                   'Senior': 'Senior', 'Emeritus': 'Emeritus'}

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
    for row in sheets['To sort']:
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
                    'authors': clean_authors(row[1]),
                    'doi': doi,
                    'url': url})
    return out


# --- loading the sheets ------------------------------------------------------

def sheets_from_workbook(path):
    z = zipfile.ZipFile(path)
    ss, ds = shared_strings(z), date_styles(z)
    return {name: read_sheet(z, p, ss, ds) for name, p in sheet_map(z)}


def sheets_from_sources():
    """Read the verbatim per-sheet dumps archived under sources/.

    They are what the workbook held, so the import runs identically from either
    -- which matters, because the workbook itself is no longer in the tree.
    """
    sheets = {}
    for sheet, filename in SOURCE_FILES.items():
        path = os.path.join(ROOT, 'sources', filename)
        if not os.path.exists(path):
            sys.exit('error: %s is missing; cannot seed from sources/' % path)
        with open(path, newline='', encoding='utf-8') as fh:
            sheets[sheet] = [row for row in csv.reader(fh)]
    return sheets


def main(src=None, airtable=None, from_sources=False):
    sheets = sheets_from_sources() if from_sources else sheets_from_workbook(src)

    os.makedirs(DATA, exist_ok=True)
    print('writing %s/' % os.path.relpath(DATA, ROOT))

    people, stray = build_people(sheets)
    if airtable and os.path.exists(airtable):
        people = merge_airtable(people, airtable)
    else:
        print('  note: no Airtable export given; seeding from the workbook only')
    print('  %-22s %4d rows' % ('people.csv', W.write_people(people)))

    resources = build_resources(sheets)
    print('  %-22s %4d rows' % ('resources.csv', W.write_table(
        os.path.join(DATA, 'resources.csv'),
        ['title', 'authors', 'doi', 'url'], resources)))

    unsorted = build_unsorted(sheets, stray)
    print('  %-22s %4d rows' % ('unsorted.csv', W.write_table(
        os.path.join(DATA, 'unsorted.csv'),
        ['name', 'institution', 'notes', 'source'], unsorted)))

    print('  %-22s %4d rows' % ('data_issues.csv', W.write_table(
        os.path.join(DATA, 'data_issues.csv'),
        ['table', 'id', 'field', 'problem'], issues)))

    W.refresh_derived(people, resources, unsorted, issues)
    print('  %-22s %4d people summarised'
          % (os.path.relpath(W.SITE_DATA, os.path.dirname(ROOT)), len(people)))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('workbook', nargs='?', help='WRiFO.xlsx')
    ap.add_argument('airtable', nargs='?', help='tab-separated Airtable export')
    ap.add_argument('--from-sources', action='store_true',
                    help='read the per-sheet dumps in sources/ instead')
    ap.add_argument('--yes', action='store_true',
                    help='skip the confirmation prompt')
    a = ap.parse_args()
    if not a.from_sources and not a.workbook:
        ap.error('give a workbook, or --from-sources')
    if not a.yes:
        print(__doc__.split('\n\n')[1].strip() + '\n')
        if input('Overwrite data/people.csv? [y/N] ').strip().lower() != 'y':
            sys.exit('aborted')
    main(a.workbook,
         a.airtable or os.path.join(ROOT, 'airtable_dump.txt'),
         a.from_sources)
