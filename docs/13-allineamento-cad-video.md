# 13 · Allineamento CAD ↔ video (compito aperto)

Stato: **implementato sul ramo `cad-allineamento` (NON ancora in `main`), provato solo con camera sintetica e browser headless**. Mai provato con iPhone, treppiede, marker stampati o un CAD vero. Code freeze: dom 07:30.

## Implementato (ramo `cad-allineamento`)
| Pezzo | Dove | Note |
|---|---|---|
| Normalizzazione DXF | `oracolo/cad_norm.py` (senza OpenCV) | metri, origine (0,0), perimetro per layer o per forma, ostacoli = poligoni chiusi con altezza di default se manca `_H`, scarta quote/testi/porte/oggetti minuscoli (<0,10 m²), espande i blocchi `INSERT`; restituisce sempre `{ok, errors, warnings, stats}` |
| «Carica DXF» | pannello `/` e `/room`, `POST /dxf` | solo `.dxf` (DWG rifiutato); se il file non è utilizzabile la planimetria precedente resta; copia standard salvata in `planimetria.dxf` |
| Avvio senza stanza | `scripts/run_camera.py` | nessuna planimetria predefinita: si sceglie «Carica DXF» o «Disegna»; `--dxf` resta come ripiego da terminale; `--room-file` (default `planimetria.dxf`) evita di sovrascrivere gli esempi in `scenarios/` |
| Ancore ArUco a terra | `oracolo/vision/align.py`, `/calibrate`, `POST /anchors`, `POST /calib_anchors`, `anchors.json` | id 10-13, DICT_4X4_50, coordinate del centro nel CAD, `rot_deg` facoltativo; la calibrazione a 4 clic resta |
| Stato allineamento | `pipeline.py` → `state["align"]`, banner nel pannello | `OK` / `DEGRADATO` / `NON_COINCIDE` (+ `NON_VERIFICATO` senza ancore, `SENZA_CALIBRAZIONE`); `health = min(frame_health, confidenza)` con confidenza 1,0 / 0,6 / 0,0 |
| Marker da stampare | `scripts/make_anchor_markers.py` → `markers/marker_ancora_ID1x_*.pdf` | A3 con nero 20 cm (consigliato), A4 con nero 15 cm (minimo) |

Non fatta: la verifica a bordi (punto 3 della proposta): fragile senza stanza vera, da valutare solo dopo una prova reale.

## Come si usa (ancore)
1. Stampare i 4 marker (`markers/marker_ancora_ID10…13_20cm_A3.pdf`, **al 100%**), misurare il quadrato nero, incollarli piatti a terra in punti noti del CAD, sparsi, lato superiore verso +Y della planimetria.
2. `/calibrate` → «Ancore a terra»: per ogni marker x, y del centro in metri (o «sulla mappa» e clic), lato nero in cm, e **posizione della camera (x, y, altezza)**: la camera NON viene stimata (vedi limiti). «Salva ancore», poi «Calibra da ancore» con le ancore ben visibili.
3. Nel pannello controllare che il CAD si sovrapponga al video e che «allineamento» sia `OK`. In alternativa si può scrivere `anchors.json` (esempio: `scenarios/anchors_esempio.json`).

## Dimensione minima dei marker (SIMULAZIONE, indicativa: non misurata su iPhone)
Condizioni simulate: frame **960×540** come li invia `camera.html` (non la risoluzione nativa), campo visivo ~69° (f ≈ 700 px), JPEG 72%, sfocatura e rumore leggeri, camera a 1,8-2,2 m, marker a terra a 2-3 m in orizzontale, ruotati in tutti i modi.
| lato nero | lato minore apparente a 3 m | rilevato (sim.) |
|---|---|---|
| 10 cm | 11-12 px | 85-89% |
| 15 cm | 17-18 px | 100% |
| **20 cm** | 23-24 px | 100% |
| 25-30 cm | 28-35 px | 100% |

