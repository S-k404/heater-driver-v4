"""Stage 4: silkscreen - subsystem separators + titles, connector labels, reference designators, bottom legend."""
import pcbnew, sys, math
from shapely.geometry import Polygon, LineString, box, Point
from shapely.ops import unary_union
from pcb_lib import OX, OY, mm
import place
IN, OUT = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(IN)
W, H = place.W, place.H
FS, BS = pcbnew.F_SilkS, pcbnew.B_SilkS
u = lambda v: pcbnew.ToMM(v)
def bx(x, y): return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))

def poly_of(item, layer, clearance=0.0):
    sps = pcbnew.SHAPE_POLY_SET()
    item.TransformShapeToPolygon(sps, layer, mm(clearance), mm(0.02), pcbnew.ERROR_OUTSIDE)
    out = []
    for i in range(sps.OutlineCount()):
        o = sps.Outline(i)
        pts = [(u(o.CPoint(j).x) - OX, u(o.CPoint(j).y) - OY) for j in range(o.PointCount())]
        if len(pts) >= 3: out.append(Polygon(pts).buffer(0))
    return unary_union(out) if out else None

# ---------- obstacles ----------
pads_F = []      # exposed copper on top (silk must stay off)
silk_F = []      # existing footprint silk graphics
for f in b.GetFootprints():
    for p in f.Pads():
        if p.IsOnLayer(pcbnew.F_Cu) or p.IsOnLayer(pcbnew.F_Mask):
            g = poly_of(p, pcbnew.F_Cu, 0.0)
            if g is not None: pads_F.append(g)
        if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH or p.GetDrillSizeX() > mm(2.5):
            pass
    for it in f.GraphicalItems():
        if it.GetLayer() == FS:
            g = poly_of(it, FS, 0.0)
            if g is not None: silk_F.append(g)
# NPTH mounting holes keep-off
for f in b.GetFootprints():
    if f.GetReference().startswith('H'):
        c = f.GetPosition(); silk_F.append(Point(u(c.x) - OX, u(c.y) - OY).buffer(1.8))
from shapely.ops import polygonize
bodies = []; bodies_big = []
for f in b.GetFootprints():
    if f.GetReference().startswith('H'): continue
    segs = []; fills = []
    for it in f.GraphicalItems():
        if it.GetLayer() != pcbnew.F_Fab or it.GetClass() == 'PCB_TEXT': continue
        st = it.GetShape()
        if st == pcbnew.SHAPE_T_SEGMENT:
            segs.append(LineString([(u(it.GetStart().x) - OX, u(it.GetStart().y) - OY), (u(it.GetEnd().x) - OX, u(it.GetEnd().y) - OY)]))
        else:
            g = poly_of(it, pcbnew.F_Fab, 0.0)
            if g is not None:
                fills.append(Polygon(g.exterior) if g.geom_type == 'Polygon' else g.convex_hull)
    polys = list(polygonize(unary_union(segs))) if segs else []
    body = unary_union(polys + fills)
    if not body.is_empty:
        bodies.append(body)
        if f.GetReference()[:1] in 'UJF' or f.GetReference() in ('SW1', 'C1', 'Q1', 'TVS1', 'D1'):
            bodies_big.append(body)
BODIES = unary_union(bodies)
BODIES_BIG = unary_union(bodies_big)
PADS = unary_union(pads_F).buffer(0.15)        # silk-to-mask clearance
SILK = unary_union(silk_F)
INNER = box(0.35, 0.35, W - 0.35, H - 0.35)    # silk-to-edge margin
placed = []                                   # newly placed silk geometry (lines + texts)

def blocked(geom, extra_gap=0.12, bodies=False):
    if not INNER.contains(geom): return True
    if bodies == 'big' and geom.intersects(BODIES_BIG): return True
    if bodies is True and geom.intersects(BODIES): return True
    if geom.intersects(PADS): return True
    if geom.buffer(extra_gap).intersects(SILK): return True
    for g in placed:
        if geom.buffer(extra_gap).intersects(g): return True
    return False

def add_line(x1, y1, x2, y2, layer=FS, w=0.15):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(bx(x1, y1)); s.SetEnd(bx(x2, y2))
    s.SetLayer(layer); s.SetWidth(mm(w)); b.Add(s)

