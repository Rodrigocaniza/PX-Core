# BC Caja responsive comparison

The same UI selects one of two deterministic metric profiles from the available
display area. Tk/CustomTkinter remains the only DPI scaling authority.

| Metric | 1366×768 compact | 1920×1080 Full HD |
|---|---:|---:|
| General UI font | 9 | 12 |
| Section heading | 11 | 14 |
| KPI amount | 14 | 20 |
| Input height | 24 px | 34 px |
| Movement row | 27 px | 38 px |
| Left form width | 570 px | 750 px |
| Movement area height | 354 px | 590 px |
| Approximate visible rows | 13 | 15 |
| Useful content width | 1330 px | 1880 px |

The Full HD profile prioritizes reading distance, larger interaction targets,
wide movement columns and additional visible rows. The compact profile retains
the previously validated geometry. At Windows 125%, no second application-level
multiplier is applied, preventing double scaling.
