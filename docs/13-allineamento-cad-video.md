# 13 · Allineamento CAD ↔ video (compito aperto)

Stato: **da fare**. Scritto il sabato sera prima del code freeze (dom 07:30).

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
3. **Verifica a bordi (secondario)**: punteggio tra i bordi del CAD proiettati e i bordi dell'immagine (Canny + distance transform). Fragile senza stanza vera: soglie da tarare su un video reale; usarlo come indicatore, non come unico criterio.
4. **Integrazione**: stato `allineamento` ∈ {OK, DEGRADATO, NON_COINCIDE}; `health = min(frame_health, confidenza_allineamento)`; banner nel pannello "CAD non coincide con il video".

## Criteri di accettazione
- Test sintetici: CAD allineato → OK; camera spostata/ruotata → NON_COINCIDE; ancore coperte → DEGRADATO (non OK).
- `make test` verde prima e dopo; nessuna dipendenza nuova non dichiarata in `THIRD_PARTY.md`; il motore (`oracolo/*.py` fuori da `vision/`) non importa OpenCV.
- Documentare i limiti: non è un sistema di sicurezza certificato.

## Divisione del lavoro (evitare conflitti)
- Collega: pianta 2D e QR (probabilmente `scripts/make_room_dxf.py`, `web/*.html`, `server.py`).
- Qui: file **nuovi** (`cad_norm.py`, `vision/align.py`, test) + piccoli punti di aggancio in `pipeline.py` e `/calibrate`. Lavorare su un ramo proprio e unire dopo `git pull`.

## Rischi
- La catena iPhone → Mac **non è ancora stata provata dal vivo** (test fatti solo con camera sintetica e finta). Serve una prova vera per tarare le soglie.
- Non abbiamo un CAD reale di prova: chiedere agli organizzatori un DXF di esempio, o usare uno scaricabile.
