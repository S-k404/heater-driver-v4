import sys, uuid, math, copy, json
sys.path.insert(0, '.')
from sexp import parse, dump, find, find1, Sym
from design import PARTS, CONN, POWER_NETS

OUT = sys.argv[1]
PROJ = 'heater_driver_v4'
SYMDIR = '/usr/share/kicad/symbols/'
U = lambda: str(uuid.uuid5(uuid.NAMESPACE_URL, 'hd3/' + str(next(_ctr))))
import itertools; _ctr = itertools.count()
ROOT = U()
g = lambda n: round(n * 2.54, 4)

# ---------- library symbol loading / flattening ----------
_libs = {}
def libsym(lib_id):
    lib, name = lib_id.split(':')
    if lib not in _libs:
        _libs[lib] = {x[1]: x for x in find(parse(open(SYMDIR + lib + '.kicad_sym').read())[0], 'symbol')}
    s = copy.deepcopy(_libs[lib][name])
    ext = find1(s, 'extends')
    if ext:
        parent = libsym(lib + ':' + ext[1])
        pname = parent[1].split(':')[1]
        props = {p[1]: p for p in find(s, 'property')}
        out = [Sym('symbol'), lib_id]
        for x in parent[2:]:
            if isinstance(x, list) and x[0] == 'property' and x[1] in props:
                out.append(props.pop(x[1]))
            elif isinstance(x, list) and x[0] == 'symbol':
                x = copy.deepcopy(x); x[1] = x[1].replace(pname, name, 1); out.append(x)
            else:
                out.append(x)
        # insert any extra props after last property
        idx = max(i for i, x in enumerate(out) if isinstance(x, list) and x[0] == 'property')
        for p in props.values():
            idx += 1; out.insert(idx, p)
        return out
    s[1] = lib_id
    return s

def pins_of(lib_id, unit):
    s = libsym(lib_id)
    res = {}
    for u in find(s, 'symbol'):
        parts = u[1].rsplit('_', 2)
        un = int(parts[-2])
        if un not in (0, unit): continue
        for p in find(u, 'pin'):
            at = find1(p, 'at')
            res[find1(p, 'number')[1]] = (float(at[1]), float(at[2]), float(at[3]), find1(p, 'name')[1], str(p[1]))
    return res

def xf(x, y, rot, px, py):
    a = math.radians(rot)
    rx = px * math.cos(a) - py * math.sin(a)
    ry = px * math.sin(a) + py * math.cos(a)
    return round(x + rx, 4), round(y - ry, 4)

# ---------- placement (x, y in grid units, rot) ----------
P = {
 # ISOLATED INPUT block
 'J3': (14, 24, 180), 'R1': (24, 21, 0), 'D2': (30, 27, 270), 'U2': (40, 24, 0),
 'R2': (52, 21, 0), 'R3': (58, 27, 0),
 # GATE DRIVE block
 'U1': (82, 26, 0), 'C2': (74, 16, 0), 'R4': (98, 21, 0),
 'R5': (104, 29, 0), 'ZD1': (110, 29, 270), 'Q2': (70, 38, 0),
 # POWER INPUT / PROTECTION block
 'J1': (126, 22, 180), 'F1': (134, 18, 0), 'TVS1': (140, 26, 270), 'C1': (146, 26, 0),
 # POWER STAGE block
 'J2': (126, 48, 180), 'D1': (136, 48, 270), 'R16': (142, 44, 0), 'D4': (142, 53, 90),
 'Q1': (150, 50, 0), 'RS1': (154, 64, 0),
 # OVERCURRENT LATCH block
 'R6': (16, 66, 0), 'R7': (16, 76, 0), 'C5': (22, 76, 0), 'R8': (30, 64, 0), 'C6': (36, 70, 0),
 'U3A': (50, 68, 0), 'U3B': (82, 68, 0), 'U3E': (106, 68, 0), 'C4': (112, 68, 0),
 'R18': (124, 87, 0), 'TH1': (124, 94, 0), 'R19': (131, 87, 0), 'R20': (136, 93, 0), 'C9': (141, 93, 0), 'U3C': (152, 87, 0), 'U3D': (152, 93, 0),
 'R9': (64, 62, 0), 'R10': (64, 74, 0), 'C8': (70, 74, 0),
 'R11': (94, 56, 0), 'R12': (94, 80, 0), 'C7': (99, 80, 0), 'R13': (100, 64, 90),
 'R14': (70, 92, 0), 'SW1': (78, 98, 0), 'R17': (88, 101, 0), 'R15': (100, 92, 0), 'D3': (100, 101, 90),
 # MECH
 'H1': (130, 78, 0), 'H2': (140, 78, 0),
}
UNITS = {'U3A': ('U3', 1), 'U3B': ('U3', 2), 'U3C': ('U3', 3), 'U3D': ('U3', 4), 'U3E': ('U3', 5)}

