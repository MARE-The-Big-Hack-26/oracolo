# 12 · Pipeline reale: iPhone su treppiede → Mac (pannello)

Stato: **implementata e provata con camera simulata e con un browser vero (camera finta)**. NON ancora provata su iPhone, treppiede e persone reali: è il prossimo passo (vedi «Da fare»).

## Cosa fa
```
iPhone (Safari, /camera) --JPEG ~10 fps, HTTPS--> Mac: LivePipeline
   marker ArUco sulla sedia  -> posa del muletto (posizione, direzione, velocità)
   rilevatore di persone     -> piedi -> metri sulla planimetria -> tracking
   camera fissa calibrata    -> cosa vede / cosa è zona cieca (geometria + inquadratura)
   Oracolo (motore)          -> livello 0..3, limite di velocità, causa
Mac: pannello (/) = video con CAD sovrapposto + mappa dall'alto + indicatori
```
Il muletto non ha display: il segnale è solo il comando (limite + livello). La sedia la spinge una persona che "fa da attuatore"; il pannello mostra anche se la sedia supera il limite (violazioni).

## Avvio (sul Mac)
```bash
pip install -r requirements.txt
make camera                            # avvia il server (HTTPS, porta 8443) SENZA planimetria
```
- **Non c'è una stanza predefinita.** Nel pannello (`/`) si sceglie: **«Carica DXF»** (solo file `.dxf`, non DWG: viene normalizzato in metri con origine in (0,0), con avvisi) oppure **«Disegna planimetria»** (editor `/room`). Entrambi salvano la planimetria standard in `planimetria.dxf` (cartella corrente, `--room-file`).
- Ripiego da terminale: `python scripts/run_camera.py --dxf percorso/file.dxf` (non viene sovrascritto). I file in `scenarios/` sono solo esempi e fixture di test; `make room` genera ancora `scenarios/stanza.dxf` dalle misure di `stanza_esempio.json`.
- **Mac:** `http://localhost:8443/` (pannello, senza alcun avviso certificato; la porta 8443 accetta sia HTTP che HTTPS).
- **iPhone (e altri dispositivi):** di default `run_camera.py` apre automaticamente un **Cloudflare Quick Tunnel** (`https://<id>.trycloudflare.com/camera`, scaricando `cloudflared` in `~/.cache/oracolo/cloudflared` se assente) con certificato HTTPS pubblico riconosciuto da iOS/Android/macOS senza avvisi *"Non sicuro"*. In assenza di rete o con `--no-tunnel`, usa il fallback LAN `https://<IP-del-Mac>:8443/camera`.
- **Calibrazione (una volta, treppiede fermo):** `http://localhost:8443/calibrate`
  1. «Aggiorna immagine»; 2. clicca un punto A TERRA sul video e lo stesso punto sulla mappa (angolo della stanza, base di un mobile), almeno 4, ben distanziati; 3. «Imposta posizione camera» e clicca dove sta sulla mappa; altezza della camera da terra; 4. «Calcola e salva» → `calib.json` (errore medio in cm).
- **Calibrazione automatica con ancore a terra (alternativa ai clic):** 4 marker ArUco id 10-13 a terra in punti noti del CAD + posizione della camera, da `/calibrate` → «Ancore a terra»; segnala anche se il CAD non coincide più col video. Dettagli, dimensione dei marker e limiti: `docs/13-allineamento-cad-video.md`.
- **Sedia:** stampare `markers/marker_muletto_ID0_A4.pdf` (100%, carta opaca), incollarlo piatto sulla sedia con il lato SUPERIORE verso il davanti; quota del marker `--marker-h` (default 0,45 m).

## Piano B e prove senza iPhone
- Video registrato: `python scripts/run_camera.py --source video:clip.mp4 --loop` (registrare con l'app Foto, AirDrop sul Mac).
- Webcam / Continuity Camera: `--source cam:0` (con iPhone dello stesso Apple ID).
- Senza HTTPS (solo prove sul Mac): `--http`.
- Persone: `--detector hog` (OpenCV, nessun download, qualità media), `--detector rfdetr:nano` (consigliato; `pip install rfdetr`, scarica i pesi la prima volta; **non ancora provato qui**), `--detector none` (solo muletto).

## Mappa della stanza (senza CAD)
- **Misure:** `scenarios/stanza_esempio.json` → `make room` → DXF (perimetro + ostacoli con altezza).
- **Scansione LiDAR** (iPhone 15 Pro, app che esporta DXF): `--lines-as-walls` legge i muri disegnati a segmenti. **Non provato su un file reale**: appena c'è un DXF vero, verificare e adattare `oracolo/cad.py`.
- **Importante:** definire come "magazzino" l'AREA DI PROVA (nastro a terra) e non tutta la stanza: ciò che la camera non vede è "ignoto" e il motore frena. Meglio che la camera copra quasi tutta l'area e che i punti ciechi siano gli scaffali/ostacoli voluti.

## Scelte tecniche (perché)
- **Modello locale sul Mac, non API cloud:** latenza di secondi e dipendenza dalla rete non vanno bene per un comando di frenata.
- **Camera iPhone via pagina web HTTPS** (iPhone dell'organizzazione ≠ stesso Apple ID → niente Continuity Camera). Certificato autofirmato generato da `oracolo/vision/certs.py`.
- **Marker ArUco per la sedia:** identità e direzione certe; la classe "sedia" del modello confonde le sedie ferme.
- **Correzione di parallasse:** il marker sta a ~0,45 m; senza correzione la posizione sbaglia anche di oltre 1 m. Servono la posizione e l'altezza della camera.
- **Conducente escluso:** chi spinge la sedia (dentro 1,3 m e non davanti) non è un pedone da proteggere (`LivePipeline.driver_radius`).
- **Fail-safe:** se i frame smettono di arrivare (> 0,6 s) lo stato diventa FERMA / «Affidabilità persa». Se il marker non si vede, nessun comando («muletto non rilevato»).
- **Profilo `sedia`** (default in `run_camera.py`): v_max 1 m/s, margine 0,3 m, ingombro 0,6 m, orizzonte 3 m. Per il carrello reale: `--profile magazzino` (8 km/h). Parametri = ipotesi dichiarate.

## Limiti dichiarati
- Un'unica camera: dietro gli ostacoli e fuori inquadratura è "ignoto" (frenata prudente anche senza persone).
- Persone con i piedi non visibili (taglio del riquadro) → posizione meno affidabile.
- ID che cambiano (tracker semplice) = persone in più → il motore è più prudente.
- L'errore di calibrazione si somma: verificare la sovrapposizione del CAD sul video prima di ogni prova.
- Nessuna misura su un carrello vero: tutto ciò che riguarda l'arresto è simulato o fatto con una sedia spinta a mano.

## Test (67)
`python -m pytest -q`. I test della pipeline usano una camera sintetica (`tests/synth.py`: pinhole, marker proiettato con parallasse) e verificano: omografia, correzione di quota, tracking, esclusione del conducente, livello con persona davanti, server HTTPS completo (frame → calibrazione → stato → video annotato) e arresto per frame fermi.

## Da fare (in ordine)
1. Prova reale: iPhone + treppiede + calibrazione + sedia con marker (verificare nitidezza, distanza di lettura del marker, errore in cm).
2. Scegliere il rilevatore di persone (RF-DETR vs HOG) misurando i fps sul MacBook Air.
3. Prova con persone che attraversano e si nascondono dietro uno scaffale; registrare clip per il video e le metriche.
4. (Bonus) Scansione LiDAR → DXF; mappa dal video con segmentazione (SAM 2) in modo semi-automatico.
