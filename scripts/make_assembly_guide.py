"""Build the v4 placement / assembly guide (HTML -> PDF) from the real board file.

Usage: python3 make_assembly_guide.py <board.kicad_pcb> <out.html>
Every coordinate, orientation and value comes from the KiCad board, so the guide
always matches the Gerbers.
"""
import sys, io, base64, math
import pcbnew
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Polygon as MPoly

BOARD, OUT = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(BOARD)
u = pcbnew.ToMM
OX, OY = 100.0, 100.0
bb = b.GetBoardEdgesBoundingBox()
W, H = u(bb.GetWidth()), u(bb.GetHeight())

SUB = {   # subsystem of each part (matches silkscreen numbers 1-6)
    '1 Isolated PWM input': ['J3', 'R1', 'D2', 'U2'],
    '2 Overcurrent + over-temp latch': ['U3', 'R6', 'R7', 'C5', 'C9', 'R8', 'R9', 'R10', 'C6', 'C8', 'R11', 'R12', 'R13',
                                        'C7', 'C4', 'R17', 'R18', 'R19', 'R20', 'TH1'],
    '3 Gate drive': ['U1', 'C2', 'R2', 'R3', 'Q2', 'R14', 'R4', 'R5', 'ZD1'],
    '4 Power in + protection': ['J1', 'F1', 'C1', 'TVS1', 'D1', 'D4', 'R16'],
    '5 Power stage': ['J2', 'Q1', 'RS1'],
    '6 UI': ['SW1', 'R15', 'D3'],
    'Mechanical': ['H1', 'H2'],
}
COL = {'1': '#3b82f6', '2': '#a855f7', '3': '#10b981', '4': '#f59e0b', '5': '#ef4444', '6': '#0ea5e9', 'M': '#6b7280'}
sub_of = {r: s for s, refs in SUB.items() for r in refs}

# what to tell the builder, by part type
def howto(ref, val):
    t = ref.rstrip('0123456789')
    if ref == 'RS1':
        return ('Not polarized. Open-air metal strap: push fully down so it stands vertical, solder both legs with plenty of solder '
                '(8 A flows here). The two small copper squares next to the legs are the Kelvin sense points - do not bridge them.')
    if ref == 'TH1':
        return 'Not polarized. Leave ~3 mm of lead and bend the bead so it leans against the RS1 strap / Q1 copper (a dab of thermal epoxy is ideal).'
    if ref == 'Q1':
        return ('Pin 1 = GATE = SQUARE pad (rightmost). Printed face toward J2 (up), METAL TAB faces DOWN toward R5/ZD1. '
                'Stand it straight, no heatsink needed (~0.1 W).')
    if ref == 'Q2':
        return 'Pin 1 = SOURCE = SQUARE pad (left). FLAT face of the TO-92 matches the flat side of the silkscreen outline (facing down, toward R14).'
    if ref.startswith('U'):
        return 'Pin 1 = SQUARE pad, top-left. Notch / dot on the IC toward the notch on the silkscreen. A DIP socket is fine.'
    if ref == 'C1':
        return 'POLARIZED. Long lead (+) into the SQUARE pad marked "+". The stripe on the can is the minus (-) side.'
    if t == 'C':
        return 'Not polarized. Push down until the coating just touches the board.'
    if ref in ('D3', 'D4'):
        return 'POLARIZED LED. Short leg / flat edge (cathode, K) into the SQUARE pad. Long leg into the round pad.'
    if t in ('D', 'ZD', 'TVS'):
        return ('POLARIZED, mounted standing. Body sits on the SQUARE pad: put the BANDED end (cathode) down into the square pad, '
                'bend the other lead back down into the round pad.')
    if t == 'R':
        return ('Not polarized. Mounted standing (2.54 mm): body upright over the pad inside the silkscreen circle, '
                'bend the top lead down into the other pad.')
    if t == 'J':
        return 'Wire openings face the board edge. Seat flat and solder both pins generously (J1/J2 carry 8 A).'
    if ref == 'F1':
        return 'Fuse holder: 4 pins, fits one way. Plug in a 15 A ATM mini blade fuse only after the step-6 checks.'
    if ref == 'SW1':
        return '6 mm tact switch: the legs only fit in two ways, both are correct. Press flat before soldering.'
    if t == 'H':
        return 'M3 mounting hole (no part). Use M3 nylon or metal standoffs.'
    return ''

