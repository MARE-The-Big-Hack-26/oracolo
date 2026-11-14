# 08 · Repository GitHub

## Struttura (già pronta in `repo/`)
```
oracolo/        motore, simulatore, macchina, render
tests/          42 test (pytest)
scripts/        run_demo.py, render_scene.py
scenarios/      t_junction.json (formato da compilare per il modellino)
.github/workflows/ci.yml   test + benchmark ad ogni push
README.md  THIRD_PARTY.md  AI_USAGE.md  requirements*.txt  Makefile  pyproject.toml
```

## Creazione (5 minuti)
```bash
cd ~/Desktop/"bighack mare"/repo
git init -b main && git add . && git commit -m "Oracolo: motore, simulatore, test"
gh repo create <nome-team>/oracolo --public --source=. --push     # oppure crea il repo dal sito e fai git remote add
```
Il regolamento richiede che il repository sia **leggibile dalla giuria**: pubblico, o con accesso concesso. Controllate da una finestra privata.

## Regole di lavoro
- Branch: `main` sempre verde (CI). Ognuno lavora su `m/…`, `v/…`, `e/…` e fa PR piccole o merge rapido.
- Commit piccoli e frequenti, **push ogni ora**; tag `v1.0-freeze` alle 07:30 e `v1.0` alla consegna.
- Niente file video pesanti nel repo (`.gitignore`): link esterni nel README; tenere solo esempi leggeri in `samples/`.

## Cosa deve contenere il README finale (criterio Chiarezza)
1. Titolo e frase d'impatto + immagine dell'HUD.
2. Un comando per provare: `make test && make demo`.
3. Architettura in un'immagine.
4. Risultati (due tabelle: simulazione e clip reali) con il confronto con le baseline.
5. **Limiti dichiarati** e «non è un sistema di sicurezza certificato».
6. Lavori correlati (da `01-problema-e-stato-dell-arte.md`).
7. Librerie, modelli e uso dell'AI (da `THIRD_PARTY.md` e `AI_USAGE.md`).
8. Come riprodurre le clip e le metriche.

## Licenze
Scegliete una licenza per il vostro codice (es. MIT o Apache-2.0) e aggiungete `LICENSE`; ricordate che il partner ha un'opzione di acquisto di 12 mesi e che organizzatore e partner possono pubblicare il progetto con licenza gratuita non esclusiva (art. 9 del regolamento). Evitate dipendenze con licenze restrittive o dichiaratele (Ultralytics YOLO: AGPL-3.0).

## Cose da altri strumenti (riferimenti)
`supervision` (tracking/annotazioni, MIT), RF-DETR (rilevatore, Apache-2.0), OpenCV (Apache-2.0), shapely (BSD). Verificate ognuna prima di dichiararla e annotate la data in `THIRD_PARTY.md`.
