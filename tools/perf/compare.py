# python3 compare.py <baseDir> <newDir> [suffix]  -> per row: base median (p90-med spread) vs new median (spread)
# for MOT (anim0), go, ready, pill, evtPaint; '*' marks |new-base| over the larger of the two spreads
# and 10ms (the plan's noise rule, both ways), 'KIND' a different guard-kind mix.
# suffix: '' for the hold-0 files, '-h100' etc. for others (new dir only).
import json, sys, os, glob
b, n = sys.argv[1], sys.argv[2]; suf = sys.argv[3] if len(sys.argv) > 3 else ''
KEYS = [('MOT', 'anim0'), ('go', 'go'), ('ready', 'ready'), ('pill', 'pill'), ('paint', 'evtPaint')]
tot = {k: [0, 0] for k, _ in KEYS}
out = []
for fb in sorted(f for f in glob.glob(os.path.join(b, '*.json')) if not os.path.basename(f).startswith('cast-')):
    name = os.path.basename(fb)[:-5]
    fn = os.path.join(n, name + suf + '.json')
    if not os.path.exists(fn): continue
    B, N = json.load(open(fb)), json.load(open(fn))
    for sn, s in B['switches'].items():
        if sn not in N['switches']: continue
        for dn, d in s['dirs'].items():
            e = N['switches'][sn]['dirs'].get(dn)
            if not e: continue
            row = [name, sn, dn]
            for lab, k in KEYS:
                k2 = 'built' if (sn == 'fold' and k == 'anim0' and d['med'].get(k) is None) else k
                bm, bp, nm, np_ = d['med'].get(k2), d['p90'].get(k2), e['med'].get(k2), e['p90'].get(k2)
                if bm is None or nm is None: row.append(f"{lab} -"); continue
                sp = max(bp - bm, np_ - nm, 10)
                flag = '*' if abs(nm - bm) > sp else ''
                tot[lab][0] += 1; tot[lab][1] += bool(flag)
                row.append(f"{lab} {bm:.0f}->{nm:.0f}{flag}")
            kb = d['kinds'].replace('×', 'x'); kn = e['kinds'].replace('×', 'x')
            if kb != kn: row.append(f"KIND {kb} | {kn}")
            out.append('\t'.join(row))
print('\n'.join(out))
print('outside noise:', {k: f"{v[1]}/{v[0]}" for k, v in tot.items()})
