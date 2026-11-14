# 07 · Roadmap e planning — da sabato 14/11 16:30 a domenica 15/11 12:00

Scritta sabato 14/11 alle 16:30. Restano **19 h 30** alla scadenza (dom 12:00 CET), ma l'obiettivo è **consegnare entro le 11:15**.
Tre jolly, tre cappelli: **M** = Motore, **V** = Visione e modellino, **E** = Esperienza (HUD, audio, video, testi).
Il motore (fisica, sim, test) è già scritto e testato nel repo: il lavoro di M è integrarlo e provarlo, non inventarlo.
Quindi la parte rischiosa è **V** (camera + modellino) ed **E** (video): lì va la maggior parte del tempo.

## 0. Regole del piano
1. **Cancelli duri.** A ogni cancello si decide in 5 minuti: passato → si va avanti; non passato → si attiva il piano B scritto, senza discutere.
2. **Sempre una demo funzionante.** Dalle 20:30 esiste una versione registrabile; ogni ora si migliora quella, non se ne costruisce una nuova.
3. **Push ogni ora** su GitHub + copia su chiavetta (il Wi‑Fi della sede non è affidabile).
4. **Una macchina fa la demo, un'altra monta il video, la terza scrive.** Non montare sulla macchina della demo.
5. **Nessuna nuova funzione dopo il blocco del codice (07:30).** Dopo: solo correzioni, video, testi.
6. **Si dorme a turni**, uno alla volta, mai durante un cancello.
7. **Dichiarare sempre** cosa è simulato e cosa è misurato su clip reali.

## 1. Tabella delle fasi

| Fase | Orario | Obiettivo | Cancello (uscita) |
|---|---|---|---|
| P0 Avvio | sab 16:30–17:15 | Iscrizione verificata, repo su GitHub, test verdi su tutti i Mac, ruoli, slot mentor, lista materiali | **G0 17:15** |
| P1 Baseline | 17:15–20:30 | Modellino montato, camera vede il "pedone", coordinate sul piano, motore collegato a eventi reali | **G1 20:30** |
| P2 Cena + mentor 1 | 20:30–21:30 | Allineamento, primo checkpoint, decisioni | — |
| P3 Integrazione | 21:30–00:30 | Anello completo: camera → motore → comando → macchina virtuale → HUD, 4 livelli visibili | **G2 00:30** |
| P4 Rafforzamento | 00:30–04:00 | Guasti (link perso, camera coperta), HUD rifinito, registrazione run con verità a terra | **G3 04:00** |
| P5 Misure | 04:00–07:30 | 25–30 run reali, metriche, tabella e grafico, taratura | **G4 07:30 blocco codice** |
| P6 Riprese | 07:30–09:30 | Video grezzo + checkpoint mentor 2 | **G5 09:30** |
| P7 Montaggio e testi | 09:30–10:30 | Video ≤ 2:45, README, descrizione, licenze | — |
| P8 Consegna | 10:30–11:15 | Checklist 7/7 e invio | **G6 11:15** |
| P9 Margine | 11:15–12:00 | Solo emergenze; preparare chi rappresenta il team alla chiusura | — |

## 2. Dettaglio per fase e per ruolo

### P0 · 16:30–17:15 · Avvio (tutti, 45 min)
- **Subito (5 min):** verificare che tutti e 3 risultino iscritti e il team confermato col telefono del referente. Le iscrizioni chiudono **oggi alle 16:30**.
- **M:** `git init`, push della cartella `repo/` su GitHub (repo pubblico o leggibile alla giuria), `make test && make demo` sul proprio Mac.
- **V:** lista materiali e acquisto/recupero: cartone (scaffali di altezze diverse), scatole, nastro, colla, foglio A4 o carta quadrettata per la pianta, pennarelli, tappi o dischetti colorati saturi (il "pedone"), un supporto/treppiede per iPhone.
- **E:** prenotare i due slot mentor dal sito evento; creare il documento di appunti; copiare le slide-risposte "Possiamo vincere?" da `09-hackathon.md`.
- **Cancello G0 17:15:** i 3 Mac eseguono `make test` (42 test verdi) e `make demo`; repo online; ruoli confermati; slot mentor prenotati.

