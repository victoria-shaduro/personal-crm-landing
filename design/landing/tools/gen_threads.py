"""Generates the woven thread illustrations for the Uzelok landing page.

Each thread is a cubic Bezier path rendered as a shaded tube (7 opaque
stroke layers). Crossings are detected automatically; over/under alternates
along each thread, and the "over" thread is redrawn on top inside a feathered
circular mask, with a soft shadow masked to the "under" thread.

Usage: python3 gen_threads.py <output_dir>
"""
import math, os, sys

def cubic(p0, p1, p2, p3, t):
    u = 1 - t
    return (u**3*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t**3*p3[0],
            u**3*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t**3*p3[1])

def sample(start, curves, n=120):
    pts = [start]; cur = start
    for p1, p2, p3 in curves:
        for i in range(1, n + 1):
            pts.append(cubic(cur, p1, p2, p3, i / n))
        cur = p3
    return pts

def seg_inter(a, b, c, d):
    d1 = (b[0]-a[0], b[1]-a[1]); d2 = (d[0]-c[0], d[1]-c[1])
    den = d1[0]*d2[1] - d1[1]*d2[0]
    if abs(den) < 1e-9: return None
    t = ((c[0]-a[0])*d2[1] - (c[1]-a[1])*d2[0]) / den
    u = ((c[0]-a[0])*d1[1] - (c[1]-a[1])*d1[0]) / den
    return (t, u) if 0 <= t < 1 and 0 <= u < 1 else None

def crossings(P, Q, self_=False):
    res = []
    for i in range(len(P)-1):
        for j in range(len(Q)-1):
            if self_ and j <= i + 3: continue
            r = seg_inter(P[i], P[i+1], Q[j], Q[j+1])
            if r: res.append((i + r[0], j + r[1]))
    return res

def at(pts, x):
    n = len(pts)-1; i = min(int(x), n-1); f = x - i
    return (pts[i][0] + (pts[i+1][0]-pts[i][0])*f, pts[i][1] + (pts[i+1][1]-pts[i][1])*f)

def d_of(pts, a=None, b=None):
    n = len(pts)-1; a = 0 if a is None else max(0, a); b = n if b is None else min(n, b)
    xs = [a] + [i for i in range(math.ceil(a), math.floor(b)+1) if a < i < b] + [b]
    return "M" + " L".join(f"{at(pts,x)[0]:.1f} {at(pts,x)[1]:.1f}" for x in xs)

def angle(pts, x):
    a = at(pts, max(0, x-1)); b = at(pts, min(len(pts)-1, x+1))
    return math.atan2(b[1]-a[1], b[0]-a[0])

def mix(hexc, f):
    r, g, b = [int(hexc[i:i+2], 16) for i in (1, 3, 5)]
    if f < 0: r, g, b = [c*(1+f) for c in (r, g, b)]
    else: r, g, b = [c + (255-c)*f for c in (r, g, b)]
    return '#%02X%02X%02X' % tuple(round(c) for c in (r, g, b))

# (width factor, lightness shift) from outer edge to highlight
LAYERS = [(1.0,-0.42),(0.88,-0.26),(0.76,-0.13),(0.62,0.0),(0.48,0.08),(0.32,0.17),(0.16,0.3)]

def grad_defs(gid, coords, stops):
    x1, y1, x2, y2 = coords; out = []
    for li, (w, f) in enumerate(LAYERS):
        st = "".join(f'<stop offset="{o}" stop-color="{mix(c,f)}"/>' for o, c in stops)
        out.append(f'<linearGradient id="{gid}{li}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" gradientUnits="userSpaceOnUse">{st}</linearGradient>')
    return "".join(out)

def tube(d, t):
    return "".join(f'<path d="{d}" stroke="url(#{t["grad"]}{li})" stroke-width="{t["width"]*w:.1f}" stroke-linecap="round" stroke-linejoin="round" fill="none"/>' for li, (w, f) in enumerate(LAYERS))