ORDER = [  # solder lowest parts first
    ('1. Resistors (standing)', lambda r: r.rstrip('0123456789') == 'R' and r != 'RS1'),
    ('2. Small diodes', lambda r: r in ('D2', 'ZD1')),
    ('3. Ceramic capacitors', lambda r: r in ('C4', 'C5', 'C6', 'C7', 'C8', 'C9', 'C2')),
    ('4. ICs / sockets', lambda r: r.startswith('U')),
    ('5. Transistor Q2, LEDs, NTC', lambda r: r in ('Q2', 'D3', 'D4', 'TH1')),
    ('6. Switch', lambda r: r == 'SW1'),
    ('7. Big diodes TVS1, D1', lambda r: r in ('TVS1', 'D1')),
    ('8. Electrolytic C1', lambda r: r == 'C1'),
    ('9. MOSFET Q1, shunt RS1', lambda r: r in ('Q1', 'RS1')),
    ('10. Fuse holder, terminals', lambda r: r in ('F1', 'J1', 'J2', 'J3')),
]
def step(ref):
    for i, (name, f) in enumerate(ORDER):
        if f(ref): return i + 1, name
    return 99, 'Mechanical'

fps = {f.GetReference(): f for f in b.GetFootprints()}

def pkg(fp):
    for key, name in [('R_Axial_DIN0207', '1/4 W axial, standing (2.54 mm)'), ('C_Disc_D3.0mm_W2.0mm', 'NTC disc (2.5 mm)'),
                      ('C_Disc', 'ceramic disc (2.5 mm)'), ('C_Rect', 'radial MLCC (2.5 mm)'), ('CP_Radial_D6.3mm', 'electrolytic 6.3 mm (2.5 mm)'),
                      ('DIP-14', 'DIP-14'), ('DIP-8', 'DIP-8'), ('DIP-4', 'DIP-4'), ('DO-35', 'DO-35, standing'), ('DO-41', 'DO-41, standing'),
                      ('DO-201AD', 'DO-201AD, standing'), ('LED_D3.0mm', '3 mm LED'), ('TO-92', 'TO-92'), ('TO-220', 'TO-220, vertical'),
                      ('MKDS', '5.08 mm screw terminal'), ('MPT', '2.54 mm screw terminal'), ('Fuseholder', 'mini blade fuse holder'),
                      ('SW_PUSH_6mm', '6 mm tact switch'), ('OAR3', 'OAR-3 open-air strap (15.24 mm)'), ('MountingHole', 'M3 hole')]:
        if key in fp: return name
    return fp

def cy_rect(f):
    c = f.GetCourtyard(pcbnew.F_CrtYd).BBox()
    return u(c.GetLeft()) - OX, u(c.GetTop()) - OY, u(c.GetWidth()), u(c.GetHeight())

def draw_board(ax, highlight=None, labels=True, fs=6.0):
    ax.add_patch(Rectangle((0, 0), W, H, fc='#0f5132', ec='#222', lw=1.2))
    for ref, f in fps.items():
        x, y, w, h = cy_rect(f)
        key = sub_of.get(ref, 'Mechanical')[0]
        c = COL.get(key if key != 'M' else 'M', '#888')
        if highlight and ref == highlight:
            ax.add_patch(Circle((x + w / 2, y + h / 2), max(w, h) / 2 + 2.6, fc='none', ec='#ffea00', lw=2.6, zorder=9))
        if highlight:
            hl = ref == highlight
            ax.add_patch(Rectangle((x, y), w, h, fc=('#ff2d2d' if hl else '#2d6a4f'), ec=('#fff' if hl else '#1b4332'),
                                   lw=(1.6 if hl else 0.4), alpha=(0.95 if hl else 0.8), zorder=(5 if hl else 2)))
        else:
            ax.add_patch(Rectangle((x, y), w, h, fc=c, ec='#111', lw=0.4, alpha=0.55, zorder=2))
        for p in f.Pads():
            px, py = u(p.GetPosition().x) - OX, u(p.GetPosition().y) - OY
            sq = p.GetShape() in (pcbnew.PAD_SHAPE_RECT, pcbnew.PAD_SHAPE_ROUNDRECT)
            r = max(0.35, min(u(p.GetSize().x), u(p.GetSize().y)) / 2)
            fc = '#ffd166' if (not highlight or ref == highlight) else '#b7c4bb'
            if sq: ax.add_patch(Rectangle((px - r, py - r), 2 * r, 2 * r, fc=fc, ec='#333', lw=0.3, zorder=6))
            else: ax.add_patch(Circle((px, py), r, fc=fc, ec='#333', lw=0.3, zorder=6))
        if labels and (not highlight or ref == highlight):
            ax.text(x + w / 2, y + h / 2, ref, ha='center', va='center', fontsize=fs, weight='bold', zorder=8,
                    color='white' if highlight else '#111',
                    bbox=dict(boxstyle='round,pad=0.12', fc=('#000000aa' if highlight else '#ffffffcc'), ec='none'))
    ax.set_xlim(-0.5, W + 0.5); ax.set_ylim(H + 0.5, -0.5); ax.set_aspect('equal'); ax.axis('off')

