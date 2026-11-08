import pcbnew, sys, json, re
sys.path.insert(0, '.')
from design import PARTS, CONN, POWER_NETS
def KNET(n):
    return n if n in POWER_NETS else '/' + n
FPDIR = '/usr/share/kicad/footprints/'
import os
PRJ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..')) + '/'
mm = pcbnew.FromMM
OX, OY = 100.0, 100.0   # board origin in KiCad coords
def V(x, y): return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))

def sch_uuids():
    """map ref -> symbol uuid from the schematic, for footprint<->symbol linking"""
    t = open(PRJ + 'heater_driver_v4.kicad_sch').read()
    res = {}
    for m in re.finditer(r'\(symbol\s*\(lib_id "([^"]+)"\)[\s\S]*?\(uuid "([^"]+)"\)\s*\(property "Reference" "([^"]+)"', t):
        if not m.group(3).startswith('#'):
            res.setdefault(m.group(3), m.group(2))
    return res

def load_fp(fpid):
    lib, name = fpid.split(':')
    d = PRJ + 'HeaterDriver.pretty' if lib == 'HeaterDriver' else FPDIR + lib + '.pretty'
    f = pcbnew.FootprintLoad(d, name)
    f.SetFPID(pcbnew.LIB_ID(lib, name))
    return f

def build(board, place):
    nets = {}
    def net(n):
        if n not in nets:
            ni = pcbnew.NETINFO_ITEM(board, KNET(n)); board.Add(ni); nets[n] = ni
        return nets[n]
    uu = sch_uuids()
    fps = {}
    for ref, (lib_id, value, fpid, mpn, desc, block) in PARTS.items():
        f = load_fp(fpid)
        f.SetReference(ref); f.SetValue(value)
        f.SetPath(pcbnew.KIID_PATH('/' + uu[ref]))
        f.SetField('MPN', mpn); f.GetFieldByName('MPN').SetVisible(False)
        x, y, rot, side = (place[ref] + ('F',))[:4]
        board.Add(f)
        f.SetPosition(V(x, y))
        f.SetOrientationDegrees(rot)
        if side == 'B': f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        for p in f.Pads():
            n = CONN[ref].get(p.GetNumber())
            if n: p.SetNet(net(n))
            elif p.GetNumber() in CONN[ref]:   # explicit no-connect pin: match schematic's auto net name
                nn = ('unconnected-(%s-NC-Pad%s)' if ref == 'U1' else 'unconnected-(%s-Pad%s)') % (ref, p.GetNumber())
                if nn not in nets:
                    ni = pcbnew.NETINFO_ITEM(board, nn); board.Add(ni); nets[nn] = ni
                p.SetNet(nets[nn])
        fps[ref] = f
    return fps, nets
