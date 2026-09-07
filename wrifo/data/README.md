# WRIFO data

Flat CSV tables behind <https://fungalgenomes.org/wrifo/>. UTF-8, RFC 4180
quoting, header row, `\n` line endings. Every file here is **generated** —
see [Rebuilding](#rebuilding) before editing.

## `people.csv`

One row per person; the directory itself.

| Column | Notes |
| --- | --- |
| `id` | Stable slug from the name, e.g. `aime-catherine`. Namesakes at different institutions get a `-2` suffix. Use this to reference a person in an issue or a correction. |
| `name` | As recorded, normally `Last, First`. Diacritics preserved. |
| `sort_name` | `name` lowercased and accent-folded. Sort on this, not on `name`. |
| `institution` | Institution name with any trailing country code removed. |
| `country` | ISO 3166-1 alpha-2, or empty where the source never recorded one. |
| `region` | One of: Africa, Asia, Australia/NZ, Europe, North America, South America. See `regions.csv`. |
| `research_area_1`, `research_area_2` | From the vocabulary in `research_areas.csv`. May be empty. |
| `keywords` | Free text, `; ` separated, de-duplicated. |
| `website` | Primary lab or institutional page. Outlook safelinks are unwrapped. |
| `website_2` | Additional pages, `; ` separated, where the source recorded more than one. |
| `career_stage` | From `career_stages.csv`. |
| `roster` | `faculty` or `postdoc` — which sheet of the source workbook the row came from. |
| `notes` | Free text left over from the source, e.g. "No longer research active". |
| `source` | Which upstream sources contained the row: `wrifo-workbook`, `airtable`, or `wrifo-workbook; airtable` for the 345 people in both. |

No email addresses or other contact details are stored. That is deliberate:
this table is published on a public website.

## Vocabulary tables

`research_areas.csv` (`area`, `n_people`), `regions.csv` (`region`,
`n_people`), `career_stages.csv` (`stage`, `description`, `n_people`). The
counts are recomputed on every build and are there for facet labels; treat the
first column as the authoritative list.

## `resources.csv`

Published work on equity and representation in mycology: `title`, `authors`,
`doi`, `url`. Corresponding-author emails present in the source workbook are
deliberately not carried over.

## `unsorted.csv`

Names suggested for the directory that only have `name`, `institution` and a
`notes` fragment. `source` records which sheet they were pasted into. These are
a worklist, not part of the directory — each needs a region, research areas and
a lab link before it becomes a row in `people.csv`.

## `incoming.csv` and `ingest_log.csv`

The form review queue and the record of every response ever seen. Both are
written by `scripts/ingest_form.py` and described under
[the ongoing pipeline](#the-ongoing-pipeline). Neither is published with the
site: the queue holds submissions nobody has looked at yet.

## `data_issues.csv`

What the import could not resolve on its own: `table`, `id`, `field`,
`problem`. Rows that were merged, rows dropped for having no name, free text
found in a controlled field. Worth reading after every rebuild.

## Where the data comes from

`people.csv` **is the source of truth.** It was seeded once from the two files
below and now grows through the form pipeline; nothing regenerates it wholesale
any more.

### The ongoing pipeline

```
Google Form -> responses sheet -> ingest_form.py -> incoming.csv -> you -> people.csv
```

```sh
python3 scripts/ingest_form.py              # fetch new responses into the queue
python3 scripts/ingest_form.py --list       # see what is waiting
vim data/incoming.csv                       # curate: fix the flagged fields, delete junk
python3 scripts/ingest_form.py --promote    # merge the queue into people.csv
```

Responses land in `incoming.csv`, not straight in the directory: the form is a
public write endpoint onto a page of named people, so nothing reaches the site
unreviewed. Each queued row carries a `problems` column naming what is wrong
with it — a region outside the vocabulary, a LinkedIn URL where a lab page
should be, a name that is not `Last, First`. A row that still has problems is
refused by `--promote` and stays in the queue; `--promote --force` overrides.

For an **update** to someone already listed, the queued row is the existing
record with the submission laid over it, so what you review is exactly what
gets written. Keywords accumulate; removing one means editing the queue row.

`ingest_log.csv` records every response ever seen — `response_key`,
`submitted_at`, `name`, when it was queued and promoted, and the outcome
(`added`, `updated`, `rejected`). Re-running the fetch is safe and cannot
duplicate anyone, and a response you deleted from the queue is never re-queued.
Neither `incoming.csv` nor `ingest_log.csv` is published with the site.

Setup and authentication are documented at the top of `scripts/ingest_form.py`.
It needs a spreadsheet id in `WRIFO_SHEET_ID` or `scripts/ingest.config.json`,
and read-only Google credentials from `gcloud auth application-default login`
or a service account. `--from responses.csv` takes a manual export instead and
needs no credentials at all.

The form's email question is deliberately never copied out of the sheet. Use
the sheet to reach a submitter; the directory publishes no contact details.

### The original seed

Two upstream copies of the roster existed and had drifted apart:

- `WRiFO.xlsx` — the original shared workbook, and the one with the most recent
  additions (18 people the Airtable base does not have).
- `airtable_dump.txt` — a tab-separated export of the Airtable base. It carries
  a `country` column, some fresher lab URLs, and one person the workbook lacks.

The build takes their **union**. Where both hold a value for the same field the
workbook wins and the disagreement is written to `data_issues.csv` — about
twenty rows, each one a question only a person can answer. Keyword lists are
unioned rather than contested. Airtable's `Early`/`Mid` career stages are
mapped onto the workbook's `Junior`/`Intermediate` so that one vocabulary is
published.

Neither was authoritative on its own, and neither is upstream any more — new
people arrive through the form. Reconciling the twenty open rows in
`data_issues.csv` is the remaining piece of that history.

## Re-seeding from scratch

`scripts/build_data.py` reconstructs `people.csv` from the upstream sources.
**It overwrites the file and knows nothing about anything added since**, so it
will discard every form submission. It prompts before writing; it is here to
rebuild from zero, not to refresh.

```sh
python3 scripts/build_data.py --from-sources          # from sources/sheet-*.csv
python3 scripts/build_data.py WRiFO.xlsx airtable_dump.txt
```

The `--from-sources` route reads the verbatim dumps in `../sources/` and
reproduces the workbook import exactly, which matters because the workbook
itself is no longer in the tree. It cannot redo the Airtable merge — that
export is gone too — so it yields 383 people rather than 384.

`scripts/xlsx_reader.py` is a small dependency-free `.xlsx` reader used by the
seed; run it alone to dump every sheet verbatim:

```sh
python3 scripts/xlsx_reader.py WRiFO.xlsx sources/
```

## Making corrections

Edit `people.csv` directly — it is the source of truth — then refresh the
tables derived from it:

```sh
python3 -c "import sys; sys.path.insert(0,'scripts'); \
            import wrifo_data as W; W.refresh_derived()"
```

The vocabulary tables carry per-value counts, so they go stale the moment
anyone is added or their research area changes.

Three small correction maps at the top of `build_data.py` (`REGION_FIXES`,
`COUNTRY_FIXES`, `AREA_FIXES`) record deliberate departures from the workbook,
so a re-seed does not reintroduce errors that were already fixed.

## The scripts

| file | what it is |
| --- | --- |
| `scripts/wrifo_data.py` | the schema, vocabularies, validation and shared helpers. Both scripts below import it, so there is one definition of what a row is. |
| `scripts/ingest_form.py` | the ongoing pipeline: form responses in, curated people out. |
| `scripts/build_data.py` | the one-time seed. Retired; run only to rebuild from scratch. |
| `scripts/xlsx_reader.py` | minimal `.xlsx` reader, standard library only. |