def png(fig, dpi):
    bio = io.BytesIO(); fig.savefig(bio, format='png', dpi=dpi, bbox_inches='tight', pad_inches=0.05); plt.close(fig)
    return 'data:image/png;base64,' + base64.b64encode(bio.getvalue()).decode()

# ---------- overview map ----------
fig, ax = plt.subplots(figsize=(10.5, 8.2))
draw_board(ax, labels=True, fs=7.5)
ax.text(0.3, H + 0.3, 'top view, board edge %.0f x %.0f mm - origin (0,0) = bottom-left corner' % (W, H), fontsize=8, va='top', color='#333')
overview = png(fig, 140)

rows = []
for ref, f in fps.items():
    pos = f.GetPosition()
    x, y = u(pos.x) - OX, H - (u(pos.y) - OY)       # Y measured up from the bottom edge
    val = f.GetValue()
    mpn = f.GetFieldText('MPN') if f.HasFieldByName('MPN') else ''
    fpn = pkg(str(f.GetFPID().GetLibItemName()))
    st, stname = step(ref)
    rows.append(dict(ref=ref, val=val, mpn=mpn, fp=fpn, x=x, y=y, rot=f.GetOrientationDegrees() % 360,
                     sub=sub_of.get(ref, 'Mechanical'), step=st, stepname=stname, how=howto(ref, val),
                     tht=(f.GetAttributes() & pcbnew.FP_THROUGH_HOLE) != 0 or ref.startswith('H')))
def natkey(r):
    t = r['ref'].rstrip('0123456789'); n = r['ref'][len(t):]
    return (t, int(n) if n else 0)
rows.sort(key=lambda r: (r['step'], natkey(r)))

cards = []
for r in rows:
    fig, ax = plt.subplots(figsize=(3.3, 2.6))
    draw_board(ax, highlight=r['ref'], fs=9)
    cards.append((r, png(fig, 90)))

all_tht = all(r['tht'] for r in rows)
esc = lambda s: s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

html = ['''<!doctype html><html><head><meta charset="utf-8"><title>Heater Driver v4 - Placement Guide</title><style>
@page{size:A4;margin:11mm 11mm}
body{font-family:Helvetica,Arial,sans-serif;font-size:9pt;color:#111}
h1{font-size:17pt;margin:0}
h2{font-size:12pt;margin:10px 0 5px;border-bottom:1.5px solid #333;padding-bottom:2px}
.sub{color:#555;margin:2px 0 8px}
table{border-collapse:collapse;width:100%}
th,td{border:1px solid #aaa;padding:2px 4px;vertical-align:top;font-size:8pt}
table.pl td:nth-child(9){width:38%}
table.pl td:nth-child(4){width:15%}
th{background:#eee;text-align:left}
.k{display:inline-block;width:10px;height:10px;border:1px solid #333;margin-right:4px;vertical-align:middle}
.cards{display:grid;grid-template-columns:1fr 1fr;gap:7px}
.card{border:1px solid #999;border-radius:5px;padding:5px;break-inside:avoid;display:flex;gap:6px}
.card img{width:46%;height:auto;border-radius:3px}
.card .t{font-size:8.3pt;line-height:1.3}
.ref{font-size:13pt;font-weight:bold}
.pol{color:#b00;font-weight:bold}
.pb{break-before:page}
.note{border:1.5px solid #0a7;background:#effaf5;padding:6px 8px;margin:6px 0}
</style></head><body>''']
html.append('<h1>Heater Driver v4 &mdash; Component Placement &amp; Assembly Guide</h1>')
html.append('<div class="sub">12 V / 100 W (8.33 A) &middot; rev 4.0 &middot; board %.0f &times; %.0f mm, 2 layers &middot; %d parts on %d footprints &middot; generated from heater_driver_v4.kicad_pcb</div>' % (W, H, len([r for r in rows if not r['ref'].startswith('H')]), len(rows)))
html.append('<div class="note"><b>%s</b> Every component is a through-hole part, so you only need a soldering iron (60&ndash;80 W tip for J1/J2/RS1/F1), 0.8 mm solder and flush cutters. '
            'Fit the parts in the numbered order below (lowest first) so the board lies flat while you solder. '
            'Square pad = pin 1 / cathode / + on every part.</div>' % ('100 % THROUGH-HOLE.' if all_tht else 'NOTE: not all parts are THT.'))
