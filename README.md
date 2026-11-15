# Oracolo — rilevazione dei punti ciechi per macchine industriali

> Prototipo da hackathon (The Big Hack 2026 · Challenge 03 FieldVision, Mare Group). **Non è un sistema di sicurezza certificato.**

**Idea in una riga:** una camera fissa e la planimetria (CAD) della zona permettono di calcolare dove la macchina *non vede*; Oracolo tratta l'ignoto come «potenzialmente occupato» (**ignoto ≠ libero**) e calcola a che velocità il carrello può ancora fermarsi in tempo, con 4 livelli di pericolo e un comando **fail-safe**.

## Come funziona
1. **Si importa il CAD** (file DXF) oppure si **disegna la planimetria** nell'editor 3D integrato. Chi vuole solo provare sceglie una **planimetria di prova** dal menu (aula o magazzino). Il programma normalizza il file (unità → metri, origine in 0,0, perimetro, ostacoli, altezze) e **segnala cosa ha scartato** (porte, testi, quote, oggetti minuscoli): `oracolo/cad_norm.py`.
2. **Una camera fissa** (posizione e quota note) vede persone e carrello. Dalla geometria si calcolano le **zone d'ombra** dietro gli ostacoli.
3. **Oracolo** ricorda le persone sparite dietro un ostacolo, considera libero solo ciò che vede davvero e calcola la **velocità massima** con cui il carrello si ferma in tempo → **4 livelli**.
4. Il **comando** (limite, livello, causa, scadenza) va al ricevitore sul carrello. Se i comandi smettono di arrivare o la camera non coincide più con il CAD, il carrello si ferma da solo.
5. In prototipo il carrello è virtuale; la camera è un **iPhone** su treppiede e il pannello gira su un **Mac**.

### Livelli di pericolo
| Livello | Significato | Azione |
|---|---|---|
| 0 NORMALE | visibilità sufficiente | velocità piena |
| 1 ATTENZIONE | limite appena sotto il massimo | riduzione lieve |
| 2 RALLENTA | collisione possibile se la persona esce dalla zona cieca | riduzione forte |
| 3 FERMA | non c'è margine | arresto |

## Prova rapida (solo simulazione, nessun hardware)
```bash
git clone https://github.com/MARE-The-Big-Hack-26/oracolo
cd oracolo/repo
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
make test      # 131 test
make demo      # tabella di confronto + caso passo-passo
make frames    # immagini per il video (out/frames)
```

## Pipeline con camera reale (iPhone su treppiede → pannello sul Mac)
Dettagli: `docs/12-pipeline-reale.md` e `docs/13-allineamento-cad-video.md`.
```bash
cd oracolo/repo && source .venv/bin/activate
PYTHONPATH=. python scripts/run_camera.py --marker-h 1.2 --worker-h 1.2
```
Il terminale stampa gli indirizzi: **pannello** `http://localhost:8443/` sul Mac e **camera** `https://…trycloudflare.com/camera` da aprire sull'iPhone (tunnel HTTPS: Safari richiede HTTPS per la camera). Con `--no-tunnel` si usa solo la rete locale, ma Safari può rifiutare la camera con il certificato autofirmato.

1. **Planimetria:** nel pannello *Carica DXF*, *Disegna planimetria* oppure *Planimetria di prova…*.
2. **Camera:** l'iPhone, fermo sul treppiede in orizzontale, apre `/camera` e preme *Avvia trasmissione*.
3. **Calibrazione:** a 4 clic, oppure da **marker ArUco a terra** (4–8, id 10–17) in punti noti del CAD.
4. **Allineamento CAD ↔ video:** `OK` se i marker stanno dove il CAD dice; `DEGRADATO` se sono pochi o coperti; `NON_COINCIDE` se la camera si è spostata → banner e comando **FERMA**.
5. **Chi viene riconosciuto:**
   - **Muletto simulato:** una persona che porta in mano un marker ArUco **id 0** (`--marker-h` = quota a cui lo tiene).
   - **Lavoratori:** persone rilevate con HOG (o RF-DETR/YOLO se installati). In più, un **cartello-lavoratore** indossato al petto — un foglio stampato da noi, riconosciuto per forma e confronto con un modello (oppure un marker ArUco id 1–9) — conta come persona certa e sostituisce il riquadro del rilevatore (`--worker-h` = quota del cartello; `--no-worker-tag` per disattivarlo).
6. Il pannello mostra CAD e video sovrapposti, le zone non osservate, il livello e il limite di velocità.

### Prova con camera reale (15/11/2026)
Cosa è stato verificato con l'hardware. I risultati in simulazione (sotto) sono un'altra cosa e non vanno mescolati.

| Voce | Esito |
|---|---|
| Collegamento iPhone → Mac con tunnel HTTPS | **Verificato**: il video dell'iPhone compare nel pannello sul Mac. Con il solo certificato autofirmato Safari ha rifiutato la camera («Camera non disponibile»), per questo il tunnel è attivo di default. |
| Rilevatore di persone usato | HOG (OpenCV), il predefinito |
| Planimetria usata | Disegnata nell'editor: 9,88 × 9,00 m con 4 tavoli di 1,4 × 1,4 m, alti 0,72 m. Camera impostata a x 9,15 m, y 0,3 m, quota 1,57 m (valori inseriti, non ottenuti dalle ancore). |
| Import DXF | **Verificato** nel pannello: magazzino di prova 24 × 14 m con 12 ostacoli; porte, testi e quote scartati con avviso. |

