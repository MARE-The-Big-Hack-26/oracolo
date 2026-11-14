# Oracolo — rilevazione dei punti ciechi per macchine industriali

> Prototipo da hackathon (The Big Hack 2026, Challenge 03 FieldVision). NON è un sistema di sicurezza certificato.

## Come funziona (workflow)
1. **Si importa il CAD del magazzino** (file DXF) oppure si **disegna la planimetria** nell'editor integrato. Il programma normalizza il file (unità, origine, perimetro, ostacoli, altezze) e segnala cosa ha scartato (`oracolo/cad.py`, `oracolo/cad_norm.py`).
2. **Una o più camere fisse** (posizione e quota note) vedono carrelli, persone e — calcolate dalla geometria — le **zone d'ombra** (punti ciechi).
3. **Oracolo** tratta l'ignoto come potenzialmente occupato, ricorda le persone sparite dietro un ostacolo e calcola la velocità massima con cui il carrello può ancora fermarsi in tempo → **4 livelli**: NORMALE, ATTENZIONE, RALLENTA, FERMA.
4. Il **comando** (limite di velocità, livello, causa, scadenza) arriva al **sensore/ricevitore sul carrello** che rallenta o ferma. Se i comandi smettono di arrivare, il carrello si ferma da solo (fail-safe).
5. In prototipo il carrello è virtuale e il ricevitore è un **iPhone** (Safari) che riceve i comandi dal **Mac**.

## Prova rapida
```bash
git clone https://github.com/MARE-The-Big-Hack-26/oracolo
cd oracolo/repo
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
make test      # 110 test
make demo      # tabella di confronto + caso passo-passo (simulazione)
make frames    # immagini per il video (out/frames)
```

## Pipeline con camera reale (iPhone su treppiede → pannello sul Mac)
Dettagli: `docs/12-pipeline-reale.md` e `docs/13-allineamento-cad-video.md`.
```bash
make camera    # server HTTPS: pannello Mac https://localhost:8443/  ·  iPhone https://<IP-Mac>:8443/camera (QR nel pannello)
```
1. Nel pannello: **Carica DXF** oppure **Disegna planimetria** (non esiste una stanza predefinita).
2. L'iPhone, fisso su treppiede, apre la pagina `/camera` e invia il video al Mac.
3. **Calibrazione:** a 4 clic, oppure automatica da **4 marker ArUco a terra** (id 10–13) in punti noti del CAD.
4. **Allineamento CAD ↔ video:** se i marker a terra risultano dove il CAD dice → `OK`; se sono pochi o coperti → `DEGRADATO`; se la camera è stata spostata → `NON_COINCIDE`, banner nel pannello e comando **FERMA** (ignoto ≠ libero).
5. Riconosce persone (RF-DETR o HOG) e un muletto simulato da una **sedia con marker ArUco** (id 0); il pannello mostra il CAD sovrapposto al video, le zone non osservate, il livello e il limite di velocità.

**Stato della verifica:** testato con camera sintetica e browser headless (110 test). Prova con iPhone, treppiede e marker stampati: *[DA COMPILARE dopo la prova in aula: errori misurati in cm, rilevatore usato, fps]*.

## Livelli di pericolo
| Livello | Significato | Azione |
|---|---|---|
| 0 NORMALE | visibilità sufficiente | velocità piena |
| 1 ATTENZIONE | limite appena sotto il massimo | riduzione lieve |
| 2 RALLENTA | collisione possibile se la persona esce dalla zona cieca | riduzione forte |
| 3 FERMA | non c'è margine | arresto |

## Risultati in simulazione (30 casi con tempi e velocità casuali dei due pedoni)
Collisione = contatto con il mezzo **in moto**; lo sfioramento con il mezzo già fermo si conta a parte. Numeri di SIMULAZIONE (identità perfetta, nessun rumore del sensore): vanno affiancati ai risultati sulle clip reali.

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

## Struttura
- `oracolo/cad.py` import DXF → scena · `oracolo/warehouse.py` scenario magazzino + copertura camere
- `oracolo/geometry.py` visibilità 2.5D · `oracolo/fog.py` mappa visibile / ricordato / sconosciuto / persona nascosta
- `oracolo/policy.py` fisica: tempo di arresto, curva di frenata, livelli
- `oracolo/machine.py` comando con TTL, bus con ritardo/perdita, macchina virtuale con watchdog, UDP
- `oracolo/cab.py` ricevitore "cabina" (server web per l'iPhone, con watchdog nella pagina)
- `oracolo/sim.py`, `bench.py`, `render.py` simulazione, benchmark, video
- `oracolo/cad_norm.py` normalizzazione DXF · `oracolo/vision/` pipeline reale (calibrazione, marker, allineamento, rilevatori, tracking, server e pannello web)
- `tests/` 110 test (fisica verificata anche per forza bruta)

## Limiti dichiarati
- **Non è un sistema di sicurezza certificato**: prototipo di ricerca.
- I risultati della tabella sono di **simulazione** (identità perfetta, nessun rumore del sensore) e vanno letti separatamente dalle prove con camera reale.
- Le **soglie di allineamento** (OK sotto 10 cm, NON_COINCIDE sopra 25 cm per 3 frame) e la **dimensione dei marker** (20 cm consigliati, 15 cm minimo) sono ipotesi o simulazioni, non misure con l'iPhone.
- Con 4 marker a terra una coordinata sbagliata su uno solo può non essere rilevata: controllare anche la sovrapposizione CAD-video. La posizione della camera si misura col metro.
- Una sola camera fissa nel prototipo; il CAD vero non è stato provato (solo file sintetici). Solo formato DXF.
- Il rilevatore YOLO (opzionale) ha licenza AGPL-3.0; il rilevatore predefinito funziona senza.

Dichiarazioni: `repo/THIRD_PARTY.md` (librerie e licenze), `repo/AI_USAGE.md` (uso dell'AI). Altri documenti: `docs/`.