html.append('<h2>Board map (top side, parts coloured by subsystem)</h2><img src="%s" style="width:100%%">' % overview)
html.append('<div>' + ' &nbsp; '.join('<span class="k" style="background:%s"></span>%s' % (COL[s[0] if s[0] != 'M' else 'M'], esc(s)) for s in SUB) + '</div>')

html.append('<h2 class="pb">Solder order &amp; shopping list</h2><table><tr><th>Step</th><th>Parts</th></tr>')
for i, (name, f) in enumerate(ORDER):
    refs = [r['ref'] for r in rows if r['step'] == i + 1]
    html.append('<tr><td>%s</td><td>%s</td></tr>' % (esc(name), ', '.join(refs)))
html.append('</table>')
html.append('<h2>Complete placement table</h2><table class="pl"><tr><th>#</th><th>Ref</th><th>Value</th><th>Part number</th><th>Package (THT)</th><th>X mm</th><th>Y mm</th><th>Subsystem</th><th>Orientation / polarity</th></tr>')
for r in rows:
    pol = any(w in r['how'] for w in ('POLARIZED', 'Pin 1'))
    html.append('<tr><td>%d</td><td><b>%s</b></td><td>%s</td><td>%s</td><td>%s</td><td>%.1f</td><td>%.1f</td><td>%s</td><td>%s%s</td></tr>' % (
        r['step'], r['ref'], esc(r['val']), esc(r['mpn']), esc(r['fp']), r['x'], r['y'], esc(r['sub']),
        '<span class="pol">&#9888; </span>' if pol else '', esc(r['how'])))
html.append('</table><div class="sub">X/Y = position of the part origin (pin 1 for through-hole parts) measured from the bottom-left board corner, Y up.</div>')

html.append('<h2 class="pb">Where each component goes (one card per part, in solder order)</h2><div class="cards">')
for r, img in cards:
    pol = any(w in r['how'] for w in ('POLARIZED', 'Pin 1'))
    html.append('<div class="card"><img src="%s"><div class="t"><div class="ref">%s</div><b>%s</b><br>%s<br>'
                '<span style="color:#555">%s</span><br>X %.1f / Y %.1f mm &middot; step %d<br>%s%s</div></div>' % (
        img, r['ref'], esc(r['val']), esc(r['mpn']), esc(r['fp']), r['x'], r['y'], r['step'],
        '<span class="pol">&#9888; </span>' if pol else '', esc(r['how'])))
html.append('</div>')
html.append('<h2 class="pb">Before first power-up</h2><ol>'
            '<li>Inspect every joint; no bridges between the IC pins or the RS1 sense squares and the big pads.</li>'
            '<li>Check every polarity marked &#9888; above against this guide (C1, D1&ndash;D4, ZD1, TVS1, U1&ndash;U3, Q1, Q2).</li>'
            '<li>Follow <i>heater_driver_v4_test_checklist.pdf</i> steps 1&ndash;12 with the fuse REMOVED / current-limited supply, then fit the 15 A ATM fuse.</li>'
            '<li>Wire: J1 = 12 V supply (+12V / GND as printed underneath), J2 = heater, J3 = MCU PWM (PWM+ / PWM- = MCU ground; it is isolated).</li></ol>')
html.append('</body></html>')
open(OUT, 'w').write('\n'.join(html))
print('ok', len(rows), 'parts, all THT:', all_tht)
