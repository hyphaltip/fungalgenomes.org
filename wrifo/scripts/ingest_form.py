#!/usr/bin/env python3
"""Pull Google Form responses into the WRIFO directory, via a review queue.

    python3 scripts/ingest_form.py                 # fetch new responses
    python3 scripts/ingest_form.py --from x.csv    # ... or from a CSV export
    python3 scripts/ingest_form.py --list          # show what is waiting
    python3 scripts/ingest_form.py --promote       # merge the queue into people.csv

Responses land in `data/incoming.csv` with a `problems` column, not straight
into the directory: the form is a public write endpoint onto a page of named
people, so nothing reaches the site until someone has looked at it. Curate that
file -- fix the flagged fields, delete the junk -- then `--promote`. A row that
still has problems is refused and stays in the queue.

`data/ingest_log.csv` records every response ever seen, so re-running is safe
and cannot duplicate anyone.

Configuration
-------------
The spreadsheet id, from its URL
(docs.google.com/spreadsheets/d/<THIS>/edit), goes in the WRIFO_SHEET_ID
environment variable or in scripts/ingest.config.json:

    {"spreadsheet_id": "1a2b3c...", "range": "Form Responses 1"}

Authentication uses Google's application default credentials, so either

    gcloud auth application-default login          # your own account

or a service account, shared read access to the sheet, and

    export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json

Fetching needs `pip install google-api-python-client google-auth`; --from,
--list and --promote are standard library only.
"""
import argparse, csv, datetime, hashlib, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wrifo_data as W

CONFIG = os.path.join(W.HERE, 'ingest.config.json')
SCOPE = 'https://www.googleapis.com/auth/spreadsheets.readonly'

LOG_FIELDS = ['response_key', 'submitted_at', 'name', 'queued_at',
              'promoted_at', 'outcome']

# Form question -> people.csv column. Matched as a substring of the lowercased
# header, so rewording a question does not break the import.
HEADER_MAP = [
    ('timestamp',     'submitted_at'),
    ('name',          'name'),
    ('institution',   'institution'),
    ('region',        'region'),
    ('research area 1', 'research_area_1'),
    ('research area 2', 'research_area_2'),
    ('keyword',       'keywords'),
    ('website',       'website'),
    ('career',        'career_stage'),
]
# Never copied out of the sheet. The form collects an address so you can reach
# the submitter; the directory is public and does not publish contact details.
DROP_HEADERS = ('email', 'e-mail', 'address')


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# --- reading the responses ---------------------------------------------------

def map_headers(header_row):
    """Match each form question to a column, reporting anything unrecognised."""
    mapping, unknown = {}, []
    for i, raw in enumerate(header_row):
        h = raw.strip().lower()
        if not h:
            continue
        if any(d in h for d in DROP_HEADERS):
            continue
        for needle, field in HEADER_MAP:
            if needle in h:
                mapping[i] = field
                break
        else:
            unknown.append(raw.strip())
    return mapping, unknown


def rows_to_responses(rows):
    if not rows:
        return [], []
    mapping, unknown = map_headers(rows[0])
    if 'name' not in mapping.values():
        sys.exit('error: no column in the sheet looks like the name question.\n'
                 '       headers seen: %s' % ', '.join(rows[0]))
    out = []
    for row in rows[1:]:
        rec = {}
        for i, field in mapping.items():
            rec[field] = row[i].strip() if i < len(row) else ''
        if rec.get('name'):
            out.append(rec)
    return out, unknown


def fetch_from_sheet():
    try:
        import google.auth
        from googleapiclient.discovery import build
    except ImportError:
        sys.exit('error: fetching needs the Google client libraries.\n'
                 '       pip install google-api-python-client google-auth\n'
                 '       or export the responses and use --from responses.csv')

    conf = {}
    if os.path.exists(CONFIG):
        with open(CONFIG, encoding='utf-8') as fh:
            conf = json.load(fh)
    sheet_id = os.environ.get('WRIFO_SHEET_ID') or conf.get('spreadsheet_id')
    if not sheet_id:
        sys.exit('error: no spreadsheet id. Set WRIFO_SHEET_ID or write\n'
                 '       %s with {"spreadsheet_id": "..."}' % CONFIG)
    rng = conf.get('range', 'Form Responses 1')

    try:
        creds, _ = google.auth.default(scopes=[SCOPE])
    except Exception as err:
        sys.exit('error: no Google credentials (%s).\n'
                 '       Run: gcloud auth application-default login' % err)
    api = build('sheets', 'v4', credentials=creds, cache_discovery=False)
    values = api.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=rng).execute().get('values', [])
    print('read %d rows from %s!%s' % (len(values), sheet_id[:12] + '…', rng))
    return values


