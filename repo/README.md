# Oracolo — rilevazione dei punti ciechi per macchine industriali

> Prototipo da hackathon (The Big Hack 2026, Challenge 03 FieldVision). NON è un sistema di sicurezza certificato.

## Come funziona (workflow)
1. **Si importa il CAD del magazzino** (DXF): perimetro e ostacoli (scaffali, pilastri, carichi) con la loro altezza (`oracolo/cad.py`).
2. **Una o più camere fisse** (posizione e quota note) vedono carrelli, persone e — calcolate dalla geometria — le **zone d'ombra** (punti ciechi).
3. **Oracolo** tratta l'ignoto come potenzialmente occupato, ricorda le persone sparite dietro un ostacolo e calcola la velocità massima con cui il carrello può ancora fermarsi in tempo → **4 livelli**: NORMALE, ATTENZIONE, RALLENTA, FERMA.
4. Il **comando** (limite di velocità, livello, causa, scadenza) arriva al **sensore/ricevitore sul carrello** che rallenta o ferma. Se i comandi smettono di arrivare, il carrello si ferma da solo (fail-safe).
5. In prototipo il carrello è virtuale e il ricevitore è un **iPhone** (Safari) che riceve i comandi dal **Mac**.

## Prova rapida
```bash
pip install -r requirements.txt
python -m pytest -q                 # 42 test
python -m oracolo.bench --runs 30   # tabella di confronto
make frames                         # video planimetria + cabina (out/demo.mp4)
make live                           # server per l'iPhone: apri http://<IP-del-Mac>:8000 in Safari
python scripts/run_live.py --cut-at 7   # a t=7 s il collegamento cade: l'iPhone va in STOP da solo
python scripts/make_sample_dxf.py       # rigenera il magazzino d'esempio; per il vostro: --dxf file.dxf
```

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
- `tests/` 42 test (fisica verificata anche per forza bruta)

Dichiarazioni: THIRD_PARTY.md, AI_USAGE.md. Limiti e ipotesi: docs/ nel progetto.