def render(threads, prefix, grads):
    defs = [grad_defs(*g) for g in grads]
    defs.append(f'<radialGradient id="{prefix}feather"><stop offset="0" stop-color="#fff"/><stop offset="0.72" stop-color="#fff"/><stop offset="1" stop-color="#000"/></radialGradient>')
    out = [tube(d_of(t['pts']), t) for t in threads]
    cs = []
    for i in range(len(threads)):
        for j in range(i, len(threads)):
            for pa, pb in crossings(threads[i]['pts'], threads[j]['pts'], self_=(i == j)):
                cs.append((i, pa, j, pb))
    idx = {}
    for k in range(len(threads)):
        ev = sorted([(c[1], n) for n, c in enumerate(cs) if c[0] == k] + [(c[3], n) for n, c in enumerate(cs) if c[2] == k])
        for r, (p, n) in enumerate(ev): idx.setdefault(n, []).append((k, p, r))
    step = lambda t, p: math.hypot(*[a-b for a, b in zip(at(t['pts'], p+1), at(t['pts'], p))]) or 1
    for n, (i, pa, j, pb) in enumerate(cs):
        ri = [r for (k, p, r) in idx[n] if k == i and abs(p-pa) < 1e-6][0]
        i_over = (ri % 2 == 0) != threads[i].get('flip', False)
        ov, op = (i, pa) if i_over else (j, pb)
        un, up = (j, pb) if i_over else (i, pa)
        to, tu = threads[ov], threads[un]
        th = max(abs(math.sin(angle(to['pts'], op) - angle(tu['pts'], up))), 0.3)
        r = ((to['width']*0.8 + tu['width']*0.6)/th + 16)/0.72
        c = at(to['pts'], op)
        sub = d_of(to['pts'], op - r*2.4/step(to, op), op + r*2.4/step(to, op))
        usub = d_of(tu['pts'], up - r*2.4/step(tu, up), up + r*2.4/step(tu, up))
        cid, mid = f'{prefix}c{n}', f'{prefix}m{n}'
        defs.append(f'<mask id="{cid}" maskUnits="userSpaceOnUse" x="{c[0]-r-2:.0f}" y="{c[1]-r-2:.0f}" width="{2*r+4:.0f}" height="{2*r+4:.0f}"><circle cx="{c[0]:.1f}" cy="{c[1]:.1f}" r="{r:.1f}" fill="url(#{prefix}feather)"/></mask>')
        defs.append(f'<mask id="{mid}" maskUnits="userSpaceOnUse" x="-300" y="-300" width="2040" height="1300"><path d="{usub}" stroke="#fff" stroke-width="{tu["width"]}" fill="none"/></mask>')
        w = to['width']
        sh = (f'<path d="{sub}" stroke="#000" stroke-opacity="0.28" stroke-width="{w*1.7:.0f}" stroke-linecap="round" fill="none"/>'
              f'<path d="{sub}" stroke="#000" stroke-opacity="0.32" stroke-width="{w*1.3:.0f}" stroke-linecap="round" fill="none"/>')
        out.append(f'<g mask="url(#{cid})"><g mask="url(#{mid})">{sh}</g>{tube(sub, to)}</g>')
    return "".join(defs), "\n".join(out)

def svg(viewbox, defs, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" preserveAspectRatio="xMidYMid slice" aria-hidden="true">'
            f'<defs>{defs}</defs>\n{body}\n</svg>\n')

# ---- Hero: three threads, one ties a loop -------------------------------
HERO_GRADS = [('tA',(0,0,1440,0),[(0,'#8E8A3C'),(0.45,'#C9C46A'),(0.8,'#EE9A63'),(1,'#C46A3A')]),
              ('tB',(0,620,1440,0),[(0,'#4A3FA8'),(0.5,'#9C82E6'),(1,'#C9B5F5')]),
              ('tC',(0,0,1440,0),[(0,'#E8783A'),(1,'#F3B488')])]
HERO = [dict(width=54, grad='tA', pts=sample((-120,470),[((260,470),(420,170),(700,170)),((980,170),(1000,400),(760,410)),((520,420),(560,230),(840,260)),((1120,290),(1250,520),(1580,480))])),
        dict(width=54, grad='tB', flip=True, pts=sample((120,720),[((420,560),(620,400),(860,210)),((1040,70),(1280,10),(1580,70))])),
        dict(width=22, grad='tC', pts=sample((-120,250),[((260,320),(600,590),(1000,560)),((1240,540),(1350,430),(1580,380))]))]
# ---- Final CTA: two threads twisting into a knot -----------------------
FINAL_GRADS = [('fA',(0,0,1440,0),[(0,'#C9C46A'),(1,'#EE9A63')]),
               ('fB',(0,0,1440,0),[(0,'#6C5BD0'),(1,'#C9B5F5')])]
FINAL = [dict(width=40, grad='fA', pts=sample((-60,250),[((300,250),(520,80),(720,80)),((900,80),(900,230),(720,230)),((560,230),(600,120),(760,150)),((980,190),(1100,300),(1500,280))])),
         dict(width=40, grad='fB', flip=True, pts=sample((-60,120),[((360,120),(560,300),(760,240)),((960,180),(1100,90),(1500,110))]))]

if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else '.'
    os.makedirs(out, exist_ok=True)
    d, b = render(HERO, 'h', HERO_GRADS)
    open(os.path.join(out, 'threads-hero.svg'), 'w').write(svg('0 0 1440 620', d, b))
    open(os.path.join(out, 'threads-hero-mobile.svg'), 'w').write(svg('470 40 620 525', d, b))
    d, b = render(FINAL, 'f', FINAL_GRADS)
    open(os.path.join(out, 'threads-final.svg'), 'w').write(svg('0 0 1440 360', d, b))
    open(os.path.join(out, 'threads-final-mobile.svg'), 'w').write(svg('420 10 600 330', d, b))
    print('ok')