def clipped_polyline(pts, w=0.15, step=0.05, min_len=0.6):
    """draw polyline on F.SilkS, skipping any part that would touch pads / existing silk"""
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        L = math.hypot(x2 - x1, y2 - y1); n = max(1, int(L / step))
        ok = []
        for i in range(n + 1):
            t = i / n; x, y = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
            c = Point(x, y).buffer(w / 2)
            ok.append(INNER.contains(c) and not c.intersects(PADS) and not c.buffer(0.1).intersects(SILK))
        i = 0
        while i <= n:
            if ok[i]:
                j = i
                while j + 1 <= n and ok[j + 1]: j += 1
                ta, tb = i / n, j / n
                xa, ya = x1 + (x2 - x1) * ta, y1 + (y2 - y1) * ta
                xb, yb = x1 + (x2 - x1) * tb, y1 + (y2 - y1) * tb
                if math.hypot(xb - xa, yb - ya) >= min_len:
                    add_line(xa, ya, xb, yb, FS, w)
                    placed.append(LineString([(xa, ya), (xb, yb)]).buffer(w / 2))
                i = j + 1
            else:
                i += 1

def mk_text(txt, x, y, size, angle=0, layer=FS, bold=False, thick=None):
    t = pcbnew.PCB_TEXT(b); t.SetText(txt); t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size))); t.SetTextThickness(mm(thick or size * 0.15))
    t.SetBold(bold); t.SetTextAngleDegrees(angle); t.SetPosition(bx(x, y))
    t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER); t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    if layer == BS: t.SetMirrored(True)
    return t

def text_geom(t):
    bb = t.GetBoundingBox()
    return box(u(bb.GetLeft()) - OX, u(bb.GetTop()) - OY, u(bb.GetRight()) - OX, u(bb.GetBottom()) - OY)

def place_text(txt, cands, size, bold=False, required=True, within=None):
    """cands: list of (x, y, angle); first collision-free wins"""
    for bm in (True, 'big'):
      for (x, y, a) in cands:
        t = mk_text(txt, x, y, size, a, bold=bold)
        g = text_geom(t)
        if within is not None and not within.contains(g): continue
        if not blocked(g, bodies=bm):
            b.Add(t); placed.append(g); return (x, y, a)
    if required: print('  !! no spot for', txt)
    return None

def search(region, size, txt, angles=(0, 90), step=0.25, prefer=None):
    """grid search inside region polygon, nearest to prefer point"""
    minx, miny, maxx, maxy = region.bounds
    px, py = prefer or (region.centroid.x, region.centroid.y)
    pts = []
    x = minx
    while x <= maxx:
        y = miny
        while y <= maxy:
            pts.append((math.hypot(x - px, y - py), x, y)); y += step
        x += step
    pts.sort()
    return [(x, y, a) for _, x, y in pts for a in angles]

# ---------- subsystem separators ----------
SEPARATORS = [
 [(11.6, 6.6), (11.6, 18.6), (0.4, 18.6)],                                                   # isolation barrier
 [(11.6, 18.6), (11.6, 20.3), (23.9, 20.3), (23.9, 30.45), (40.5, 30.45)],                    # OCP | DRIVE
 [(25.8, 41.6), (25.8, 33.7), (40.5, 33.7)],                                                  # OCP | UI
 [(11.6, 6.6), (21.8, 6.6), (21.8, 17.9), (34.6, 17.9), (34.6, 23.2), (40.4, 23.2), (40.4, 8.4), (43.4, 8.4), (43.4, 12.1), (53.6, 12.1)],  # PROT
 [(37.95, 23.2), (37.95, 30.45)],                                                             # DRIVE | POWER
 [(40.5, 30.45), (40.5, 41.6)],                                                               # UI | POWER
]
# isolation barrier drawn heavier
clipped_polyline(SEPARATORS[0], w=0.3)
for s in SEPARATORS[1:]: clipped_polyline(s, w=0.15)

REGIONS = {
 '1 ISOLATED PWM IN': (Polygon([(0, 0), (11.6, 0), (11.6, 18.6), (0, 18.6)]), (5.5, 16.5)),
 '2 OCP + OTP LATCH': (Polygon([(0, 18.6), (11.6, 18.6), (11.6, 20.3), (23.9, 20.3), (23.9, 30.45), (40.5, 30.45), (40.5, 33.7), (25.8, 33.7), (25.8, 42), (0, 42)]), (12, 41)),
 '3 GATE DRIVE': (Polygon([(11.6, 6.6), (21.8, 6.6), (21.8, 17.9), (34.6, 17.9), (34.6, 23.2), (37.95, 23.2), (37.95, 30.45), (23.9, 30.45), (23.9, 20.3), (11.6, 20.3)]), (22, 19)),
 '4 POWER IN + PROTECTION': (Polygon([(21.8, 0), (54, 0), (54, 12.1), (43.4, 12.1), (43.4, 8.4), (40.4, 8.4), (40.4, 23.2), (34.6, 23.2), (34.6, 17.9), (21.8, 17.9)]), (28, 17)),
 '5 POWER STAGE 8.3A': (Polygon([(40.4, 8.4), (43.4, 8.4), (43.4, 12.1), (54, 12.1), (54, 42), (40.5, 42), (40.5, 30.45), (37.95, 30.45), (37.95, 23.2), (40.4, 23.2)]), (47, 30)),
 '6 UI': (Polygon([(25.8, 33.7), (40.5, 33.7), (40.5, 42), (25.8, 42)]), (33, 41.5)),
}
SHORT = {'1 ISOLATED PWM IN': '1 ISO IN', '2 OCP + OTP LATCH': '2 OCP/OTP', '3 GATE DRIVE': '3 DRIVE',
         '4 POWER IN + PROTECTION': '4 PWR IN/PROT', '5 POWER STAGE 8.3A': '5 POWER STAGE', '6 UI': '6 UI'}