BLOCKS = [
 ('1  ISOLATED PWM INPUT  (MCU side | power side)', 6, 10, 64, 44),
 ('2  GATE DRIVE + FAULT SHUTDOWN', 66, 10, 118, 44),
 ('3  POWER INPUT + PROTECTION', 120, 10, 160, 34),
 ('4  POWER STAGE (8.33 A)', 120, 36, 160, 72),
 ('5  OVERCURRENT TRIP (11.9 A) + LATCH', 6, 48, 118, 108),
 ('MECHANICAL', 120, 74, 160, 81.5),
 ('6  OVER-TEMPERATURE SHUTDOWN (~84 C)', 120, 82, 160, 97.5),
]
NOTES = [
 (8, 86, [
  'HEATER DRIVER v4 - DESIGN NOTES',
  'Load: 12 V / 100 W resistive heater, 8.33 A nominal.',
  'Q1 IRFB7430: 1.3 mOhm max @ Vgs 10 V -> 0.09 W @ 25C, ~0.15 W hot. Runs cold, no heatsink.',
  'RS1 OAR-3 10 mOhm open-air strap: 0.69 W @ 8.33 A (3 W part). Kelvin sense pads SH_P / SH_N.',
  'OTP: TH1 NTC beside RS1/Q1. Above ~84 C U3C pulls TRIP_N low -> same latch, red LED.',
  'Trip: VREF = 12 V x 1k/101k = 119 mV -> 11.9 A. Ratiometric with supply',
  '   (heater current also scales with V), so trip margin stays ~43 %.',
  'Latch: U3A pulls TRIP_N low -> U3B FAULT high -> Q2 clamps DRV_IN, U1B lights D3.',
  '   P(normal)=4.0 V < N=6.0 V < P(latched)=7.9 V. RESET lifts N to 10.2 V via R17;',
  '   if the short is still there U3A holds N low, so protection stays active.',
  'Input: PC817 emitter follower = NON-inverting; MCU off/unplugged = heater OFF.',
  '   R1 330R: 6.4 mA @ 3.3 V, 11.5 mA @ 5 V. Recommended PWM <= 1 kHz.',
  'Isolation: J3/R1/D2/U2(pins 1-2) are on MCU ground (PWM_N), NOT board GND.',
  ]),
]

items = []
lib_used = {}
nets_at = []   # (net, x, y, outward_angle)
pwr_ctr = itertools.count(1)

def prop(name, val, x, y, hide=False, just=None, angle=0, size=1.27):
    eff = [Sym('effects'), [Sym('font'), [Sym('size'), size, size]]]
    if just: eff.append([Sym('justify')] + [Sym(j) for j in just.split()])
    if hide: eff.append([Sym('hide'), Sym('yes')])
    return [Sym('property'), name, val, [Sym('at'), x, y, angle], eff]

def place_symbol(lib_id, ref, unit, x, y, rot, value, fp='', fields=None, in_bom=True, pins=None, ref_off=None, val_off=None, hide_ref=False, hide_val=False):
    lib_used[lib_id] = libsym(lib_id)
    ro = ref_off or (2.54, -1.27, 'left'); vo = val_off or (2.54, 1.27, 'left')
    s = [Sym('symbol'), [Sym('lib_id'), lib_id], [Sym('at'), x, y, rot], [Sym('unit'), unit],
         [Sym('exclude_from_sim'), Sym('no')], [Sym('in_bom'), Sym('yes' if in_bom else 'no')],
         [Sym('on_board'), Sym('yes')], [Sym('dnp'), Sym('no')], [Sym('uuid'), U()],
         prop('Reference', ref, x + ro[0], y + ro[1], just=ro[2], hide=hide_ref),
         prop('Value', value, x + vo[0], y + vo[1], just=vo[2], hide=hide_val),
         prop('Footprint', fp, x, y, hide=True),
         prop('Datasheet', '~', x, y, hide=True),
         prop('Description', '', x, y, hide=True)]
    for k, v in (fields or {}).items():
        s.append(prop(k, v, x, y, hide=True))
    for pn in (pins or {}):
        s.append([Sym('pin'), pn, [Sym('uuid'), U()]])
    s.append([Sym('instances'), [Sym('project'), PROJ, [Sym('path'), '/' + ROOT, [Sym('reference'), ref], [Sym('unit'), unit]]]])
    items.append(s)

