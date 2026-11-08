#!/bin/bash
set -e
SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
P="$(cd "$SCRIPTS/.." && pwd)"
S="${BUILD:-$SCRIPTS/build}"; mkdir -p "$S"
FREEROUTING_JAR="${FREEROUTING_JAR:-$HOME/freerouting-2.1.0.jar}"
cd "$SCRIPTS"
python3 stage1.py $S/s1.kicad_pcb $S/s1.dsn | tail -1
(timeout 1500 java -jar "$FREEROUTING_JAR" -de $S/s1.dsn -do $S/s1.ses -mp 100 -mt 4 -oit 0.001 --router.optimizer.enabled=true --router.optimizer.max_passes=200 2>&1 | grep -v JAVA_TOOL | grep -E "incomplete_count" | tail -1)
python3 stage2.py $S/s1.kicad_pcb $S/s1.ses $S/s2.kicad_pcb
python3 stage3.py $S/s2.kicad_pcb $S/s3.kicad_pcb | tail -1
python3 stage4.py $S/s3.kicad_pcb $S/s4.kicad_pcb 2>&1 | grep -E "!!|hid|removing|saved"
cp $S/s4.kicad_pcb $P/heater_driver_v4.kicad_pcb
cd $P && kicad-cli pcb drc --schematic-parity -o $S/final_drc.rpt heater_driver_v4.kicad_pcb >/dev/null 2>&1 || true
grep -E "^\[" $S/final_drc.rpt | sed 's/\].*/]/' | sort | uniq -c; grep -E "Found" $S/final_drc.rpt
