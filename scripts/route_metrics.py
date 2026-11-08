"""Routing quality metrics: signal length, vias, segments, non-45 segments, tiny segments."""
import pcbnew, sys, math
for fn in sys.argv[1:]:
    b = pcbnew.LoadBoard(fn)
    segs = [t for t in b.GetTracks() if t.GetClass() == 'PCB_TRACK' and not t.IsLocked()]
    vias = [t for t in b.GetTracks() if t.GetClass() == 'PCB_VIA' and not t.IsLocked()]
    L = sum(pcbnew.ToMM(t.GetLength()) for t in segs)
    odd = 0
    for t in segs:
        a = math.degrees(math.atan2(t.GetEnd().y - t.GetStart().y, t.GetEnd().x - t.GetStart().x)) % 45
        if 0.5 < a < 44.5: odd += 1
    tiny = sum(1 for t in segs if pcbnew.ToMM(t.GetLength()) < 0.3)
    print('%-40s signal length %6.1f mm | segments %3d | vias %2d | off-45 %2d | tiny %2d' % (fn.split('/')[-1], L, len(segs), len(vias), odd, tiny))