def read_csv_export(path):
    with open(path, newline='', encoding='utf-8-sig') as fh:
        return [row for row in csv.reader(fh)]


# --- the queue ---------------------------------------------------------------

def response_key(rec):
    """Stable id for one submission, so a re-run recognises what it has seen."""
    raw = '%s|%s' % (rec.get('submitted_at', ''), rec.get('name', ''))
    return hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]


def normalise(rec):
    """Turn one raw response into a people.csv row, without deciding anything."""
    name = ' '.join(rec.get('name', '').split())
    institution, country = W.split_country(rec.get('institution', ''))
    website, website_2, leftover = W.split_urls(rec.get('website', ''))
    stage = rec.get('career_stage', '').strip()
    person = W.blank_person(
        id=W.slugify(name),
        name=name,
        sort_name=W.sort_key(name),
        institution=institution,
        country=country,
        region=rec.get('region', '').strip(),
        research_area_1=W.AREA_FIXES.get(rec.get('research_area_1', '').strip(),
                                         rec.get('research_area_1', '').strip()),
        research_area_2=W.AREA_FIXES.get(rec.get('research_area_2', '').strip(),
                                         rec.get('research_area_2', '').strip()),
        keywords=W.norm_keywords(rec.get('keywords', '')),
        website=website,
        website_2=website_2,
        career_stage=stage,
        # A submission's own career stage decides which list it belongs on.
        roster='postdoc' if stage in ('Postdoc', 'PhD') else 'faculty',
        notes=leftover,
        source='form')
    return person


def merge_over(prior, incoming):
    """Overlay a submission on the record already held for that person."""
    merged = dict(prior)
    for field in W.PEOPLE_FIELDS:
        if field in ('id', 'sort_name', 'source'):
            continue
        if incoming.get(field):
            merged[field] = incoming[field]
    # Keywords accumulate; dropping one is a deliberate edit to the queue file.
    merged['keywords'] = W.norm_keywords(
        '; '.join(x for x in (prior.get('keywords'), incoming.get('keywords')) if x))
    merged['source'] = prior.get('source', '')
    return merged


def queue_new(responses):
    log = {r['response_key']: r for r in W.read_table(W.INGEST_LOG)}
    queue = W.read_table(W.INCOMING_CSV)
    existing = {p['id']: p for p in W.read_people()}
    queued = 0

    for rec in responses:
        key = response_key(rec)
        if key in log:
            continue
        person = normalise(rec)
        prior = existing.get(person['id'])
        if prior is not None:
            # Show the curator the record as it would end up, not just the
            # submission: what is reviewed in this file is what gets written.
            person = merge_over(prior, person)
        row = dict(person)
        row['submitted_at'] = rec.get('submitted_at', '')
        row['action'] = 'update' if prior is not None else 'add'
        row['problems'] = '; '.join(W.validate(person))
        row['response_key'] = key
        queue.append(row)
        log[key] = {'response_key': key, 'submitted_at': row['submitted_at'],
                    'name': person['name'], 'queued_at': now(),
                    'promoted_at': '', 'outcome': 'queued'}
        queued += 1

    W.write_table(W.INCOMING_CSV, W.INCOMING_FIELDS, queue)
    W.write_table(W.INGEST_LOG, LOG_FIELDS, list(log.values()))
    return queued, queue


def show_queue(queue):
    if not queue:
        print('the queue is empty')
        return
    width = max(len(r['name']) for r in queue)
    print('%-6s %-*s %-26s %s' % ('action', width, 'name', 'institution', 'problems'))
    for r in queue:
        print('%-6s %-*s %-26s %s' % (r.get('action', ''), width, r['name'],
                                      r['institution'][:26],
                                      r.get('problems') or '-'))


