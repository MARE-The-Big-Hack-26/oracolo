# bighack mare — ClearCorner

Cartella di progetto per **The Big Hack 2026 · Challenge 03 FieldVision (Mare Group)**.
Progetto: **ClearCorner**, rilevazione dei punti ciechi per macchine industriali (camera → 4 livelli di pericolo → comando che rallenta o ferma la macchina).

**Scadenza: domenica 15/11/2026 ore 12:00 CET. Consegna entro le 11:15.**

## Cosa c'è qui
| Percorso | Contenuto |
|---|---|
| `CLAUDE.md` | Contesto per le chat/Claude Code: carica questo per primo |
| `DECISIONI.md` | Registro delle decisioni |
| `docs/` | 00 visione · 01 stato dell'arte · 02 comando alla macchina, costi, fattibilità · 03 motore · 04 visione e modellino · 05 demo e UX · 06 metriche · **07 roadmap** · 08 GitHub · **09 hackathon** (regole, rubrica, «Possiamo vincere?», giuria, video, checklist) · 10 prompt · 11 come continuare nella nuova chat · `templates/` |
| `repo/` | Il progetto Python pronto per GitHub (motore, simulatore, test, CI) |

## Prova in 30 secondi
```bash
cd repo
pip install -r requirements.txt
make test      # 42 test
make demo      # tabella di confronto + caso passo-passo
make frames    # immagini per il video (out/frames)
```

## Da dove ripartire
1. Leggi `docs/07-roadmap.md` (cosa fare ora, cancelli, piani B/C).
2. Segui `docs/11-handoff-nuova-chat.md` per creare il progetto Claude e le chat per ruolo.
3. Pubblica `repo/` su GitHub (`docs/08-github.md`).