def power_symbol(net, x, y, out_ang):
    n = next(pwr_ctr)
    if net == 'GND':
        rot = {270: 0, 0: 90, 90: 180, 180: 270}[out_ang]
        place_symbol('power:GND', '#PWR%02d' % n, 1, x, y, rot, 'GND', in_bom=False, pins={'1': 0},
                     ref_off=(0, 6.35, 'left'), val_off=(0, 3.81, ''), hide_ref=True)
    else:
        rot = {90: 0, 180: 90, 270: 180, 0: 270}[out_ang]
        place_symbol('power:+12V', '#PWR%02d' % n, 1, x, y, rot, '+12V', in_bom=False, pins={'1': 0},
                     ref_off=(0, -6.35, 'left'), val_off=(0, -3.81, ''), hide_ref=True)
    # rotated value text: keep simple, centered
    s = items[-1]
    for p in find(s, 'property'):
        if p[1] == 'Value':
            ox, oy = {0: (0, 1), 90: (1, 0), 180: (0, -1), 270: (-1, 0)}[out_ang]
            p[3] = [Sym('at'), round(x + ox * 5.08, 4), round(y - oy * 5.08, 4), 0]

def label(net, x, y, ang):
    just = 'left bottom' if ang in (0, 90) else 'right bottom'
    items.append([Sym('label'), net, [Sym('at'), x, y, ang], [Sym('fields_autoplaced'), Sym('yes')],
                  [Sym('effects'), [Sym('font'), [Sym('size'), 1.27, 1.27]], [Sym('justify')] + [Sym(j) for j in just.split()]],
                  [Sym('uuid'), U()]])

def wire(x1, y1, x2, y2):
    items.append([Sym('wire'), [Sym('pts'), [Sym('xy'), x1, y1], [Sym('xy'), x2, y2]],
                  [Sym('stroke'), [Sym('width'), 0], [Sym('type'), Sym('default')]], [Sym('uuid'), U()]])

STUB = 2.54
DIRECT = {'LED_ST': [], 'FLED_A': []}
for key, (gx, gy, rot) in P.items():
    ref, unit = UNITS.get(key, (key, 1))
    lib_id, value, fp, mpn, desc, block = PARTS[ref]
    x, y = g(gx), g(gy)
    pins = pins_of(lib_id, unit)
    ic = ref.startswith('U') or ref.startswith('Q')
    two_vert = lib_id.split(':')[1] in ('R', 'C', 'C_Polarized', 'Fuse') and rot == 0
    if two_vert:
        ro, vo = (2.54, -1.27, 'left'), (2.54, 1.27, 'left')
    elif ref.startswith('J'):
        ro, vo = (-2.54, -5.08, 'right'), (-2.54, 5.08, 'right')
    elif ic:
        ro, vo = (2.54, -10.16 if ref == 'U1' else -6.35, 'left'), (2.54, 10.16 if ref == 'U1' else 6.35, 'left')
        if key == 'U3E': ro, vo = (2.54, -2.54, 'left'), (2.54, 0, 'left')
        if key in ('U3C', 'U3D'): ro, vo = (6.35, -3.81, 'left'), (6.35, 3.81, 'left')
    elif ref.startswith('H'):
        ro, vo = (0, -3.81, ''), (0, 3.81, '')
    elif ref == 'SW1':
        ro, vo = (0, -3.81, ''), (0, 3.81, '')
    elif ref == 'RS1':
        ro, vo = (2.54, -6.35, 'left'), (2.54, 6.35, 'left')
    else:
        ro, vo = (2.54, -1.27, 'left'), (2.54, 1.27, 'left')
    fields = {'MPN': mpn, 'Description2': desc, 'Block': block}
    if rot in (90, 270) and not ref.startswith('U'):
        if ref == 'R13':
            ro, vo = (0, -2.54, ''), (0, 2.54, '')
        else:
            ro, vo = (6.35, -1.27, ''), (6.35, 1.27, '')
    place_symbol(lib_id, ref, unit, x, y, rot, value, fp, fields, in_bom=not ref.startswith('H'),
                 pins=pins, ref_off=ro, val_off=vo)
    if rot in (90, 270):
        for p in find(items[-1], 'property'):
            p[3][3] = rot
    # set Description property
    for p in find(items[-1], 'property'):
        if p[1] == 'Description': p[2] = desc
    items[-1] = [x for x in items[-1] if not (isinstance(x, list) and x[0] == 'property' and x[1] == 'Description2')]
    for pn, (px, py, pa, pname, ptype) in pins.items():
        net = CONN[ref].get(pn)
        cx, cy = xf(x, y, rot, px, py)
        out = int(round((pa + 180 + rot) % 360))
        if net is None:
            if ptype != 'no_connect':
                items.append([Sym('no_connect'), [Sym('at'), cx, cy], [Sym('uuid'), U()]])
            continue
        dx, dy = {0: (1, 0), 90: (0, -1), 180: (-1, 0), 270: (0, 1)}[out]
        if net in DIRECT:
            DIRECT[net].append((cx, cy)); continue
        st = 10.16 if (ref.startswith('J') and net in POWER_NETS) else STUB
        ex, ey = round(cx + dx * st, 4), round(cy + dy * st, 4)
        wire(cx, cy, ex, ey)
        if net in POWER_NETS:
            power_symbol(net, ex, ey, out)
        else:
            label(net, ex, ey, out)

