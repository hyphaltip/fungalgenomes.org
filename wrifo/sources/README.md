# Upstream sources

Dumps of the sheets in `WRiFO.xlsx`, one file per sheet, as the workbook held
them — no cleaning, no column renaming, with one exception: **email addresses
are redacted**, here and in `workbook-comments.csv` and `airtable-export.txt`.
Several people pasted an address into a comment or a website cell, and this
directory is committed to a public repository. They are archived
here so the import is reproducible without the binary workbook, and so there is
a record of what the data looked like before `scripts/build_data.py` touched it.

| file | sheet | rows |
| --- | --- | --- |
| `sheet-faculty.csv` | Faculty | 372 |
| `sheet-postdocs.csv` | Postdocs | 23 |
| `sheet-published-resources.csv` | Published resources | 2 |
| `sheet-keywords.csv` | Keywords (research area vocabulary) | 12 |
| `sheet-to-sort.csv` | To sort | 31 |
| `sheet-form-responses.csv` | Form Responses 1 (header only, no responses yet) | 0 |

The `Charts` and `Marginalised scientists` sheets were empty and are not dumped.

`airtable-export.txt` is the tab-separated export of the Airtable base, 346
rows, kept here for the same reason: it is the other half of the seed, and
`data/data_issues.csv` only makes sense alongside it.

With both archived, the seed reproduces `data/people.csv` exactly:

```sh
python3 scripts/build_data.py WRiFO.xlsx airtable_dump.txt   # 384 people
python3 scripts/build_data.py --from-sources                 # 383, workbook only
```

`--from-sources` reads the per-sheet dumps and reproduces the workbook import
exactly; it does not yet re-run the Airtable merge, so it yields one person
fewer. Regenerate the dumps from the workbook with:

```sh
python3 scripts/xlsx_reader.py WRiFO.xlsx sources/
```

`workbook-comments.csv` holds the workbook's 97 threaded comment threads —
years of people asking to be added and maintainers replying, none of which
survives the export to CSV. Regenerate it, and re-triage which requests were
never actioned, with:

```sh
python3 scripts/extract_comments.py WRiFO.xlsx
```

`WRiFO.xlsx` itself is **deliberately not committed** (see `.gitignore`): its
comment threads carry personal email addresses unredacted. Keep it somewhere
private and re-run the two scripts above after editing it.