# --- promotion ---------------------------------------------------------------

def promote(force=False):
    queue = W.read_table(W.INCOMING_CSV)
    if not queue:
        print('nothing in the queue')
        return 0
    people = W.read_people()
    by_id = {p['id']: p for p in people}
    log = {r['response_key']: r for r in W.read_table(W.INGEST_LOG)}
    queued_keys = {r.get('response_key') for r in queue}

    kept, added, updated = [], 0, 0
    for row in queue:
        person = W.blank_person(**{k: row.get(k, '') for k in W.PEOPLE_FIELDS})
        # A curator may have edited the name, so the id follows it.
        person['id'] = W.slugify(person['name'])
        person['sort_name'] = W.sort_key(person['name'])
        person['website'] = W.clean_url(person['website'])
        person['keywords'] = W.norm_keywords(person['keywords'])

        problems = W.validate(person)
        if problems and not force:
            row['problems'] = '; '.join(problems)
            kept.append(row)
            continue
        entry = log.get(row.get('response_key'))

        prior = by_id.get(person['id'])
        if prior is None:
            person['source'] = person['source'] or 'form'
            people.append(person)
            by_id[person['id']] = person
            added += 1
        else:
            # The queue row was built as the merged record and then curated, so
            # it replaces the old one outright rather than being merged again.
            person['source'] = prior.get('source', '')
            if 'form' not in person['source']:
                person['source'] = '; '.join(filter(None, [person['source'], 'form']))
            prior.clear()
            prior.update(person)
            updated += 1

        if entry:
            entry['promoted_at'] = now()
            entry['outcome'] = 'added' if prior is None else 'updated'

    # A response that was queued but is in neither the promoted set nor the
    # remaining queue was deleted by the curator: record that, so a later run
    # does not re-queue it and the log stays a true account of every response.
    rejected = 0
    for entry in log.values():
        # Still marked queued, never promoted, and no longer in the queue file:
        # the curator deleted it. Recording that keeps the log a true account of
        # every response, and stops a later run from re-queueing it.
        if (entry['outcome'] == 'queued' and not entry['promoted_at']
                and entry['response_key'] not in queued_keys):
            entry['outcome'] = 'rejected'
            entry['promoted_at'] = now()
            rejected += 1

    W.write_people(people)
    W.write_table(W.INCOMING_CSV, W.INCOMING_FIELDS, kept)
    W.write_table(W.INGEST_LOG, LOG_FIELDS, list(log.values()))
    W.refresh_derived(people)

    print('%d added, %d updated%s -- data/people.csv now has %d people'
          % (added, updated,
             ', %d rejected' % rejected if rejected else '', len(people)))
    if kept:
        print('%d row(s) refused and left in the queue:' % len(kept))
        show_queue(kept)
        print('\nfix data/incoming.csv and run --promote again, or --promote '
              '--force to take them as they are.')
    return added + updated


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--from', dest='csv_path', metavar='FILE',
                    help='read responses from a CSV export instead of the API')
    ap.add_argument('--list', action='store_true', help='show the review queue')
    ap.add_argument('--promote', action='store_true',
                    help='merge the queue into data/people.csv')
    ap.add_argument('--force', action='store_true',
                    help='with --promote, accept rows that still have problems')
    args = ap.parse_args()

    if args.list:
        show_queue(W.read_table(W.INCOMING_CSV))
        return
    if args.promote:
        promote(force=args.force)
        return

    rows = read_csv_export(args.csv_path) if args.csv_path else fetch_from_sheet()
    responses, unknown = rows_to_responses(rows)
    if unknown:
        print('note: ignoring unrecognised form question(s): %s'
              % ', '.join(unknown))
    queued, queue = queue_new(responses)
    if not queued:
        print('no new responses (%d already recorded)' % len(responses))
        if queue:
            print('%d row(s) still waiting in the queue:' % len(queue))
            show_queue(queue)
        return
    print('%d new response(s) -> %s\n'
          % (queued, os.path.relpath(W.INCOMING_CSV, W.ROOT)))
    show_queue(queue)
    print('\ncurate that file, then: python3 scripts/ingest_form.py --promote')


if __name__ == '__main__':
    main()