Indicazione: **20 cm di nero consigliati** (3 m), **15 cm minimo**; regola indicativa ~7 cm di lato per ogni metro di distanza dalla camera. Il bordo bianco (lato/6 per parte) è parte del marker: 20 cm nero = 26,7 cm in totale (A3); su A4 al massimo 15 cm. La simulazione non include sfocatura da movimento, riflessi sul pavimento, autofocus: confermare con l'iPhone.

## Limiti misurati / dichiarati
- **Posizione della camera non stimata dalle ancore**: provata la stima dall'omografia (senza focale nota) con la camera sintetica: con 0,5 px di rumore sbaglia di ~0,5 m (95° percentile ~2 m). Con focale assunta l'errore cresce con quello sulla focale (5% → ~14 cm, 10% → ~28 cm). Per questo si indica a mano (3 numeri) o si riusa quella della calibrazione precedente.
- **Soglie = ipotesi, non tarate su video reale**: `OK` ≤ 10 cm di errore medio sugli angoli delle ancore, `NON_COINCIDE` > 25 cm per 3 frame di fila (0,3 s a 10 fps), ancore viste negli ultimi 2 s; servono ≥3 ancore per `OK`. Da tarare con la prova vera (`oracolo/vision/align.py`, costanti in testa).
- Con camera sintetica spostata di 40 cm: errore 26 cm → `NON_COINCIDE` dopo 3 frame, health 0, comando FERMA. Una spinta piccola (~5 cm sulle ancore) resta `OK` (test `test_known_limit_small_camera_shift…`).
- **Una coordinata sbagliata di 1 m su UNA ancora non viene rilevata** con 4 ancore (errore ~8 cm: l'omografia è quasi determinata dai soli centri). Servono ≥5 ancore, oppure il controllo visivo della sovrapposizione CAD-video. Test `test_known_limit_single_wrong_coordinate…`.
- Le ancore verificano solo se la camera «vede» il CAD dove dovrebbe nei punti delle ancore, non che scaffali e muri siano disegnati giusti.
- Se le ancore restano coperte oltre 2 s → `DEGRADATO` (rallenta, health 0,6); non si torna `OK` finché non se ne vedono ≥3.
- Normalizzazione: nessuna rotazione/raddrizzamento del disegno; ARC, SPLINE, HATCH e quote non sono letti; la regola «porta» (elemento sottile <0,3 m e corto <3 m attaccato al perimetro) può scartare un tramezzo corto: viene segnalato negli avvisi. Provata solo su file sintetici (nessun CAD reale).
- Prototipo di ricerca: non è un sistema di sicurezza certificato.


## Obiettivo
L'utente importa un CAD (DXF) vero. Il sistema:
1. lo **porta al nostro standard** (unità, origine, layer, altezze) e segnala se è inutilizzabile;
2. lo **mette in corrispondenza con il video** della camera fissa;
3. se CAD e video **non coincidono** → avvisa e, per il principio "ignoto ≠ libero", non si fida della mappa (comando FERMA);
4. se coincidono → mostra punti ciechi e ostacoli (già calcolati dal motore dalla geometria del CAD).

La pianta 2D disegnata a mano (lavoro di un collega) resta il **piano B** quando non c'è un CAD.

## Cosa esiste già (non rifare)
- `oracolo/cad.py`: `load_dxf` (mm/cm/m, layer `_H<altezza>`, perimetro, muri a segmenti con `lines_as_walls`).
- `oracolo/vision/calib.py`: omografia pixel→metri da ≥4 coppie cliccate in `/calibrate`; errore di riproiezione `rms_m`.
- `oracolo/vision/viz.py`: sovrappone il CAD al video. `pipeline.py` calcola nebbia/punti ciechi (`use_fog`) e accetta `health` (0..1): sotto 0.3 il motore ferma.
- `tests/synth.py`: camera sintetica per test senza hardware.

## Proposta (in ordine di affidabilità)
1. **Normalizzazione CAD** (`oracolo/cad_norm.py`): controlla perimetro chiuso, scala plausibile (stanza 1–200 m), origine in (0,0), layer sconosciuti, ostacoli senza altezza; restituisce `{ok, warnings, stats}` mostrato nel pannello.
2. **Ancore a terra**: 4 marker ArUco (id 10–13) incollati a terra in punti noti del CAD (coordinate in un piccolo JSON). Calibrazione automatica senza clic; l'**errore di riproiezione delle ancore è la misura di coincidenza** e, rifatta di continuo, rileva anche una camera spostata. È il segnale più robusto.
3. **Verifica a bordi (secondario) — NON implementata**: punteggio tra i bordi del CAD proiettati e i bordi dell'immagine (Canny + distance transform). Fragile senza stanza vera: soglie da tarare su un video reale; usarlo come indicatore, non come unico criterio.
4. **Integrazione**: stato `allineamento` ∈ {OK, DEGRADATO, NON_COINCIDE}; `health = min(frame_health, confidenza_allineamento)`; banner nel pannello "CAD non coincide con il video".

## Criteri di accettazione
- Test sintetici: CAD allineato → OK; camera spostata/ruotata → NON_COINCIDE; ancore coperte → DEGRADATO (non OK).
- `make test` verde prima e dopo; nessuna dipendenza nuova non dichiarata in `THIRD_PARTY.md`; il motore (`oracolo/*.py` fuori da `vision/`) non importa OpenCV.
- Documentare i limiti: non è un sistema di sicurezza certificato.

## Lavoro del collega (già in `main`, merge 105e049, 69 test verdi)
QR per l'iPhone, editor 3D stanza/ostacoli (`/room`, `web/room.html`, `room.js`), `scene_from_spec` e `save_dxf` in `cad.py`, `LiveApp(dxf_path=...)`, rilevatore `--detector auto` (prova YOLO → RF-DETR → HOG; YOLO è AGPL, opzionale, dichiarato in THIRD_PARTY), `calibrate.html`/`pipeline.py`/`viz.py` modificati, `scenarios/stanza.dxf` rigenerato (ora è la sua stanza 5×3 m con scrivanie, piano, letto, armadio). Partire da `main` aggiornato e leggere `git show d256f85` prima di toccare quei file.

## Divisione del lavoro (evitare conflitti)
- File **nuovi** (`cad_norm.py`, `vision/align.py`, test) + piccoli punti di aggancio in `pipeline.py`, `server.py` e `calibrate.html`, che il collega ha appena modificato: fare piccole modifiche e non riscrivere.
- Lavorare sul ramo `cad-allineamento`; unire a `main` solo su richiesta, dopo `make test`.

## DXF di prova "sporco" (`scenarios/magazzino_realistico_mm.dxf`)
File **sintetico** (non è un CAD vero) costruito per assomigliare a uno reale: millimetri, origine lontana (151 m, 86 m), layer con nomi non nostri (`A-WALL`, `S-RACK_H2800`…), quote, testi, porta, oggetto minuscolo. Con l'importatore attuale: il perimetro `A-WALL` non è riconosciuto e diventa un ostacolo alto 3 m, la porta e il cerchietto diventano ostacoli, i confini non partono da (0,0). La normalizzazione (punto 1) deve sistemare esattamente questo. Atteso dopo la normalizzazione: stanza 24×14 m con origine in (0,0), 4 scaffali (2.8 m), 6 pilastri (4 m), 2 bancali (1.2 m), nessuna porta/testo/quota come ostacolo.


## Rischi
- La catena iPhone → Mac **non è ancora stata provata dal vivo** (test fatti solo con camera sintetica e finta). Serve una prova vera per tarare le soglie.
- Non abbiamo un CAD reale di prova: chiedere agli organizzatori un DXF di esempio, o usare uno scaricabile.
