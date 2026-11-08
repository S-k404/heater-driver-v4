"""Stage 1: placement, outline, rules, hand-routed power copper, isolation keepout -> .kicad_pcb + .dsn"""
import pcbnew, sys
from pcb_lib import *
import place
OUT = sys.argv[1]; DSN = sys.argv[2]
b = pcbnew.BOARD()
fps, nets = build(b, place.PLACE)
W, H = place.W, place.H
F, B = pcbnew.F_Cu, pcbnew.B_Cu

# ---- outline (1 mm corner radius) ----
def shape_seg(x1, y1, x2, y2, layer, w):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(V(x1, y1)); s.SetEnd(V(x2, y2)); s.SetLayer(layer); s.SetWidth(mm(w)); b.Add(s); return s
def shape_arc(cx, cy, sx, sy, ang, layer=pcbnew.Edge_Cuts, w=0.1):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_ARC); s.SetCenter(V(cx, cy)); s.SetStart(V(sx, sy)); s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(ang, pcbnew.DEGREES_T)); s.SetLayer(layer); s.SetWidth(mm(w)); b.Add(s)
r = 1.0
shape_seg(r, 0, W - r, 0, pcbnew.Edge_Cuts, 0.1); shape_seg(W, r, W, H - r, pcbnew.Edge_Cuts, 0.1)
shape_seg(W - r, H, r, H, pcbnew.Edge_Cuts, 0.1); shape_seg(0, H - r, 0, r, pcbnew.Edge_Cuts, 0.1)
shape_arc(r, r, 0, r, 90); shape_arc(W - r, r, W - r, 0, 90); shape_arc(W - r, H - r, W, H - r, 90); shape_arc(r, H - r, r, H, 90)

# ---- rules ----
ds = b.GetDesignSettings()
nc = ds.m_NetSettings.GetDefaultNetclass()
nc.SetTrackWidth(mm(0.3)); nc.SetClearance(mm(0.2)); nc.SetViaDiameter(mm(0.7)); nc.SetViaDrill(mm(0.35))
ds.m_MinClearance = mm(0.2); ds.m_TrackMinWidth = mm(0.2); ds.m_ViasMinSize = mm(0.6); ds.m_MinThroughDrill = mm(0.3)
ds.m_CopperEdgeClearance = mm(0.4); ds.m_HoleClearance = mm(0.25); ds.m_HoleToHoleMin = mm(0.25)
ds.SetCopperLayerCount(2)

# ---- hand-routed high-current copper ----
def trk(pts, w, net, layers=(F,)):
    for layer in layers:
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(b); t.SetStart(V(x1, y1)); t.SetEnd(V(x2, y2)); t.SetWidth(mm(w))
            t.SetLayer(layer); t.SetNet(nets[net]); t.SetLocked(True); b.Add(t)
def via(x, y, net, d=0.8, drill=0.4):
    v = pcbnew.PCB_VIA(b); v.SetPosition(V(x, y)); v.SetWidth(mm(d)); v.SetDrill(mm(drill)); v.SetNet(nets[net]); v.SetLocked(True); b.Add(v)

P = lambda ref, pad: [(pcbnew.ToMM(p.GetPosition().x) - OX, pcbnew.ToMM(p.GetPosition().y) - OY) for p in fps[ref].Pads() if p.GetNumber() == pad]
j1v, = P('J1', '1'); j1g, = P('J1', '2'); j2p, = P('J2', '1'); j2n, = P('J2', '2')
f1v = P('F1', '1'); f1o = P('F1', '2')
c1p, = P('C1', '1'); tvk, = P('TVS1', '1'); d1k, = P('D1', '1'); d1a, = P('D1', '2')
qg, = P('Q1', '1'); qd, = P('Q1', '2'); qs, = P('Q1', '3'); rs1, = P('RS1', '1'); rs4, = P('RS1', '4')
print('pads', j1v, j1g, j2p, j2n, f1v, f1o, c1p, tvk, d1k, d1a, qg, qd, qs, rs1, rs4)
lo = max(f1o, key=lambda p: p[1])          # lower +12V clip of F1
# VIN: J1.1 -> both F1 VIN clips (both layers)
trk([j1v, (f1v[0][0], j1v[1])], 3.0, 'VIN', (F, B))
trk([f1v[0], f1v[1]], 2.6, 'VIN', (F, B))
# +12V: F1 out -> TVS1 K -> D1 K -> straight under the shunt strap -> J2.1 (both layers); C1+ spur
trk([f1o[0], f1o[1]], 2.6, '+12V', (F, B))
trk([lo, (tvk[0], lo[1] + 2.1), tvk], 2.6, '+12V', (F, B))
trk([tvk, d1k], 2.6, '+12V', (F,))      # top only: leaves a bottom-layer passage for the SH_N Kelvin line
trk([d1k, j2p], 3.0, '+12V', (F, B))
trk([c1p, (c1p[0] + 1.6, c1p[1] - 3.0), lo], 1.6, '+12V', (F,))
# HEAT_N: J2.2 -> Q1 drain (both layers), D1 anode -> J2.2 straight under the strap
trk([j2n, (qd[0], j2n[1] + 2.3)], 3.0, 'HEAT_N', (F, B))
trk([(qd[0], j2n[1] + 2.3), qd], 2.2, 'HEAT_N', (F, B))
trk([d1a, j2n], 1.5, 'HEAT_N', (F, B))
# SRC: Q1 source -> shunt current pad (both layers, short)
trk([qs, rs1], 2.4, 'SRC', (F, B))
# GND return: shunt GND pad -> J1 GND (both layers) + stitching
trk([rs4, j1g], 3.0, 'GND', (F, B))
for (x, y) in [(44.2, 10.8), (45.8, 10.4), (44.0, 7.8)]:
    via(x, y, 'GND')
