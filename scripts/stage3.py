"""Stage 3: copper pours, pad connection overrides, fill."""
import pcbnew, sys
from pcb_lib import OX, OY, mm, KNET
import place
IN, OUT = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(IN)
W, H = place.W, place.H
F, B = pcbnew.F_Cu, pcbnew.B_Cu
net = lambda n: b.FindNet(KNET(n))
ds = b.GetDesignSettings(); ds.m_CopperEdgeClearance = mm(0.25)
for z in list(b.Zones()):            # routing-only keepout is not needed in the final board
    if z.GetIsRuleArea() and z.GetZoneName() == 'HEATN_BOTTOM_KEEPOUT': b.Remove(z)

def zone(name, netname, layers, pts, prio, thermal=True, min_w=0.25):
    z = pcbnew.ZONE(b); z.SetZoneName(name); z.SetNet(net(netname))
    ls = pcbnew.LSET()
    for l in layers: ls.AddLayer(l)
    z.SetLayerSet(ls); z.SetAssignedPriority(prio)
    z.SetLocalClearance(mm(0.3)); z.SetMinThickness(mm(min_w))
    z.SetThermalReliefGap(mm(0.4)); z.SetThermalReliefSpokeWidth(mm(0.8))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL if thermal else pcbnew.ZONE_CONNECTION_FULL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    ol = z.Outline(); ol.NewOutline()
    for x, y in pts: ol.Append(mm(OX + x), mm(OY + y))
    b.Add(z); return z

E = 0.0
board_pts = [(E, E), (W - E, E), (W - E, H - E), (E, H - E)]
# power-side ground everywhere except the MCU (isolated) corner
gnd_pts = [(13.0, 0), (W, 0), (W, H), (0, H), (0, 20.0), (13.0, 20.0)]
zone('GND_B', 'GND', [B], gnd_pts, 0)
zone('GND_F', 'GND', [F], gnd_pts, 0)
zone('VIN', 'VIN', [F, B], [(37.9, 0.3), (53.7, 0.3), (53.7, 6.4), (37.9, 6.4)], 5, thermal=False)
zone('P12V_A', '+12V', [F], [(26.9, 0.3), (37.2, 0.3), (37.2, 7.3), (26.9, 7.3)], 5, thermal=False)
zone('P12V_B', '+12V', [F], [(21.8, 7.4), (34.6, 7.4), (34.6, 13.4), (21.8, 13.4)], 5, thermal=False)
zone('P12V_C', '+12V', [F, B], [(34.6, 13.4), (47.4, 13.4), (47.4, 17.6), (34.6, 17.6)], 4, thermal=False)
zone('HEATN', 'HEAT_N', [F, B], [(35.5, 19.0), (53.6, 19.0), (53.6, 23.5), (50.15, 23.5), (50.15, 26.4), (47.3, 26.4), (47.3, 23.5), (44.5, 23.5), (44.5, 22.2), (35.5, 22.2)], 6, thermal=False)
zone('SRC', 'SRC', [F, B], [(40.7, 24.1), (46.95, 24.1), (46.95, 26.9), (40.7, 26.9)], 5, thermal=False)
# MCU-side ground pour (isolated, PWM_N) on bottom
zone('MCU_GND', 'PWM_N', [B], [(0, 0), (10.0, 0), (10.0, 17.0), (0, 17.0)], 1)

# solid (no thermal) connection for high-current THT pads
for f in b.GetFootprints():
    for p in f.Pads():
        if (f.GetReference(), p.GetNumber()) in [('J1', '2'), ('J1', '1'), ('J2', '1'), ('J2', '2'), ('F1', '1'), ('F1', '2'),
                                                 ('Q1', '2'), ('Q1', '3'), ('D1', '1'), ('TVS1', '1'), ('TVS1', '2'),
                                                 ('C1', '2'), ('RS1', '1'), ('RS1', '4')] or f.GetReference() in ('C4', 'C7', 'C8', 'C9', 'R12', 'R3', 'Q2', 'R10', 'D3', 'TH1', 'R20', 'U3'):
            p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
filler = pcbnew.ZONE_FILLER(b)
filler.Fill(b.Zones())
b.Save(OUT)
for z in b.Zones():
    if not z.GetIsRuleArea():
        print(z.GetZoneName(), z.GetNetname(), 'filled area mm2:', round(z.GetFilledArea() / 1e12, 1))
