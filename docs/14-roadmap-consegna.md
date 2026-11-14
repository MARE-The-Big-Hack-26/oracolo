# 14 · Roadmap della mattina di consegna (dom 15/11)

**Vincoli:** consegna entro le **12:00**, obiettivo **11:15**. Si parte alle 09:00, quindi restano ~2 h 15 min utili: il code freeze delle 07:30 è saltato, **nessuna funzione nuova, solo prova, video, README, consegna**. Se si riesce a iniziare prima (08:00), tutto sotto diventa più comodo.

Ruoli proposti (adattare): **P1** hardware e calibrazione · **P2** planimetria e prove sedia/persona · **P3** README, video, modulo di consegna.

## Orari
| Ora | Cosa | Chi |
|---|---|---|
| 09:00–09:10 | `git pull` su tutti i Mac, `make test` (110 test), `make camera`. Dividersi i ruoli | tutti |
| 09:10–09:25 | Misurare l'area di prova: origine (0,0) in un angolo, larghezza × profondità, ostacoli (angolo, larghezza, profondità, altezza). Mettere 1–2 oggetti alti per creare un punto cieco | P1 + P2 |
| 09:10–09:25 | Stampare i marker (4 ancore + sedia) se non già fatto; leggere `docs/15-testo-consegna.md` e il README bozza (ramo `readme-finale`) | P3 |
| 09:25–09:40 | Disegnare la planimetria in `/room` (**Disegna planimetria**) con le misure; incollare 4 ancore a terra e misurarne il centro; misurare la camera (x, y, altezza) | P2 / P1 |
| 09:40–10:10 | iPhone: aprire il QR, accettare certificato, **Calibra camera → Ancore a terra → Calibra da ancore**. Obiettivo: stato `OK` e CAD sovrapposto al video | P1 |
| **10:15** | **Taglio:** se l'iPhone live non è calibrato, passare al piano B/C (sotto). Niente debug oltre questa ora | tutti |
| 10:10–10:30 | Registrare lo schermo (Cmd+Shift+5): 1) Carica DXF + avvisi 2) camera live con livelli 3) treppiede urtato → banner e FERMA 4) due marker coperti → DEGRADATO 5) sedia + persona. Annotare gli errori in cm | P1 + P2 |
| 10:10–10:40 | Montaggio video ≤ 3:00 (target 2:45), sottotitoli in italiano, caricarlo (link visibile senza login), controllare il file finale | P3 |
| 10:30–10:50 | README finale: inserire i risultati reali (cm, prove) senza inventare numeri; unire a `main`; aprire la repo da una finestra privata | P3 + P2 |
| 10:50–11:15 | Modulo di consegna (titolo ≤ 100 caratteri, descrizione 200–5.000, link video, link repo, telefono del referente, ≥ 2 membri), checklist 7/7, **«Consegna il progetto»**, screenshot della conferma | P3 + referente |
| 11:15–12:00 | Margine. **Nessun push** su `main` dopo la consegna | — |

## Piani di ripiego
- **B (iPhone live non va entro le 10:15):** registrare con l'app Fotocamera un video dell'area con ancore, sedia e persona, mandarlo al Mac con AirDrop e lanciare `make camera` con `--source video:PERCORSO --loop`. La calibrazione si fa sullo stesso video.
- **C (neanche il video funziona):** video con la simulazione (`make demo`, `make frames`, clip in `demo/`) più la registrazione dello schermo di Carica DXF e allineamento, **dichiarando chiaramente "simulazione"**.
- Non inventare numeri: ogni cifra viene da un log o è marcata «indicativa».

## Comandi utili
```
cd ~/Desktop/oracolo && git pull
cd repo && source .venv/bin/activate
make test
make camera              # pannello: https://localhost:8443/  ·  iPhone: https://<IP-Mac>:8443/camera
```
Marker: `markers/marker_ancora_ID10…13_20cm_A3.pdf` (o `…_15cm_A4.pdf`, minimo), stampa al 100%, misurare il lato nero col righello e scrivere il valore vero nel pannello. Sedia: `markers/marker_muletto_ID0_A4.pdf`, a ~45 cm da terra, lato alto verso la marcia.

## Cosa NON è verificato (dirlo, non nasconderlo)
Safari/iPhone dal vivo, marker stampati, treppiede, un CAD vero, soglie di allineamento (10 cm / 25 cm: ipotesi), rilevatore di persone su clip reali.
