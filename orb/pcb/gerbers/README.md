# Gerber Files

Generate Gerbers from KiCad:

1. Open `kagami_orb.kicad_pcb` in KiCad
2. File → Fabrication Outputs → Gerbers
3. Select output directory: `gerbers/`
4. Plot all layers

## Required Files

| File | Layer |
|------|-------|
| kagami_orb-F_Cu.gbr | Front Copper |
| kagami_orb-B_Cu.gbr | Back Copper |
| kagami_orb-F_Mask.gbr | Front Solder Mask |
| kagami_orb-B_Mask.gbr | Back Solder Mask |
| kagami_orb-F_Silkscreen.gbr | Front Silkscreen |
| kagami_orb-B_Silkscreen.gbr | Back Silkscreen |
| kagami_orb-Edge_Cuts.gbr | Board Outline |
| kagami_orb.drl | Drill File |

## Manufacturer Settings

- JLCPCB: Use their Gerber generator plugin
- PCBWay: Standard Gerber X2 format
- OSHPark: Direct KiCad upload supported
