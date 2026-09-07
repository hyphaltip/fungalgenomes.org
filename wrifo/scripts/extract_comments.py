#!/usr/bin/env python3
"""Archive the workbook's threaded comments and flag the unfinished ones.

    python3 scripts/extract_comments.py WRiFO.xlsx

Years of correspondence live in those comments -- people asking to be added,
maintainers replying, corrections nobody applied. None of it survives the
export to CSV, so this writes it to sources/workbook-comments.csv, and then
does the one check worth automating: for a comment that reads like a request to
be added, is that person in data/people.csv today?

Name matching is deliberately loose and deliberately not authoritative. It
narrows 94 threads down to the handful worth reading; it does not decide
anything.
"""
import csv, os, re, sys, zipfile
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wrifo_data as W
from xlsx_reader import read_sheet, shared_strings, date_styles, sheet_map

TC = '{http://schemas.microsoft.com/office/spreadsheetml/2018/threadedcomments}'
RELS = '{http://schemas.openxmlformats.org/package/2006/relationships}'
OUT = os.path.join(W.ROOT, 'sources', 'workbook-comments.csv')

# Phrasings that mark a comment as somebody asking to join the list.
REQUEST = re.compile(
    r'\b(add me|add her|can you add|could you add|would like to be added|'
    r'please add|i would like to add|like to be included|missing from)\b', re.I)

# A candidate personal name: two capitalised words on one line, as either
# "Forename Surname" or "Surname, Forename".
NAME = re.compile(r"\b([A-Z][a-z'-]{1,19})(,?)\s+([A-Z][a-z'-]{1,19})\b")
# Words that start or end a capitalised pair without it being anyone's name.
# These comments are half prose, half form-field labels, so both leak in.
NOT_A_NAME = {
    'hi', 'hello', 'dear', 'thanks', 'thank', 'please', 'best', 'kind',
    'regards', 'email', 'e-mail', 'name', 'institution', 'country', 'region',
    'research', 'keywords', 'keyword', 'area', 'areas', 'current', 'position',
    'stage', 'career', 'website', 'lab', 'university', 'univ', 'institute',
    'college', 'school', 'department', 'center', 'centre', 'national',
    'medical', 'mycology', 'ecology', 'evolution', 'genomics', 'genetics',
    'pathology', 'biology', 'immunology', 'biochemistry', 'plant', 'fungal',
    'marine', 'molecular', 'microbial', 'postdoc', 'professor', 'dr', 'prof',
    'intermediate', 'senior', 'junior', 'faculty', 'she', 'her', 'his', 'they',
    'the', 'and', 'for', 'you', 'i', 'we', 'it', 'this', 'that', 'is', 'are',
    'add', 'added', 'list', 'sheet', 'page', 'link', 'info', 'information',
}


def place_words(people):
    """Words that appear in institution names, so "Guelph, Canada" is not read
    as a person. The directory's own institutions are a better stoplist than
    any list of place names I could write out."""
    words = set()
    for p in people:
        words.update(re.findall(r"[A-Za-z'-]{2,}", p.get('institution', '').lower()))
    words.update(w.lower() for r in W.REGIONS for w in re.split(r'[/\s]', r))
    return words


def candidate_names(text, places=frozenset()):
    """Personal names a comment mentions, as best a regex can tell."""
    found = set()
    for line in text.split('\n'):
        for first, comma, second in NAME.findall(line):
            if first.lower() in NOT_A_NAME or second.lower() in NOT_A_NAME:
                continue
            if first.lower() in places or second.lower() in places:
                continue
            # "Surname, Forename" is already in the directory's order; a bare
            # "Forename Surname" has to be tried both ways round.
            found.add('%s, %s' % (first, second) if comma
                      else '%s, %s' % (second, first))
    return found


def in_directory(name, ids, sort_names):
    surname, forename = [p.strip() for p in name.split(',', 1)]
    for variant in ('%s, %s' % (surname, forename), '%s, %s' % (forename, surname)):
        if W.slugify(variant) in ids or W.sort_key(variant) in sort_names:
            return True
    # The directory often carries a middle name or a nickname in parentheses,
    # so fall back to matching on the surname plus the forename's first letter.
    prefix = W.sort_key('%s, %s' % (surname, forename[:1]))
    return any(s.startswith(prefix) for s in sort_names)


EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')


def comment_text(node):
    body = '\n'.join(t.text or '' for t in node.iter()
                     if t.tag == TC + 'text').strip()
    # People pasted their email address into these comments. The archive goes
    # into a public repository, so the addresses do not: the workbook still has
    # them if you need to reply to somebody.
    return EMAIL.sub('[email redacted]', body)


def sheet_for_comment_part(z, part):
    """Map threadedComment<N>.xml back to the worksheet that references it."""
    names = {}
    for sheet_name, sheet_path in sheet_map(z):
        rel = os.path.join(os.path.dirname(sheet_path), '_rels',
                           os.path.basename(sheet_path) + '.rels')
        if rel not in z.namelist():
            continue
        for r in ET.fromstring(z.read(rel)).findall(RELS + 'Relationship'):
            target = os.path.normpath(os.path.join(
                os.path.dirname(sheet_path), r.get('Target')))
            names[target] = sheet_name
    return names.get(os.path.normpath(part))


def row_label(sheets, sheet_name, ref):
    """The name in column A of the row a comment is anchored to."""
    m = re.match(r'([A-Z]+)(\d+)$', ref or '')
    rows = sheets.get(sheet_name) or []
    if not m:
        return ''
    i = int(m.group(2)) - 1
    return rows[i][0].strip() if 0 <= i < len(rows) and rows[i] else ''


def main(src):
    z = zipfile.ZipFile(src)
    ss, ds = shared_strings(z), date_styles(z)
    sheets = {n: read_sheet(z, p, ss, ds) for n, p in sheet_map(z)}
    people = W.read_people()
    known = {p['id'] for p in people}
    listed_names = {W.sort_key(p['name']) for p in people}
    places = place_words(people)

    threads, out = {}, []
    for part in sorted(n for n in z.namelist() if 'threadedComments/' in n):
        sheet = sheet_for_comment_part(z, part) or part
        for node in ET.fromstring(z.read(part)):
            threads.setdefault(node.get('parentId') or node.get('id'), []).append(
                (sheet, node))

    for tid, nodes in threads.items():
        root_sheet, root = nodes[0]
        body = '\n\n'.join(comment_text(n) for _, n in nodes)
        name = row_label(sheets, root_sheet, root.get('ref'))
        request = bool(REQUEST.search(body))
        unmatched = sorted(n for n in candidate_names(body, places)
                           if not in_directory(n, known, listed_names))
        out.append({
            'sheet': root_sheet,
            'cell': root.get('ref', ''),
            'row_name': name,
            'date': (root.get('dT') or '')[:10],
            'resolved': 'yes' if root.get('done') == '1' else 'no',
            'replies': len(nodes) - 1,
            'looks_like_a_request': 'yes' if request else '',
            'row_in_directory': 'yes' if W.slugify(name) in known else 'no' if name else '',
            'names_not_in_directory': '; '.join(unmatched[:6]),
            'text': body,
        })

    out.sort(key=lambda r: (r['resolved'] == 'yes', r['date']))
    W.write_table(OUT, ['sheet', 'cell', 'row_name', 'date', 'resolved',
                        'replies', 'looks_like_a_request', 'row_in_directory',
                        'names_not_in_directory', 'text'], out)
    print('%d threads -> %s' % (len(out), os.path.relpath(OUT, W.ROOT)))

    todo = [r for r in out
            if r['resolved'] == 'no' or (r['looks_like_a_request']
                                         and r['row_in_directory'] == 'no')]
    if not todo:
        print('nothing looks outstanding')
        return
    print('\n%d thread(s) worth a look:\n' % len(todo))
    for r in todo:
        print('  %s!%s  %s  resolved=%s  %s'
              % (r['sheet'], r['cell'], r['date'], r['resolved'],
                 r['row_name'] or '(no name in column A)'))
        print('    %s' % ' '.join(r['text'].split())[:200])
        if r['names_not_in_directory']:
            print('    names not in the directory: %s'
                  % r['names_not_in_directory'])
        print()


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(W.ROOT, 'WRiFO.xlsx'))
