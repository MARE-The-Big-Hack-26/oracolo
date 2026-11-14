# Librerie, modelli e dati di terze parti

Da compilare e verificare PRIMA della consegna (il regolamento richiede di dichiarare librerie, modelli e uso di AI).
Le licenze sotto sono quelle note al momento della stesura: ricontrollare sul sito/repo ufficiale e annotare la data.

| Componente | Uso | Licenza (da verificare) | Verificato il |
|---|---|---|---|
| numpy | calcolo | BSD | |
| scipy | distanze e morfologia sulla griglia | BSD | |
| shapely | geometria 2D, poligoni di visibilità | BSD-3-Clause | |
| matplotlib | rendering offline | licenza tipo BSD (matplotlib) | |
| ezdxf | lettura del CAD (DXF) | MIT | |
| pytest | test | MIT | |
| opencv-python-headless | omografia, ArUco (muletto id 0 e ancore a terra id 10-13), HOG persone, JPEG | Apache-2.0 (4.5+) | |
| cryptography | certificato HTTPS autofirmato | Apache-2.0 / BSD | |
| supervision (opzionale) | tracking/annotazioni | MIT | |
| RF-DETR (opzionale) | rilevatore persone (`--detector rfdetr:nano`) | Apache-2.0 | |
| Ultralytics YOLO11 / YOLO11-Pose (opzionale) | rilevatore persone e caviglie (`--detector yolo:pose`) | AGPL-3.0 | |
| Pillow (già dipendenza di matplotlib; nessun nuovo pacchetto) | `scripts/make_anchor_markers.py`: esporta i PDF dei marker | HPND / MIT-CMU (da verificare) | |
| Three.js (CDN, solo UI /room) | editor 3D planimetria e ostacoli (OrbitControls, TransformControls) | MIT | |

Nota su Ultralytics YOLO: ha licenza AGPL-3.0 (se incluso nella distribuzione finale richiede rilascio sotto AGPL; in alternativa usare `--detector rfdetr:nano`, Apache-2.0).

## Dati e media
- Clip video girate dal team, con il consenso delle persone riprese.
- Nessuna immagine di terzi senza licenza.
