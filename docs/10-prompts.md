# 10 · Prompt pronti per le chat di lavoro

Usate **una chat per ruolo**, tutte dentro lo stesso progetto Claude (vedi `11-handoff-nuova-chat.md`). Il contesto è nel file `CLAUDE.md`.

## Apertura di ogni chat
> Leggi `CLAUDE.md`, `DECISIONI.md` e `docs/07-roadmap.md`. Siamo nella fase **[P?]**, tocca a **[M/V/E]**. Il prossimo cancello è **[G?]** alle **[ora]**. Dimmi in 5 righe cosa fare adesso e cosa può andare storto.

## Chat Motore (M)
> Aggiungi `oracolo/live.py`: legge `FrameEvent` da JSONL o da una coda, costruisce la maschera di visibilità dalla posizione/quota della camera, chiama `Oracle.step`, invia `MachineCommand` al bus e scrive un log JSONL con latenza per frame. Scrivi i test prima. Non cambiare i parametri senza chiedere.

> Scrivi lo script di benchmark sulle clip: input = cartella di run (JSONL sensore + verità a terra), output = tabella Markdown + grafico PNG (collisioni, distanza minima, rallentamento inutile, transito, latenza p50/p95).

## Chat Visione (V)
> Sul modellino 1:20 con questa pianta [scenarios/…json]: scrivi `vision/detect.py` che prende un frame, trova il marker colorato in HSV (o ArUco), applica l'omografia (4 punti dati) e restituisce `FrameEvent`. Mostra come tarare le soglie in 2 minuti e come calcolare l'errore di omografia su punti noti.

## Chat Esperienza (E)
> Costruisci l'HUD con OpenCV partendo da `oracolo/render.py`: pianta, livello, limite, causa, scala dei 4 livelli, salute. Palette Okabe–Ito, stati leggibili senza colore. Poi la pagina "cabina" per Safari e le frasi audio con `say -v Alice`.

> Aiutami a montare il video seguendo lo script di `09-hackathon.md` §7, durata finale ≤ 2:45, sottotitoli italiani.

## Chat Documenti
> Compila `docs/templates/descrizione-consegna.md` (200–5.000 caratteri) con i risultati veri in `docs/06-metriche.md`. Controlla che nessun numero sia inventato.

## Regole per tutte le chat
- Non inventare numeri: ogni cifra viene da un log o è marcata «indicativa».
- Non dire «sistema di sicurezza» né «certificato».
- Prima di toccare il motore: `make test`. Dopo: di nuovo.
- Dopo il blocco del codice (07:30): niente nuove funzioni.
