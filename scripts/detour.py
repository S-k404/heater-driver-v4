import pcbnew, sys, math, collections
b = pcbnew.LoadBoard(sys.argv[1])
L = collections.Counter()
for t in b.GetTracks():
    if t.GetClass() == 'PCB_TRACK' and not t.IsLocked(): L[t.GetNetname()] += pcbnew.ToMM(t.GetLength())
pads = collections.defaultdict(list)
for f in b.GetFootprints():
    for p in f.Pads():
        if p.GetNetname(): pads[p.GetNetname()].append((pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y), f.GetReference() + '.' + p.GetNumber()))
rows = []
for n, pts in pads.items():
    if n in ('GND', '+12V') or len(pts) < 2: continue
    done = [0]; rest = list(range(1, len(pts))); mst = 0
    while rest:
        d, i, j = min((math.dist(pts[i][:2], pts[j][:2]), i, j) for i in done for j in rest); mst += d; done.append(j); rest.remove(j)
    rows.append((L[n] / mst if mst else 0, n, round(L[n], 1), round(mst, 1), ' '.join(p[2] for p in pts)))
for r in sorted(rows, reverse=True): print('%5.2fx %-10s routed %6.1f  direct %6.1f   %s' % r)
print('GND routed', round(L['GND'], 1), '+12V routed', round(L['+12V'], 1))
