import pcbnew, itertools, importlib
from pcb_lib import *
import place
def check():
    b = pcbnew.BOARD(); fps, nets = build(b, place.PLACE)
    bbs = {}
    for r, f in fps.items():
        c = f.GetCourtyard(pcbnew.F_CrtYd)
        bb = c.BBox()
        bbs[r] = [pcbnew.ToMM(v) - o for v, o in ((bb.GetLeft(), OX), (bb.GetRight(), OX), (bb.GetTop(), OY), (bb.GetBottom(), OY))]
    bad = []
    for a, c in itertools.combinations(bbs, 2):
        A, B = bbs[a], bbs[c]
        ox = min(A[1], B[1]) - max(A[0], B[0]); oy = min(A[3], B[3]) - max(A[2], B[2])
        if ox > 0.001 and oy > 0.001: bad.append((a, c, round(ox, 2), round(oy, 2)))
    for r, (l, rr, t, bt) in bbs.items():
        if r.startswith('H') or r.startswith('J'): continue
        if l < -0.01 or t < -0.01 or rr > place.W + .01 or bt > place.H + .01: bad.append((r, 'EDGE', round(l,2), round(rr,2), round(t,2), round(bt,2)))
    return bad, bbs
if __name__ == '__main__':
    bad, _ = check()
    for x in bad: print(x)
    print('overlaps:', len(bad))