### P1 · 17:15–20:30 · Baseline (3 h 15)
- **Già pronto (non rifare):** import CAD (`oracolo/cad.py`), scenario magazzino e copertura camere (`warehouse.py`), ricevitore iPhone (`cab.py`, `scripts/run_live.py`), video da simulazione (`make frames`). **Per il vostro magazzino:** esportate il CAD in DXF (layer PERIMETRO e ostacoli con altezza nel nome, es. `SCAFFALI_H3000`) e lanciate `python scripts/run_live.py --dxf vostro.dxf`. **Prima cosa di P1 (M):** provare il server sull'iPhone vero (stessa rete Wi‑Fi o hotspot).
- **V — modellino 1:20.** Pianta 1 cm = 0,2 m. Corsia principale + corsia trasversale cieca come in `scenarios/t_junction.json` (adattare le misure a ciò che avete). Scaffali di cartone alti ≈ 15 cm (=3 m reali) più uno basso (=1 m) per l'asimmetria. Fissare l'iPhone: **camera "sensore"** obliqua a 25–35 cm di altezza, vista dall'angolo della corsia principale. Segnare i quattro angoli per l'omografia. Marker colorato (o ArUco) sul pedone-tappo. Rilevamento HSV/ArUco → punto in pixel → omografia → (x, y) in metri equivalenti → `FrameEvent`.
- **M:** `oracolo/live.py` (nuovo): legge una sorgente di `FrameEvent` (da file JSONL o da camera), ricostruisce la maschera di visibilità dalla posizione della camera e dalla scena, chiama `Oracle.step`, invia `MachineCommand` al bus e scrive un log JSONL. Registrazione/replay dei log. Prime misure di latenza. Se serve: tracking id semplice (distanza minima), perché in simulazione l'identità è perfetta ma dal vivo no.
- **E:** HUD v1 con OpenCV: pianta con celle verde/arancio/rosso (come `oracolo/render.py`), macchina colorata per livello, striscia con livello e limite. Schermata della cabina (livello, velocità, causa) leggibile in 2 secondi. Prima bozza dello script video.
- **Cancello G1 20:30:** l'iPhone vede il tappo che si muove sul modellino, il punto compare sulla pianta nell'HUD, il motore risponde (anche con rumore).
- **Piano B se non passa:** si usa una **clip registrata** con il tappo mosso a mano e si procede col replay; la camera dal vivo diventa "stretch goal".

### P2 · 20:30–21:30 · Cena + mentor 1
- 30 min di cena lontano dallo schermo. Poi allineamento 15 min: cosa funziona, cosa no.
- **Checkpoint mentor 1** (se in calendario): mostrare la baseline; porre le domande della sezione 3 di `09-hackathon.md`.

### P3 · 21:30–00:30 · Integrazione verticale (3 h)
- **M + V:** unire visione e motore dal vivo (o da clip). Calibrare i parametri nella scala del modellino (velocità del pedone, velocità macchina, decelerazione) in modo che i tempi siano credibili sullo schermo.
- **V:** secondo punto di vista: **iPhone zenitale** come verità a terra per le metriche (allineato offline con un battito di mani o un flash).
- **E:** collegare l'HUD agli stati reali: 4 livelli, cause (osservato, persona nascosta, zona non osservata, affidabilità persa), "ignoto ≠ libero". Pagina "cabina" su iPhone Safari (stesso Wi‑Fi o cavo/hotspot): mostra livello e velocità; la macchina virtuale riceve i comandi via UDP (F1).
- **Cancello G2 00:30:** un ciclo completo dal vivo o da clip: macchina che accelera → rallenta all'incrocio cieco → vede il pedone → fermata → riparte, con tutti e 4 i livelli almeno una volta. Registrato in un file video grezzo (anche brutto).
- **Piano B se non passa:** si lavora solo su clip registrate e sul simulatore con rendering offline (`scripts/render_scene.py`): il video usa il simulatore + clip del modellino come prova.

### P4 · 00:30–04:00 · Rafforzamento (3 h 30) — qui iniziano i turni di sonno
- **Guasti (M):** (1) il link UDP cade → la macchina si ferma da sola (watchdog); (2) camera coperta o frame fermo → "affidabilità persa" → FERMA; (3) ritardo e perdita di pacchetti → misurare quanto aumenta lo spazio di arresto. Sono i momenti che convincono la giuria.
- **V:** stabilizzare luce, soglie, marker; ripetibilità del lancio del pedone (stessa traiettoria e tempi).
- **E:** HUD pulito: etichette fisse, palette accessibile (stati distinguibili anche in bianco e nero, come nel documento precedente), banner solo per gli allarmi. Audio con `say -v Alice` per le frasi brevi: «Rallenta», «Fermo», «Zona non visibile».
- **Cancello G3 04:00:** tutti i guasti dimostrabili in ≤ 10 s ciascuno; HUD "da video".

