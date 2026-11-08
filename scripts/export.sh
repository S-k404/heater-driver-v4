#!/bin/bash
# Export every fab/doc output from the final project (run from project dir)
set -e
SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
P="$(cd "$SCRIPTS/.." && pwd)"
S="${BUILD:-$SCRIPTS/build}"; mkdir -p "$S"
FREEROUTING_JAR="${FREEROUTING_JAR:-$HOME/freerouting-2.1.0.jar}"
cd $P
python3 -c "
import pcbnew
b=pcbnew.LoadBoard('heater_driver_v4.kicad_pcb'); ds=b.GetDesignSettings()
o=pcbnew.VECTOR2I(pcbnew.FromMM(100),pcbnew.FromMM(138)); ds.SetAuxOrigin(o); ds.SetGridOrigin(o)
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save('heater_driver_v4.kicad_pcb')" 2>&1 | grep -v Debug || true
mkdir -p fab/gerbers bom docs reports
for f in fab/gerbers/*; do [ -f "$f" ] && rm "$f"; done
kicad-cli sch erc --severity-all -o reports/ERC_report.txt heater_driver_v4.kicad_sch >/dev/null
kicad-cli pcb drc --schematic-parity --severity-all -o reports/DRC_report.txt heater_driver_v4.kicad_pcb >/dev/null || true
kicad-cli pcb export gerbers -l F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts --subtract-soldermask -o fab/gerbers/ heater_driver_v4.kicad_pcb >/dev/null
kicad-cli pcb export drill --format excellon --excellon-separate-th --generate-map --map-format pdf -u mm -o fab/gerbers/ heater_driver_v4.kicad_pcb >/dev/null
(cd fab/gerbers && zip -q -r ../heater_driver_v4_GERBERS_for_fab.zip .)
kicad-cli sch export bom --fields 'Reference,Value,Footprint,MPN,Description,${QUANTITY}' --labels 'Reference,Value,Footprint,MPN,Description,Qty' --group-by 'Value,Footprint,MPN' --exclude-dnp -o bom/heater_driver_v4_BOM.csv heater_driver_v4.kicad_sch >/dev/null
kicad-cli pcb export pos --format csv --units mm --side both --use-drill-file-origin -o bom/heater_driver_v4_CPL_all.csv heater_driver_v4.kicad_pcb >/dev/null
kicad-cli sch export pdf -o docs/heater_driver_v4_schematic.pdf heater_driver_v4.kicad_sch >/dev/null
pdftoppm -png -r 150 -singlefile docs/heater_driver_v4_schematic.pdf docs/heater_driver_v4_schematic
kicad-cli pcb export pdf --mode-single --layers F.Cu,F.SilkS,F.Mask,Edge.Cuts --include-border-title -o $S/l1.pdf heater_driver_v4.kicad_pcb >/dev/null
kicad-cli pcb export pdf --mode-single --layers B.Cu,B.SilkS,B.Mask,Edge.Cuts --mirror --include-border-title -o $S/l2.pdf heater_driver_v4.kicad_pcb >/dev/null
kicad-cli pcb export pdf --mode-single --layers F.Fab,F.SilkS,Edge.Cuts --include-border-title -o $S/l3.pdf heater_driver_v4.kicad_pcb >/dev/null
pdfunite $S/l1.pdf $S/l2.pdf $S/l3.pdf docs/heater_driver_v4_layout.pdf
kicad-cli pcb export pdf --mode-single --layers F.Fab,F.SilkS,Edge.Cuts -o docs/heater_driver_v4_assembly_drawing.pdf heater_driver_v4.kicad_pcb >/dev/null
cd "$SCRIPTS"
./render.sh $P/heater_driver_v4.kicad_pcb $P/docs/heater_driver_v4_layout_top.png F.Cu,F.SilkS,F.Mask,Edge.Cuts
./render.sh $P/heater_driver_v4.kicad_pcb $P/docs/heater_driver_v4_layout_bottom.png B.Cu,B.SilkS,B.Mask,Edge.Cuts
./render.sh $P/heater_driver_v4.kicad_pcb $P/docs/heater_driver_v4_assembly.png F.Fab,F.SilkS,Edge.Cuts
python3 make_assembly_guide.py $P/heater_driver_v4.kicad_pcb $S/guide.html && /opt/pw-browsers/chromium-1194/chrome-linux/chrome --headless=new --no-sandbox --no-pdf-header-footer --print-to-pdf=$P/docs/heater_driver_v4_placement_guide.pdf $S/guide.html >/dev/null 2>&1 || echo 'guide: print guide.html to PDF with any browser'
python3 verify_traces.py $P/heater_driver_v4.kicad_pcb $P/reports/trace_current_check.json > $P/reports/trace_current_check.txt
cd $P/fab/gerbers && gerbv --export=png --dpi=400 --border=2 --output=$P/docs/gerber_check_top.png --background='#103010' --foreground='#ffffffff' heater_driver_v4-F_Silkscreen.gto --foreground='#000000ff' heater_driver_v4-PTH.drl --foreground='#000000ff' heater_driver_v4-NPTH.drl --foreground='#e0b040ff' heater_driver_v4-F_Cu.gtl --foreground='#808080ff' heater_driver_v4-Edge_Cuts.gm1 >/dev/null 2>&1
gerbv --export=png --dpi=400 --border=2 --output=$P/docs/gerber_check_bottom.png --background='#101030' --foreground='#ffffffff' heater_driver_v4-B_Silkscreen.gbo --foreground='#000000ff' heater_driver_v4-PTH.drl --foreground='#000000ff' heater_driver_v4-NPTH.drl --foreground='#40a0e0ff' heater_driver_v4-B_Cu.gbl --foreground='#808080ff' heater_driver_v4-Edge_Cuts.gm1 >/dev/null 2>&1
echo exported
