# Pill continuity, from measure.js --cast screencasts (after r36 cast2.js / r39 pillana.py).
# python3 -I pillcont.py <cast-....json>  -> JSON list, one object per sample, ms from the press:
#   pMove   first frame the pill's centre has left where it was (> 1.5px)
#   pArr    first frame it has covered 95% of its travel (the tail of the ease moves under a
#           pixel a frame, so gaps there would be the rounding, not a stall)
#   pGap    longest interval between two frames that show the pill at different places,
#           from pMove to pArr (screencast frames come only when something drew)
#   pFi     the frame interval there: the median interval between consecutive screencast
#           frames (any change) from pMove to pArr. Headless Chromium composites in software,
#           and a big page (the 21,814-node list) can run at 40ms frames with nothing frozen.
#   pFrz    its progress (0..1) at the first frame of that window followed by a gap over
#           max(FREEZE_MS, 2.5 * pFi), i.e. more than 2 frames; 1 when there is none
#   pFrzAt  that frame's time
#   pFrames frames with the pill at a new place (pMove..pArr)
# The pill: the longest run (> 10px) of the accent colour along the row measure.js chose (3px
# inside the top of the pressed option, above the labels), across the group; the accent is the colour under the
# chosen option's centre in the first frame. Travel: from its centre in the first frame to its
# centre in the last.
import json, sys, os
from PIL import Image
import numpy as np

FREEZE_MS = 42.0
casts = json.load(open(sys.argv[1]))


def runs_of(a, y, x0, x1, acc):
    row = a[y, x0:x1]
    hit = np.abs(row - acc).sum(1) < 60
    out, i, n = [], 0, len(hit)
    while i < n:
        if hit[i]:
            j = i
            while j < n and hit[j]: j += 1
            if j - i > 10: out.append((i + x0, j + x0))
            i = j
        else: i += 1
    return out


def one(c):
    g, fr = c['geo'], c['frames']
    if len(fr) < 2: return {'pNote': 'frames<2'}
    a0 = np.asarray(Image.open(os.path.join(c['dir'], fr[0][0])).convert('RGB')).astype(int)
    sx = a0.shape[1] / g['w']
    y = int(round(g['y'] * sx)); x0 = max(0, int(g['x0'] * sx)); x1 = min(a0.shape[1], int(g['x1'] * sx))
    if not (0 <= y < a0.shape[0]): return {'pNote': 'row off screen'}
    ox = g['onX'] if g.get('onX') is not None else g['toX']
    acc = a0[y, min(a0.shape[1] - 1, max(0, int(ox * sx)))]
    pts = []   # (t ms from press, centre px css)
    prev = None
    for name, ts in fr:
        a = a0 if name == fr[0][0] else np.asarray(Image.open(os.path.join(c['dir'], name)).convert('RGB')).astype(int)
        rs = runs_of(a, y, x0, x1, acc)
        t = ts * 1000 - c['t0e']
        if not rs: pts.append((t, None)); continue
        if prev is None: r = max(rs, key=lambda r: r[1] - r[0])
        else: r = min(rs, key=lambda r: abs((r[0] + r[1]) / 2 - prev))
        cx = (r[0] + r[1]) / 2 / sx
        prev = cx * sx
        pts.append((t, cx))
    good = [p for p in pts if p[1] is not None]
    if len(good) < 2: return {'pNote': 'no pill'}
    c0, c1 = good[0][1], good[-1][1]
    if abs(c1 - c0) < 3: return {'pNote': 'pill did not move'}
    prog = lambda cx: (cx - c0) / (c1 - c0)
    # only the frames after the press count as motion (frames before it are the rest state)
    mv = next((k for k, (t, cx) in enumerate(good) if t > -5 and abs(cx - c0) > 1.5), None)
    if mv is None: return {'pNote': 'no move after press'}
    arr = next((k for k in range(mv, len(good)) if prog(good[k][1]) >= .95), len(good) - 1)
    # change frames in the window: the first frame of each new position
    ch = [good[mv]]
    for k in range(mv + 1, arr + 1):
        if abs(good[k][1] - ch[-1][1]) > .4: ch.append(good[k])
    # the interval from the last frame before pMove (the pill still at rest) is not a stall
    gaps = [(ch[k + 1][0] - ch[k][0], ch[k]) for k in range(len(ch) - 1)]
    pGap = max((d for d, _ in gaps), default=0.0)
    ts = [t for t, _ in pts if good[mv][0] <= t <= good[arr][0]]
    iv = sorted(b - a for a, b in zip(ts, ts[1:]))
    pFi = iv[len(iv) // 2] if iv else 16.7
    lim = max(FREEZE_MS, 2.5 * pFi)
    frz = next(((prog(q[1]), q[0]) for d, q in gaps if d > lim), None)
    out = {'pMove': good[mv][0], 'pArr': good[arr][0], 'pGap': pGap, 'pFi': pFi,
           'pFrz': frz[0] if frz else 1.0, 'pFrzAt': frz[1] if frz else None, 'pFrames': len(ch)}
    return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in out.items() if v is not None}


res = []
for c in casts:
    try: res.append(one(c))
    except Exception as e: res.append({'pNote': 'err ' + str(e)[:80]})
print(json.dumps(res))