print('titles:')
for name, (reg, pref) in REGIONS.items():
    short = SHORT[name]
    for sz, txt in [(0.9, name), (0.8, name), (0.8, short), (0.7, short), (0.7, short.split(' ')[0])]:
        r = place_text(txt, search(reg.buffer(-0.2), sz, txt, prefer=pref), sz, bold=True, required=False, within=reg)
        if r: print('  ', txt, r); break

# ---------- reference designators ----------
print('refs:')
CY = {}
for f in b.GetFootprints():
    if f.GetReference().startswith('H'): continue
    c = f.GetCourtyard(pcbnew.F_CrtYd).BBox()
    CY[f.GetReference()] = box(u(c.GetLeft()) - OX, u(c.GetTop()) - OY, u(c.GetRight()) - OX, u(c.GetBottom()) - OY)
for f in sorted(b.GetFootprints(), key=lambda f: f.GetReference()):
    rt = f.Reference(); ref = f.GetReference()
    rt.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8))); rt.SetTextThickness(mm(0.12)); rt.SetKeepUpright(True)
    if ref.startswith('H'):
        rt.SetVisible(False); continue
    cy = f.GetCourtyard(pcbnew.F_CrtYd).BBox()
    x0, x1, y0, y1 = u(cy.GetLeft()) - OX, u(cy.GetRight()) - OX, u(cy.GetTop()) - OY, u(cy.GetBottom()) - OY
    cx, cyy = (x0 + x1) / 2, (y0 + y1) / 2
    reg = box(x0 - 1.6, y0 - 1.6, x1 + 1.6, y1 + 1.6)
    cands = search(reg, 0.8, ref, step=0.2, prefer=(cx, cyy))
    own = box(x0, y0, x1, y1)
    def owned(g):
        c = g.centroid; d = own.distance(c)
        return all(d <= o.distance(c) + 0.15 for r2, o in CY.items() if r2 != ref)
    ok = False
    for size, gap, bmode in [(0.8, 0.1, True), (0.65, 0.06, True), (0.8, 0.1, 'big'), (0.65, 0.06, 'big')]:
        rt.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size))); rt.SetTextThickness(mm(0.12 if size > 0.7 else 0.11))
        for (x, y, a) in cands:
            rt.SetPosition(bx(x, y)); rt.SetTextAngleDegrees(a)
            rt.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER); rt.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
            g = text_geom(rt)
            if not blocked(g, gap, bodies=bmode) and owned(g):
                placed.append(g); ok = True; break
        if ok:
            if size < 0.8 or bmode != True: print('  ref', ref, size, 'over small body' if bmode != True else '')
            break
    if not ok:
        print('  !! ref fallback (Fab only):', ref); rt.SetLayer(pcbnew.F_Fab)

# ---------- connector / polarity labels ----------
def padpos(ref, num):
    f = b.FindFootprintByReference(ref)
    p = [p for p in f.Pads() if p.GetNumber() == num][0].GetPosition()
    return u(p.x) - OX, u(p.y) - OY
LABELS = [('J1', '1', '+12V'), ('J1', '2', 'GND'), ('J2', '1', 'HEAT+'), ('J2', '2', 'HEAT-'),
          ('J3', '1', 'PWM+'), ('J3', '2', 'PWM-'), ('SW1', '1', 'RST')]
print('labels: (bottom side)')
for ref, num, txt in []:
    x, y = padpos(ref, num)
    cands = []
    for d in [(0, -2.0), (0, 2.0), (-2.6, 0), (2.6, 0), (-3.2, 0), (0, -2.4), (0, 2.4), (-3.8, 0), (3.6, 0), (-2.2, -1.6), (-2.2, 1.6)]:
        cands.append((x + d[0], y + d[1], 0))
    r = place_text(txt, cands, 0.8, bold=True, required=False)
    if not r:
        short = '+' if txt.endswith('+') or txt == '+12V' else '-'
        big = []
        for d in [(-2.0, 0), (-2.3, -1.2), (-2.3, 1.2), (0, -1.9), (0, 1.9), (2.0, 0), (-1.7, -1.7), (-1.7, 1.7), (1.7, 1.7), (1.7, -1.7)]:
            big.append((x + d[0], y + d[1], 0))
        r = place_text(short, big, 1.2, bold=True)
        txt = short
    print('  ', txt, r)