### P5 · 04:00–07:30 · Misure e taratura (3 h 30)
- **V + E:** girare **25–30 run** di 15–25 s: 10 con pedone che esce dall'incrocio cieco a tempi diversi, 5 con pedone visibile, 5 senza pedone (falsi allarmi), 5 con guasto. Ogni run con clip sensore + clip zenitale.
- **M:** script di benchmark sulle clip: tabella (collisioni evitate, distanza minima, rallentamento inutile, tempo di transito, latenza p50/p95, FPS, CPU) e grafico sicurezza‑contro‑produttività (curva di Pareto). Confronto con baseline *nessuno / reattivo / zona fissa*.
- **Dichiarazione onesta:** i numeri del simulatore (README) e quelli sulle clip reali vanno in due tabelle separate.
- **Cancello G4 07:30 — BLOCCO DEL CODICE.** Tag `v1.0-freeze`. Da qui non si aggiungono funzioni.

### P6 · 07:30–09:30 · Riprese (2 h)
- **E:** voce fuori campo (italiano), riprese con iPhone 2 del modellino in azione, schermo HUD in rendering offline (non registrare lo schermo mentre gira).
- **V:** ripetere gli atti della demo; prima ripresa con la macchina fotografica "a occhio" dell'operatore e poi vista dall'alto.
- **M:** README tecnico + sezione limiti + "Lavori correlati" (vedi `01-problema-e-stato-dell-arte.md`), `THIRD_PARTY.md` e `AI_USAGE.md` completati con le licenze verificate.
- **Checkpoint mentor 2** (≈ 08:00–09:00, da confermare): mostrare la versione finale e chiedere cosa manca per il voto pieno.
- **Cancello G5 09:30:** video grezzo completo (tutti gli atti).

### P7 · 09:30–10:30 · Montaggio e testi
- **E:** montaggio (sulla macchina libera) ≤ **2:45**, sottotitoli italiani, controllo durata del file finale.
- **M:** repo pulito, `make test` e `make demo` verdi da un clone fresco; release `v1.0`.
- **V:** descrizione (200–5000 caratteri) e titolo (≤ 100); controllo incrociato con la checklist.

### P8 · 10:30–11:15 · Consegna
- Compilare tutti i campi: challenge, titolo, descrizione, link video (accessibile!), link repo (leggibile), telefono referente, ≥ 2 membri. Checklist 7/7. Premere «Consegna il progetto». **Fare uno screenshot della conferma.**

### P9 · 11:15–12:00 · Margine
- Solo correzioni d'emergenza *prima* della consegna definitiva (dopo non si modifica). Decidere chi rappresenta il team alla chiusura; preparare la risposta a «è già stato fatto?».

## 3. Turni di sonno (uno alla volta)

| Chi | Riposo | Poi |
|---|---|---|
| M | 01:00–03:30 | misure (P5) |
| V | 03:30–06:00 | ripetizione run e riprese |
| E | 06:00–07:30 (+ pausa cena) | riprese e montaggio |

Nessuno dorme durante G1, G2, G4. Chi ha dormito meno di 3 ore non fa modifiche al motore dopo le 05:00.

## 4. Piani A / B / C

| Piano | Quando | Cosa cambia |
|---|---|---|
| **A** (target) | G1–G3 passati | Modellino fisico + iPhone dal vivo + macchina virtuale su UDP + HUD + clip reali per le metriche |
| **B** | G1 o G2 falliti | Replay da clip registrate (stesso motore); iPhone solo come registratore; HUD in rendering offline |
| **C** | Nemmeno B regge alle 02:00 | Simulatore (`bench`, `render_scene`) come prova principale + una clip del modellino come prova di realismo; il video lo dichiara apertamente |

In tutti i casi il motore, i 42 test e il benchmark restano la prova solida.

## 5. Cosa può andare storto (e cosa fare)
| Rischio | Probabilità | Mitigazione |
|---|---|---|
| Omografia imprecisa → coordinate sbagliate | media | Marker ai 4 angoli; verificare su punti noti; se errore > 3 cm usare clip fissa |
| Luce che cambia → HSV instabile | alta | Lampada fissa, esposizione bloccata; ArUco come alternativa |
| Camera via Wi‑Fi a scatti | media | Cavo USB (Continuity Camera) o file registrati |
| Mac che rallenta (nessuna ventola) | media | Rendering offline; chiudere app; demo sul Mac 1 |
| Identità scambiate dal tracking | media | Un solo pedone nel run principale |
| Giuria legge "sistema di sicurezza certificato" | media | Frase fissa: «prototipo di ricerca; la sicurezza reale richiede catena certificata» |
| Video oltre 3:00 | bassa ma fatale | Montare a 2:45 e controllare il file finale |
| Consegna in ritardo | bassa ma fatale | Consegna alle 11:15, non alle 11:55 |
