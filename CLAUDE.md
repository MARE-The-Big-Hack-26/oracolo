# Contesto progetto (per Claude e per chi legge)

**Team:** 3 "jolly" (ruoli: M Motore, V Visione/modellino, E Esperienza). Hackathon: The Big Hack 2026, Challenge 03 FieldVision (Mare Group). **Deadline: domenica 15/11/2026 ore 12:00 CET** (puntare alle 11:15). Hardware: 3 MacBook Air 15 + 3 iPhone 15 Pro (camera fissa = iPhone su treppiede; il muletto NON ha display: segnale = solo comando; muletto simulato = sedia con marker). Lingua: italiano. **Dobbiamo vincere: priorità a demo funzionante, video chiaro, numeri onesti.**

**Progetto: Oracolo** — rilevazione dei punti ciechi per macchine industriali: una camera segnala 4 livelli di pericolo (0 NORMALE, 1 ATTENZIONE, 2 RALLENTA, 3 FERMA) per possibili collisioni pedone–macchina e invia un comando che rallenta o ferma. Principio: *ignoto ≠ libero*.

**Workflow del progetto:** si importa il CAD del magazzino (DXF); camere FISSE vedono carrelli, persone e zone d'ombra; il carrello ha un ricevitore che riceve il comando (limite di velocità + livello) e rallenta/ferma. In prototipo il Mac invia i comandi a un iPhone (Safari) che fa da ricevitore.

**Stato del codice (`repo/`):** testato (67 test): import CAD (`cad.py`), scenario magazzino + copertura camere (`warehouse.py`), visibilità 2.5D, mappa epistemica (fog con fantasmi), politica di velocità (TTR, curva di frenata), comando fail-safe con TTL, macchina virtuale, **ricevitore iPhone** (`cab.py` + `scripts/run_live.py`), simulatore a ciclo chiuso, benchmark, video (`make frames`). **Pipeline reale** (`oracolo/vision/`, `scripts/run_camera.py`): iPhone su treppiede → pagina web HTTPS → Mac (calibrazione a 4 punti, marker ArUco sulla sedia, persone con RF-DETR/HOG, tracking, pannello con CAD sovrapposto, fail-safe se i frame si fermano): vedi `docs/12-pipeline-reale.md`. Da fare: prova su iPhone/treppiede reali, scelta e misura del rilevatore persone, clip e metriche reali, video finale, README finale.

**Regole di lavoro**
- Non inventare numeri: ogni cifra viene da un log o è marcata «indicativa». Simulazione e clip reali vanno in tabelle separate.
- Non dire «sistema di sicurezza» né «certificato»: è un prototipo di ricerca.
- Il motore non importa OpenCV. `make test` prima e dopo ogni modifica.
- Evitare Ultralytics YOLO (AGPL); dichiarare ogni libreria in `repo/THIRD_PARTY.md` e l'uso dell'AI in `repo/AI_USAGE.md`.
- Dopo il blocco del codice (dom 07:30) niente nuove funzioni.
- Piani A/B/C e cancelli: `docs/07-roadmap.md`. Regole e giuria: `docs/09-hackathon.md`.

**Mappa dei documenti:** `docs/00-visione` · `01-problema-e-stato-dell-arte` · `02-comando-macchina-costi` · `03-motore` · `04-visione-e-modellino` · `05-demo-ux` · `06-metriche` · `07-roadmap` · `08-github` · `09-hackathon` · `10-prompts` · `11-handoff-nuova-chat` · `12-pipeline-reale`.
