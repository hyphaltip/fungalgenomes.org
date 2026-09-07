# Upstream sources

Verbatim dumps of the sheets in `WRiFO.xlsx`, one file per sheet, exactly as
the workbook held them — no cleaning, no column renaming. They are archived
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

Two upstream files are **missing from this directory** and should be restored:

- `WRiFO.xlsx` — the workbook itself. `scripts/build_data.py` reads it directly.
  The sheet dumps above cover its cell contents, but not its threaded comments,
  which contain unprocessed requests to be added to the list.
- `airtable_dump.txt` — a tab-separated export of the Airtable base, 346 rows.
  Its content is already merged into `../data/people.csv`, and the merge
  conflicts it produced are in `../data/data_issues.csv`, but the export itself
  is gone and would need re-exporting to re-run the merge.

Regenerate `sheet-*.csv` from a restored workbook with:

```sh
python3 scripts/xlsx_reader.py WRiFO.xlsx sources/
```
