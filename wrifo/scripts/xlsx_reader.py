#!/usr/bin/env python3
"""Minimal stdlib xlsx -> csv converter (no third-party deps)."""
import zipfile, csv, sys, os, re, datetime
import xml.etree.ElementTree as ET

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
RNS = '{http://schemas.openxmlformats.org/package/2006/relationships}'

def col_to_idx(ref):
    m = re.match(r'([A-Z]+)', ref)
    n = 0
    for ch in m.group(1):
        n = n * 26 + (ord(ch) - 64)
    return n - 1

def shared_strings(z):
    out = []
    if 'xl/sharedStrings.xml' not in z.namelist():
        return out
    root = ET.fromstring(z.read('xl/sharedStrings.xml'))
    for si in root.findall('m:si', NS):
        out.append(''.join(t.text or '' for t in si.iter('{%s}t' % NS['m'])))
    return out

def date_styles(z):
    """Return set of style indices that format as dates."""
    root = ET.fromstring(z.read('xl/styles.xml'))
    numfmt = {}
    for nf in root.iter('{%s}numFmt' % NS['m']):
        numfmt[int(nf.get('numFmtId'))] = nf.get('formatCode')
    builtin_dates = set(range(14, 23)) | set(range(45, 48))
    dstyles = set()
    cellxfs = root.find('m:cellXfs', NS)
    if cellxfs is None:
        return dstyles
    for i, xf in enumerate(cellxfs.findall('m:xf', NS)):
        fid = int(xf.get('numFmtId', 0))
        code = numfmt.get(fid, '')
        if fid in builtin_dates or (code and re.search(r'[ymdhs]', re.sub(r'\[[^\]]*\]|"[^"]*"', '', code))):
            dstyles.add(i)
    return dstyles

def excel_date(v):
    try:
        f = float(v)
    except ValueError:
        return v
    base = datetime.datetime(1899, 12, 30)
    d = base + datetime.timedelta(days=f)
    if abs(f - int(f)) < 1e-9:
        return d.strftime('%Y-%m-%d')
    return d.strftime('%Y-%m-%d %H:%M:%S')

def sheet_map(z):
    wb = ET.fromstring(z.read('xl/workbook.xml'))
    rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    rid = {r.get('Id'): r.get('Target') for r in rels.findall(RNS + 'Relationship')}
    out = []
    for s in wb.find('m:sheets', NS).findall('m:sheet', NS):
        t = rid[s.get('{%s}id' % NS['r'])].lstrip('/')
        if not t.startswith('xl/'):
            t = 'xl/' + t
        out.append((s.get('name'), t))
    return out

def read_sheet(z, path, ss, dstyles):
    root = ET.fromstring(z.read(path))
    rows = []
    for row in root.iter('{%s}row' % NS['m']):
        cells = {}
        for c in row.findall('m:c', NS):
            ref = c.get('r')
            idx = col_to_idx(ref) if ref else len(cells)
            t = c.get('t')
            if t == 'inlineStr':
                is_ = c.find('m:is', NS)
                val = ''.join(x.text or '' for x in is_.iter('{%s}t' % NS['m'])) if is_ is not None else ''
            else:
                v = c.find('m:v', NS)
                val = v.text if v is not None and v.text is not None else ''
                if t == 's' and val != '':
                    val = ss[int(val)]
                elif t == 'b':
                    val = 'TRUE' if val == '1' else 'FALSE'
                elif t is None and val != '':
                    s_ = c.get('s')
                    if s_ is not None and int(s_) in dstyles:
                        val = excel_date(val)
                    else:
                        try:
                            f = float(val)
                            val = str(int(f)) if f == int(f) and abs(f) < 1e15 else repr(f)
                        except ValueError:
                            pass
            if val != '':
                cells[idx] = val.replace('\r\n', '\n').strip()
        if cells:
            n = max(cells) + 1
            rows.append([cells.get(i, '') for i in range(n)])
        else:
            rows.append([])
    # trim trailing blank rows
    while rows and not any(x for x in rows[-1]):
        rows.pop()
    width = max((len(r) for r in rows), default=0)
    return [r + [''] * (width - len(r)) for r in rows]

EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')


def main(src, outdir):
    """Dump every sheet to CSV. Email addresses are redacted: this path exists
    to write the archive under wrifo/sources/, which is committed publicly."""
    os.makedirs(outdir, exist_ok=True)
    z = zipfile.ZipFile(src)
    ss = shared_strings(z)
    dstyles = date_styles(z)
    for name, path in sheet_map(z):
        rows = read_sheet(z, path, ss, dstyles)
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        dest = os.path.join(outdir, slug + '.csv')
        rows = [[EMAIL.sub('[email redacted]', c) for c in r] for r in rows]
        with open(dest, 'w', newline='', encoding='utf-8') as fh:
            csv.writer(fh).writerows(rows)
        print(f'{name:28s} -> {dest}  ({len(rows)} rows x {len(rows[0]) if rows else 0} cols)')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