# gate network, hand-routed: Q1 gate -> R5/ZD1/R4 (bottom), source returns to Q1 S (top)
r5g, = P('R5', '1'); r5s, = P('R5', '2'); zg, = P('ZD1', '1'); zs, = P('ZD1', '2'); r4g, = P('R4', '2')
trk([qg, (qg[0], qg[1] + 3.0), (r5s[0] + 0.3, qg[1] + 3.0), r5g], 0.5, 'GATE', (B,))
trk([r5g, zg], 0.5, 'GATE', (B,))
trk([zg, (zg[0] + 1.2, zg[1] + 1.7), r4g], 0.5, 'GATE', (B,))
trk([zs, r5s, (r5s[0], qs[1] + 0.6), qs], 0.5, 'SRC', (F,))
# fault LED anode: R15 -> D3, around the gate network along the bottom edge
r15a, = P('R15', '2'); d3a, = P('D3', '2')
trk([r15a, (r15a[0] + 1.6, r15a[1] + 1.6), (r15a[0] + 1.6, 40.3), (46.4, 40.3), (46.4, d3a[1]), d3a], 0.4, 'FLED_A', (F,))
# logic +12V feed for U2 collector / R16 from the F1 output clip
r16p, = P('R16', '1')
trk([r16p, (r16p[0] + 1.3, r16p[1] + 1.5), (f1o[0][0], r16p[1] + 1.5)], 0.6, '+12V', (F,))

# ---- isolation band: no copper of any kind (both layers) ----
def rule_area(pts, name):
    z = pcbnew.ZONE(b); z.SetIsRuleArea(True); z.SetZoneName(name)
    z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True); z.SetDoNotAllowCopperPour(True)
    z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
    ls = pcbnew.LSET(); ls.AddLayer(F); ls.AddLayer(B); z.SetLayerSet(ls)
    ol = z.Outline(); ol.NewOutline()
    for x, y in pts: ol.Append(mm(OX + x), mm(OY + y))
    b.Add(z)
ISO = [(10.0, -0.5), (13.0, -0.5), (13.0, 20.0), (-0.5, 20.0), (-0.5, 17.0), (10.0, 17.0)]
rule_area(ISO, 'ISOLATION_BARRIER')
# keep signal tracks off the bottom-layer drain copper (J2 HEAT- -> Q1 drain)
z = pcbnew.ZONE(b); z.SetIsRuleArea(True); z.SetZoneName('HEATN_BOTTOM_KEEPOUT')
z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True); z.SetDoNotAllowCopperPour(False)
z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
ls = pcbnew.LSET(); ls.AddLayer(B); z.SetLayerSet(ls)
ol = z.Outline(); ol.NewOutline()
for x, y in [(35.5, 19.0), (53.6, 19.0), (53.6, 23.5), (50.15, 23.5), (50.15, 26.4), (40.6, 26.4), (40.6, 22.2), (35.5, 22.2)]: ol.Append(mm(OX + x), mm(OY + y))
b.Add(z)
b.Save(OUT)
print('DSN', pcbnew.ExportSpecctraDSN(b, DSN))
