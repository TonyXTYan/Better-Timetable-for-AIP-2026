# python3 report.py <dir with measure.js JSON files>  -> table.md (medians, ms from the press) and table.txt
import json, sys, os, glob
d = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), 'base')
files = sorted([f for f in glob.glob(os.path.join(d, '*.json')) if not os.path.basename(f).startswith('cast-')], key=lambda f: (('p' in os.path.basename(f)[:1]), f))
CUM = [('pill', 'pill'), ('wt', 'wt'), ('go', 'go'), ('cb', 'cb'), ('built', 'render1'), ('scans', 'scans'), ('ready', 'ready'), ('motion', 'anim0'), ('p90', 'p90:anim0'), ('paint1', 'evtPaint'),
       ('pMove', 'pMove'), ('pArr', 'pArr'), ('pGap', 'pGap'), ('p90gap', 'p90:pGap'), ('pFi', 'pFi'), ('pFrz%', 'pFrz100'), ('minFrz%', 'min:pFrz100')]
PARTS = [('inQ', 'input'), ('anch', 'anchor'), ('old', 'old'), ('oSnap', 'oldSnap'), ('rend', 'render'), ('lay', 'layout'), ('place', 'place'), ('nScan', 'newScan'), ('plan', 'plan'), ('nSnap', 'newSnap'), ('start', 'startWait'), ('n0', 'nodes0'), ('n1', 'nodes1'), ('named', 'named'), ('pairs', 'pairs')]
def f(x): return '-' if x is None else str(round(x))
rows = []
for fn in files:
    r = json.load(open(fn))
    cfg = f"{'desk' if r['dev'].startswith('d') else 'phone'} {r['cpu']}x {r['saved']}s" + (f" h{r['hold']}" if r.get('hold') else '')
    for sn, s in r['switches'].items():
        for dn, dd in s['dirs'].items():
            med, p90 = dd['med'], dd['p90']
            def v(k):
                if k.endswith('100'):
                    x = v(k[:-3]); return None if x is None else x * 100
                if k.startswith('min:'): return (dd.get('min') or {}).get(k[4:])
                if k.startswith('p90:'): return p90.get(k[4:])
                if sn == 'fold' and k == 'render1': return med.get('built')
                if sn == 'day-v' and k == 'scans': return med.get('slide0')
                return med.get(k)
            rows.append([cfg, sn, dn] + [f(v(k)) for _, k in CUM] + [f(v(k)) for _, k in PARTS] + [dd['kinds'] + (f" miss{dd['missing']}" if dd.get('missing') else ''), ' '.join(s.get('errors') or [])[:60]])
hdr = ['config', 'switch', 'dir'] + [c for c, _ in CUM] + [c for c, _ in PARTS] + ['kind/level', 'err']
with open(os.path.join(d, 'table.md'), 'w') as o:
    o.write('| ' + ' | '.join(hdr) + ' |\n|' + '---|' * len(hdr) + '\n')
    for r in rows: o.write('| ' + ' | '.join(r) + ' |\n')
w = [max(len(str(x[i])) for x in [hdr] + rows) for i in range(len(hdr))]
with open(os.path.join(d, 'table.txt'), 'w') as o:
    for r in [hdr] + rows: o.write('  '.join(str(x).ljust(w[i]) for i, x in enumerate(r)).rstrip() + '\n')
print(open(os.path.join(d, 'table.txt')).read())
