#!/bin/bash
# render.sh board.kicad_pcb out.png [layers]
L=${3:-F.Cu,B.Cu,F.SilkS,F.Fab,F.Courtyard,Edge.Cuts,Dwgs.User}
kicad-cli pcb export svg --mode-single --layers $L --page-size-mode 2 --exclude-drawing-sheet -o ${TMPDIR:-/tmp}/hd4_render.svg "$1" >/dev/null 2>&1
python3 -c "import cairosvg,sys; cairosvg.svg2png(url='${TMPDIR:-/tmp}/hd4_render.svg', write_to='$2', output_width=1400, background_color='white')"
