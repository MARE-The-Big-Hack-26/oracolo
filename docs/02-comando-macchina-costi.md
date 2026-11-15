# 02 · Come arriva il comando alla macchina, costi e fattibilità

## 1. Come simulare l'input che ferma o rallenta il macchinario (con solo iPhone + Mac)
Si simula il **livello di comando**, non la meccanica. Il formato è lo stesso che userebbe un impianto reale.

```
Camera → ClearCorner (decisione) → MachineCommand → [canale] → Macchina (controller) → freno/velocità
```

`MachineCommand = { seq, t_sent, speed_limit [m/s], level 0..3, cause, ttl [s] }`

**Principio fail-safe.** La macchina può muoversi *solo finché riceve comandi validi e freschi*. Un comando ha una scadenza (`ttl`, default 0,25 s): se non ne arriva uno nuovo la macchina scende a velocità zero da sola (watchdog). Quindi un messaggio "stop" perso non è un problema: la sicurezza non dipende dal fatto che lo stop arrivi, ma dal fatto che il "via libera" continui ad arrivare. È lo stesso principio dei circuiti di sicurezza a diseccitazione.

| Fedeltà | Cosa è | Dove | Stato |
|---|---|---|---|
| **F0** | Macchina virtuale nello stesso processo, con ritardo, jitter e perdita di messaggi | `oracolo/machine.py` (`InProcessBus`, `VirtualMachine`) | **fatto, testato** |
| **F1** | Ricevitore in un altro dispositivo: pagina web su iPhone (HTTP, polling 80 ms) oppure UDP/JSON | `CabServer` in `oracolo/cab.py`; `UdpSender`/`UdpReceiver` | **fatto, testato** (server su loopback; telefono da provare sul Wi‑Fi) |
| **F2** | Tag industriali: OPC UA (es. libreria `asyncua`) o Modbus TCP (`pymodbus`): il comando scrive un tag `SpeedLimit` e un `Heartbeat` | da aggiungere (stessa interfaccia) | opzionale; verificare le licenze prima di dichiararle |
| **F3** | Ingresso reale a un PLC / limitatore di velocità | — | descritto come percorso, non fatto |

**Demo con iPhone (già implementata):** `python scripts/run_live.py` avvia sul Mac un piccolo server (`oracolo/cab.py`); sull'iPhone, nella stessa rete Wi‑Fi, si apre in Safari `http://<IP-del-Mac>:8000`. La pagina è il ricevitore del carrello: mostra livello, limite in km/h e causa, e **contiene il watchdog**: se non arriva un comando nuovo entro la scadenza va in STOP da sola. `--cut-at 7` simula il collegamento che cade a t=7 s. Per il video: schermo dell'iPhone + vista dall'alto (`make frames`).

**Cosa dimostrare nel video (30 s):** (1) il limite scende vicino all'incrocio cieco; (2) taglio del link → la macchina si ferma da sola; (3) camera coperta → FERMA con motivo "affidabilità persa".

## 2. Perché la decisione è questa (fisica in 5 righe)
Con decelerazione *a* e latenza totale *T* (sensing + decisione + comunicazione + attuazione) il tempo di arresto da velocità *v* è T + v/a. Perché una persona che può raggiungere la traiettoria tra TTR secondi non venga investita: T + v/a ≤ TTR, cioè **v ≤ a·(TTR − T)**. Per arrivarci in tempo si applica la curva di frenata lungo il percorso. Il limite finale è il minimo su tutti i punti in avanti. Vedi `03-motore.md`.

## 3. Quanto costa? (cifre indicative)
> **Attenzione.** Le cifre vengono quasi tutte da pagine di fornitori o blog di settore e vanno ri-verificate; non sono preventivi. Usatele come ordine di grandezza e dichiaratelo.

| Voce | Ordine di grandezza | Note |
|---|---|---|
| Rilevamento prossimità/retrofit per veicolo | ~500–3.000 $ per veicolo (indicativo) | Dipende da sensori, tag, installazione |
| Camera AI retrofit | da circa 500–700 $ (hardware camera) a diverse migliaia con kit completo | Installazione tipica di qualche ora per veicolo (fonte: Blaxtair) |
| Visione per punti ciechi (valore storico) | circa 5–6 mila $ per veicolo | Dato datato; solo come ordine di grandezza |
| Computer di bordo (es. Jetson Orin Nano) | 249 $ al lancio, poi segnalato più alto e con disponibilità limitata | Verificare il prezzo a oggi |
| Software/abbonamento | spesso a canone annuo | Dipende dal fornitore |
| Costo di un incidente | oltre 180.000 $ per un singolo incidente di carrello (stima di un fornitore); circa 41.000 $ di indennizzo medio per infortunio (stima citata da un fornitore, fonte NCCI) | Cifre di marketing: usarle con cautela |

**Formula di ritorno** (da mostrare, con i vostri numeri): `ROI = (incidenti/anno × costo medio × riduzione attesa) − (hardware ÷ vita utile + canone + manutenzione)`. Una flotta di 20 veicoli a ~3.000 $/veicolo è ~60.000 $ di investimento iniziale: si ripaga se evita anche un solo incidente grave in qualche anno. Nel pitch dite *quale ipotesi* usate.

**Costo del prototipo vostro:** 0 € in più (3 iPhone + 3 Mac + cartone).

## 4. È fattibile per un'azienda?
**Sì, a gradini, con un'avvertenza.**
1. **Modalità ombra** (mesi 0–2): il sistema calcola e registra ma non agisce; si misura quante volte *avrebbe* rallentato/fermato e se aveva ragione. Costo basso, rischio zero.
2. **Solo avvisi** (mesi 2–4): luci/suono per l'operatore.
3. **Limitatore morbido**: riduzione di velocità tramite il controller del veicolo (non è una funzione di sicurezza).
4. **Integrazione con la catena di sicurezza**: solo con sensori e controllori certificati; ClearCorner informa, non sostituisce.

**Cosa non si può dire:** che una camera con AI possa fermare un carrello come funzione di sicurezza certificata. Le norme non lo prevedono e i fornitori seri lo dicono.

**Il vantaggio concreto per l'azienda:** funziona *dove non c'è un sensore addosso a ogni persona*, usa le camere che molti impianti hanno già, e dà una **misura** del compromesso: «questa configurazione costa X secondi di produttività per evitare Y quasi-incidenti».

## 5. Fonti (ricerca 14/11/2026)
- Blaxtair, guida retrofit flotta mista: https://blaxtair.com/en/blog/retrofit-safety-system-mixed-fleet-guide
- Powerfleet, Pedestrian Proximity Detection: https://powerfleet.com/?p=50952
- Trio Mobil, guida all'acquisto: https://www.triomobil.com/en/blog/forklift-pedestrian-detection-systems-a-buyers-guide
- DGUV Test Information 05 (AI e sicurezza): https://publikationen.dguv.de/widgets/pdf/download/article/4604
- KAN, AI e sicurezza funzionale: https://www.kan.de/en/publications/kanbrief/2022/2-22/artificial-intelligence-in-the-context-of-functional-safety/
