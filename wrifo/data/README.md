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

## `data_issues.csv`

What the import could not resolve on its own: `table`, `id`, `field`,
`problem`. Rows that were merged, rows dropped for having no name, free text
found in a controlled field. Worth reading after every rebuild.

## Sources and how they are merged

Two upstream copies of the roster exist and have drifted apart:

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

Neither source is authoritative on its own. Reconciling `data_issues.csv` and
then retiring one of the two is the obvious next piece of work.

## Rebuilding

```sh
cd wrifo
python3 scripts/build_data.py WRiFO.xlsx airtable_dump.txt
```

Standard library only, no dependencies. It rewrites everything in this
directory and regenerates `_data/wrifo.yml`, which is the summary the Jekyll
pages render from. `scripts/xlsx_reader.py` is a small `.xlsx` reader used by
the build; it can also be run on its own to dump every sheet verbatim:

```sh
python3 scripts/xlsx_reader.py WRiFO.xlsx /tmp/sheets
```

### Corrections

While the workbook and the Airtable base are still upstream, fix the data
**there** and rebuild — a hand-edit to a CSV here is overwritten by the next build. The two
exceptions are the small correction maps at the top of `build_data.py`
(`REGION_FIXES`, `COUNTRY_FIXES`, `AREA_FIXES`), which record deliberate
departures from the workbook and survive rebuilds.

Once the roster moves to a repository of its own, `people.csv` becomes the
source of truth, `build_data.py` retires, and nothing about the schema changes.
