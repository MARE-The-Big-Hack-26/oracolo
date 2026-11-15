# 11 · Come continuare nella nuova chat / nel progetto Claude

## Organizzazione consigliata (una volta sola, 5 minuti)
1. Creare un **Progetto Claude** chiamato «bighack mare — ClearCorner».
2. Caricare nei file del progetto: `CLAUDE.md`, `DECISIONI.md`, `README.md` e tutta la cartella `docs/` (soprattutto `07-roadmap.md` e `09-hackathon.md`). Se il progetto accetta istruzioni, incollare il contenuto di `CLAUDE.md`.
3. Aprire **chat separate per ruolo** (Motore, Visione, Esperienza, Documenti) dentro il progetto. Ogni chat parte con il prompt di apertura di `10-prompts.md`.
4. Se usate Claude Code sul repo: aprire il terminale in `repo/`; `CLAUDE.md` della radice dà il contesto.
5. A fine fase: aggiornare `DECISIONI.md` (cosa è stato deciso e perché) e fare push.

## Perché separare le chat
Chat lunghe diventano confuse e perdono i dettagli. Una chat per ruolo tiene il contesto corto; il progetto e i file tengono la memoria comune.

## Cosa dire alla nuova chat per ripartire subito
> Siamo il team «bighack mare», challenge FieldVision, idea ClearCorner (rilevazione punti ciechi → limite di velocità → comando fail-safe). Il codice del motore è in `repo/` con 42 test verdi e un benchmark. Leggi `CLAUDE.md` e `docs/07-roadmap.md`. Sono le [ora] di [giorno], siamo in fase [P?]. Cosa facciamo adesso?

## Cartella
Tutto è in `~/Desktop/bighack mare/`:
```
README.md  CLAUDE.md  DECISIONI.md
docs/    00…11 + templates/
repo/    il progetto Python pronto per GitHub
```
