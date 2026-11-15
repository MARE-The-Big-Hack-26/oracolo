# 05 · Demo e UX

Obiettivo: in **70 secondi** il giurato capisce che (1) la macchina sa dove è cieca, (2) rallenta *prima* che il pedone compaia, (3) si ferma da sola se qualcosa smette di funzionare. Design/UX pesa quanto l'algoritmo: lo schermo deve essere leggibile in **2 secondi**.

## Copione (3 atti)
| Atto | Durata | Cosa succede | Cosa si vede |
|---|---|---|---|
| 1. L'incrocio cieco | 25 s | La macchina accelera lungo la corsia; nessun pedone in vista | Livello 0 → 1 → 2 mentre si avvicina all'incrocio; zona arancio "non osservata" accanto alla corsia; limite in m/s che scende |
| 2. Il pedone che esce | 25 s | Un compagno (con il tappo) esce dalla corsia trasversale proprio mentre la macchina arriva | Il pedone appare → "osservato"; la macchina era già lenta → si ferma con margine; poi riparte. Confronto affiancato "senza ClearCorner": collisione |
| 3. Quando qualcosa si rompe | 20 s | Si taglia il link / si copre la camera | Il banner «AFFIDABILITÀ PERSA» e FERMA; il watchdog dichiara «nessun comando valido» |

Dopo: 10 s di numeri (tabella e grafico sicurezza‑produttività).

## HUD (un solo schermo)
- **Centro:** pianta dall'alto: verde = visibile, grigio = ricordato libero, arancio = sconosciuto, rosso = persona possibile nascosta; macchina colorata per livello; pedone blu.
- **In alto:** livello (parola + numero), limite in m/s, causa in italiano.
- **A sinistra:** i 4 livelli come scala, quello attivo evidenziato.
- **In alto a destra:** salute (latenza p50/p95, FPS, qualità scena).
- **Banner centrale solo per gli allarmi.**
- Ogni stato distinguibile anche **senza colore** (forma ed etichetta: NORMALE, ATTENZIONE, RALLENTA, FERMA). Palette Okabe–Ito (pensata per il daltonismo).

## Schermata "cabina" (iPhone Safari) — già implementata
`python scripts/run_live.py` → sull'iPhone `http://<IP-del-Mac>:8000`. Sfondo colorato per livello, parola grande (NORMALE / ATTENZIONE / RALLENTA / FERMA), simbolo, velocità in km/h, causa in italiano, e quanti ms fa è arrivato l'ultimo comando. Se il comando scade la pagina va in STOP da sola («NESSUN COMANDO VALIDO → arresto automatico»). Pensata per chi guarda per mezzo secondo.

## Audio (italiano, `say -v Alice`)
Frasi di massimo 4–5 parole, una ogni 2 secondi al massimo: «Rallenta», «Zona non visibile», «Fermo», «Affidabilità persa». Priorità agli allarmi; mai parlare sopra un allarme.

## Cosa NON fare
Niente dashboard web complicate, niente 3D, niente app nativa. Una cosa che funziona bene vale più di tre a metà.

## Generare immagini per il video
`make frames` produce i frame PNG del caso incrocio cieco (livelli e zone colorati); si montano o si usano come fondale.
