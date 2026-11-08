"""Measure real copper cross-sections on the high-current paths and estimate temperature rise (IPC-2221, external, 1 oz)."""
import pcbnew, sys, json
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union
from pcb_lib import OX, OY, KNET
b = pcbnew.LoadBoard(sys.argv[1])
u = lambda v: pcbnew.ToMM(v)
def polys(sps):
    out = []
    for i in range(sps.OutlineCount()):
        o = sps.Outline(i); pts = [(u(o.CPoint(j).x) - OX, u(o.CPoint(j).y) - OY) for j in range(o.PointCount())]
        if len(pts) >= 3:
            p = Polygon(pts).buffer(0)
            for h in range(sps.HoleCount(i)):
                hh = sps.Hole(i, h); hp = [(u(hh.CPoint(j).x) - OX, u(hh.CPoint(j).y) - OY) for j in range(hh.PointCount())]
                if len(hp) >= 3: p = p.difference(Polygon(hp))
            out.append(p)
    return out
def copper(net, layer):
    g = []
    nc = b.FindNet(KNET(net)).GetNetCode()
    for t in b.GetTracks():
        if t.GetNetCode() == nc and t.IsOnLayer(layer):
            s = pcbnew.SHAPE_POLY_SET(); t.TransformShapeToPolygon(s, layer, 0, pcbnew.FromMM(0.01), pcbnew.ERROR_INSIDE); g += polys(s)
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetNetCode() == nc and p.IsOnLayer(layer):
                s = pcbnew.SHAPE_POLY_SET(); p.TransformShapeToPolygon(s, layer, 0, pcbnew.FromMM(0.01), pcbnew.ERROR_INSIDE); g += polys(s)
    for z in b.Zones():
        if z.GetNetCode() == nc and z.IsOnLayer(layer) and not z.GetIsRuleArea():
            g += polys(z.GetFilledPolysList(layer))
    return unary_union(g)
def dT(width_mm, I):
    A = width_mm / 0.0254 * 1.378          # mil^2, 1 oz = 1.378 mil
    return (I / (0.048 * A ** 0.725)) ** (1 / 0.44)
I = 8.33
CUTS = [
 ('VIN  J1 -> F1', 'VIN', [(44.0, 0.2), (44.0, 6.9)]),
 ('+12V F1 -> TVS1/C1', '+12V', [(27.0, 8.2), (34.6, 8.2)]),
 ('+12V TVS1 -> D1', '+12V', [(34.65, 7.6), (34.65, 17.6)]),
 ('+12V D1 -> J2 HEAT+ (under shunt strap)', '+12V', [(44.6, 12.6), (44.6, 18.6)]),
 ('HEAT_N J2 -> Q1 drain', 'HEAT_N', [(44.8, 22.0), (53.7, 22.0)]),
 ('HEAT_N at Q1 drain pin (TO-220 pitch-limited)', 'HEAT_N', [(47.3, 24.3), (50.1, 24.3)]),
 ('SRC  Q1 source -> RS1', 'SRC', [(44.4, 23.6), (44.4, 27.2)]),
 ('GND  RS1 -> J1 GND', 'GND', [(45.0, 6.9), (45.0, 12.2)]),
]
rows = []
for name, net, (p1, p2) in CUTS:
    line = LineString([p1, p2])
    wt = copper(net, pcbnew.F_Cu).intersection(line).length
    wb = copper(net, pcbnew.B_Cu).intersection(line).length
    tot = wt + wb
    rows.append((name, round(wt, 2), round(wb, 2), round(tot, 2), round(dT(tot, I), 1) if tot > 0 else None))
print('%-46s %6s %6s %6s %8s' % ('path (8.33 A)', 'top', 'bot', 'total', 'dT IPC'))
for r in rows: print('%-46s %6.2f %6.2f %6.2f %8s' % r)
# signal track widths
ws = {}
for t in b.GetTracks():
    if t.GetClass() == 'PCB_TRACK': ws.setdefault(t.GetNetname(), set()).add(round(u(t.GetWidth()), 2))
print('min signal track width:', min(min(v) for v in ws.values()), 'mm')
json.dump(rows, open(sys.argv[2], 'w'))