## Risultati in simulazione (30 casi, tempi e velocità casuali dei due pedoni)
Collisione = contatto con il mezzo **in moto**; lo sfioramento con il mezzo già fermo si conta a parte. Sono numeri di **simulazione** (identità perfetta, nessun rumore del sensore).

| Camere fisse | Copertura | Modalità | Collisioni | Sfioramenti (mezzo fermo) | Transito medio |
|---|---|---|---|---|---|
| 1 camera a fine corsia | 44% | none | 13/30 | 0 | 13.8 s |
| 1 camera a fine corsia | 44% | static_zone | 10/30 | 9 | 18.0 s |
| 1 camera a fine corsia | 44% | reactive | 7/30 | 5 | 16.3 s |
| 1 camera a fine corsia | 44% | oracolo | 0/30 | 0 | 40.8 s |
| 1 camera sull'incrocio | 56% | none | 13/30 | 0 | 13.8 s |
| 1 camera sull'incrocio | 56% | static_zone | 10/30 | 9 | 18.0 s |
| 1 camera sull'incrocio | 56% | reactive | 0/30 | 1 | 16.7 s |
| 1 camera sull'incrocio | 56% | oracolo | 0/30 | 0 | 30.2 s |
| 2 camere sugli incroci | 73% | none | 13/30 | 0 | 13.8 s |
| 2 camere sugli incroci | 73% | static_zone | 10/30 | 9 | 18.0 s |
| 2 camere sugli incroci | 73% | reactive | 0/30 | 1 | 16.8 s |
| 2 camere sugli incroci | 73% | oracolo | 0/30 | 0 | 19.8 s |
| 3 camere | 79% | none | 13/30 | 0 | 13.8 s |
| 3 camere | 79% | static_zone | 10/30 | 9 | 18.0 s |
| 3 camere | 79% | reactive | 0/30 | 1 | 16.8 s |
| 3 camere | 79% | oracolo | 0/30 | 1 | 19.7 s |

**Lettura onesta:** dove la camera vede poco (44% dell'area), il sistema che reagisce solo a ciò che vede collide 7 volte su 30 e Oracolo 0, ma il carrello deve strisciare (40,8 s). Con camere sugli incroci (73%) Oracolo resta a 0 collisioni con un costo di 19,8 s contro 13,8 senza sistema: **la copertura delle camere decide il prezzo della sicurezza**, e `coverage()` dice dove metterle. Con buona copertura anche il sistema solo-reattivo evita le collisioni in questo scenario: il vantaggio di Oracolo sta nei punti dove la camera non vede.

## Struttura del codice
- `oracolo/cad.py` import DXF → scena · `oracolo/cad_norm.py` normalizzazione del DXF · `oracolo/warehouse.py` scenario magazzino e copertura camere
- `oracolo/geometry.py` visibilità 2.5D · `oracolo/fog.py` mappa visibile / ricordato / sconosciuto / persona nascosta
- `oracolo/policy.py` fisica: tempo di arresto, curva di frenata, livelli (**deterministica, senza modelli di AI**)
- `oracolo/machine.py` comando con scadenza, bus con ritardo/perdita, macchina virtuale con watchdog, UDP
- `oracolo/cab.py` ricevitore «cabina» (pagina web per l'iPhone, con watchdog)
- `oracolo/vision/` pipeline reale: calibrazione, marker e cartello-lavoratore, allineamento CAD-video, rilevatori, tracking, server e pannello web, planimetrie di prova (`samples/`)
- `oracolo/sim.py`, `bench.py`, `render.py` simulazione, benchmark, video · `tests/` 131 test (la fisica è verificata anche per forza bruta)

## Limiti dichiarati
- **Non è un sistema di sicurezza certificato**: prototipo di ricerca, non va usato per proteggere persone.
- I risultati della tabella sono di **simulazione**; la prova con camera reale è descritta a parte e su un solo ambiente.
- Le **soglie di allineamento** (OK sotto 10 cm, NON_COINCIDE sopra 25 cm per 3 frame) e la **dimensione dei marker** sono ipotesi, tarate solo in parte.
- Con 4 marker a terra una sola coordinata sbagliata può non essere rilevata (con 5–8 sì). La posizione della camera non è stimata: si misura con il metro.
- Il **cartello-lavoratore** è riconosciuto per forma e somiglianza, non ha l'identità certa di un marker ArUco: dà falsi negativi con poca luce, sfocatura o a oltre 3–4 m, e va tenuto in verticale, rivolto alla camera. La soglia è tarata su immagini simulate.
- La demo usa **una persona con un marker al posto del muletto**: non è un veicolo vero, e un marker in mano può oscillare.
- Una sola camera fissa nel prototipo. Il CAD reale non è stato provato (solo file sintetici e un'aula disegnata da noi). Solo formato DXF (niente DWG, STEP, GLB).
- Il **tunnel Cloudflare** (`cloudflared`, scaricato al primo avvio) rende il pannello raggiungibile da chiunque abbia l'indirizzo finché il server è acceso; per un uso non dimostrativo va sostituito da un accesso autenticato.
- Il rilevatore opzionale YOLO ha licenza AGPL-3.0; quello predefinito (HOG) funziona senza.

## Dichiarazioni
- Librerie, modelli e licenze: `repo/THIRD_PARTY.md`.
- Uso dell'AI: `repo/AI_USAGE.md` — il codice è stato scritto con l'assistenza di Claude (Anthropic) e poi letto, eseguito e testato dal team.
- Clip video e prove girate dal team, con il consenso delle persone riprese.

Team «jolly» — The Big Hack 2026.