# ---------- bottom-side legend ----------
legend = [
 ('HEATER DRIVER v3', 1.6, True), ('12V / 100W (8.33A)  rev 3.0  2026-10-17', 0.9, False), ('', 0.5, False),
 ('1 ISOLATED PWM IN  PC817, 3.3-5V, <=1kHz', 0.8, False),
 ('2 OCP  10mR Kelvin shunt, trip 11.9A, latch', 0.8, False),
 ('3 GATE DRIVE  TC4427A + 2N7000 fault clamp', 0.8, False),
 ('4 POWER IN  15A ATM fuse + 1.5KE18A TVS', 0.8, False),
 ('5 POWER STAGE  IRF3205 low-side, 1N5822', 0.8, False),
 ('6 UI  RESET, RED=FAULT, GRN=HEAT ON', 0.8, False), ('', 0.5, False),
 ('RED LED latched = overcurrent. Remove cause, press RESET.', 0.7, False),
 ('MCU side is isolated: do NOT tie PWM- to board GND.', 0.7, False),
]
bpads = []
for f in b.GetFootprints():
    for p in f.Pads():
        if p.IsOnLayer(pcbnew.B_Cu) or p.IsOnLayer(pcbnew.B_Mask):
            g = poly_of(p, pcbnew.B_Cu, 0.0)
            if g is not None: bpads.append(g)
    if f.GetReference().startswith('H'):
        c = f.GetPosition(); bpads.append(Point(u(c.x) - OX, u(c.y) - OY).buffer(1.9))
BPADS = unary_union(bpads).buffer(0.2)
bplaced = []
def place_bottom(txt, sz, bold, prefer):
    reg = box(0.5, 0.5, W - 0.5, H - 0.5)
    for (x, y, a) in search(reg, sz, txt, angles=(0,), step=0.25, prefer=prefer):
        t = mk_text(txt, x, y, sz, a, BS, bold)
        g = text_geom(t)
        if INNER.contains(g) and not g.intersects(BPADS) and not any(g.buffer(0.15).intersects(o) for o in bplaced):
            b.Add(t); bplaced.append(g); return (round(x, 2), round(y, 2))
    print('  !! bottom no spot', txt)
print('bottom legend:')
for ref, num, txt in LABELS:
    x, y = padpos(ref, num)
    print('  ', txt, place_bottom(txt, 0.9, True, (x - 3.2 if ref != 'J3' else x + 3.0, y)))
legend = [('HEATER DRIVER v4', 1.0, True, (27, 3)), ('12V 100W 8.3A  REV 4.0', 0.9, True, (27, 6)),
          ('2026-10-17  ALL THROUGH-HOLE', 0.8, False, (27, 8)),
          ('RED LED = OC/OT FAULT', 0.8, False, (27, 31)), ('FIX CAUSE, PRESS RESET', 0.8, False, (27, 33)),
          ('PWM- IS ISOLATED', 0.8, False, (6, 20)), ('NOT BOARD GND', 0.8, False, (6, 22)),
          ('FUSE 15A ATM ONLY', 0.8, False, (42, 9)),
          ('1=ISO PWM IN', 0.8, False, (6, 10)), ('2=OCP 11.9A + OTP 84C', 0.8, False, (12, 27)), ('3=GATE DRIVE', 0.8, False, (25, 22)),
          ('4=PWR IN/PROTECT', 0.8, False, (30, 12)), ('5=POWER STAGE', 0.8, False, (46, 30)), ('6=RESET/LEDS', 0.8, False, (33, 38))]
for txt, sz, bold, pref in legend:
    print('  ', txt, place_bottom(txt, sz, bold, pref))
# hide footprint user texts that collide with pads (e.g. diode 'A' markers)
for f in b.GetFootprints():
    for it in list(f.GraphicalItems()):
        if it.GetClass() == 'PCB_TEXT' and it.GetLayer() == FS and text_geom(it).intersects(PADS.buffer(-0.1)):
            f.Remove(it); print('  removed', f.GetReference(), it.GetText())
# remove dangling track stubs
for _ in range(10):
    b.BuildConnectivity(); conn = b.GetConnectivity(); removed = 0
    for t in list(b.GetTracks()):
        if t.GetClass() == 'PCB_TRACK' and not t.IsLocked() and conn.TestTrackEndpointDangling(t, False):
            print('  removing dangling', t.GetNetname(), round(pcbnew.ToMM(t.GetLength()), 2)); b.Remove(t); removed += 1
    if not removed: break
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(OUT)
print('saved')