for net, pts in DIRECT.items():
    (x1, y1), (x2, y2) = pts
    assert x1 == x2 or y1 == y2, net
    wire(x1, y1, x2, y2)
    label(net, x1, round((y1 + y2) / 2, 2) if x1 == x2 else y1, 0) if x1 == x2 else label(net, round((x1 + x2) / 2, 2), y1, 0)

# PWR_FLAGs on +12V and GND (near power entry)
for i, net in enumerate(['+12V', 'GND']):
    x, y = g(150 + i * 6), g(14)
    place_symbol('power:PWR_FLAG', '#FLG%02d' % (i + 1), 1, x, y, 0, 'PWR_FLAG', in_bom=False, pins={'1': 0},
                 ref_off=(0, -6.35, ''), val_off=(0, -3.81, ''), hide_ref=True)
    wire(x, y, x, y + 2.54)
    if net == 'GND': power_symbol('GND', x, y + 2.54, 270)
    else:
        power_symbol('+12V', x, y + 2.54, 270)

for title, x1, y1, x2, y2 in BLOCKS:
    items.append([Sym('rectangle'), [Sym('start'), g(x1), g(y1)], [Sym('end'), g(x2), g(y2)],
                  [Sym('stroke'), [Sym('width'), 0.3], [Sym('type'), Sym('dash')]], [Sym('fill'), [Sym('type'), Sym('none')]], [Sym('uuid'), U()]])
    items.append([Sym('text'), title, [Sym('exclude_from_sim'), Sym('no')], [Sym('at'), g(x1) + 1.27, g(y1) + 3.0, 0],
                  [Sym('effects'), [Sym('font'), [Sym('size'), 2.0, 2.0], [Sym('thickness'), 0.4], [Sym('bold'), Sym('yes')]], [Sym('justify'), Sym('left'), Sym('bottom')]], [Sym('uuid'), U()]])
# isolation barrier line in block 1
items.append([Sym('polyline'), [Sym('pts'), [Sym('xy'), g(44), g(13)], [Sym('xy'), g(44), g(43)]],
              [Sym('stroke'), [Sym('width'), 0.5], [Sym('type'), Sym('dash_dot')]], [Sym('uuid'), U()]])
items.append([Sym('text'), 'ISOLATION BARRIER (5 kVrms)', [Sym('exclude_from_sim'), Sym('no')], [Sym('at'), g(44) - 1, g(42), 90],
              [Sym('effects'), [Sym('font'), [Sym('size'), 1.27, 1.27]], [Sym('justify'), Sym('left'), Sym('bottom')]], [Sym('uuid'), U()]])
for x, y, lines in NOTES:
    items.append([Sym('text'), '\n'.join(lines), [Sym('exclude_from_sim'), Sym('no')], [Sym('at'), g(x), g(y), 0],
                  [Sym('effects'), [Sym('font'), [Sym('size'), 1.27, 1.27]], [Sym('justify'), Sym('left'), Sym('top')]], [Sym('uuid'), U()]])

doc = [Sym('kicad_sch'), [Sym('version'), 20250114], [Sym('generator'), 'eeschema'], [Sym('generator_version'), '9.0'],
       [Sym('uuid'), ROOT], [Sym('paper'), 'A3'],
       [Sym('title_block'), [Sym('title'), 'Heater Driver 12 V / 100 W - v4 (All-THT, Isolated, OCP + OTP Latch)'],
        [Sym('date'), '2026-10-17'], [Sym('rev'), '4.0'], [Sym('company'), 'MosfetHeater'],
        [Sym('comment'), 1, 'v4: IRFB7430 1.3 mOhm, OAR-3 THT Kelvin shunt, LM339 OCP+OTP, safe RESET'],
        [Sym('comment'), 2, 'v4: 100 % through-hole parts. 2-layer 1 oz. Over-temperature + overcurrent latch.']],
       [Sym('lib_symbols')] + list(lib_used.values())]
doc += items
doc += [[Sym('sheet_instances'), [Sym('path'), '/', [Sym('page'), '1']]], [Sym('embedded_fonts'), Sym('no')]]
open(OUT, 'w').write(dump(doc) + '\n')
json.dump({'root': ROOT}, open(OUT + '.meta.json', 'w'))
print('ok', len(items))
