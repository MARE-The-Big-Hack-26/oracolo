# 03 · Il motore (cosa fa ogni modulo e come si usa)

Tutto in `repo/oracolo/`. Nessun import di OpenCV nel motore: si testa senza camera.

| Modulo | Ruolo |
|---|---|
| `geometry.py` | Visibilità 2.5D: poligono di visibilità (ray-casting esatto sui vertici), `line_of_sight` con quote, `mutual_visibility` / `classify_pair` (reciproca, solo A vede B, solo B vede A, cecità reciproca), `visible_distance_along` |
| `fog.py` | Mappa epistemica su griglia (0,2 m): VISIBILE / RICORDATO_LIBERO / SCONOSCIUTO / PERSONA_NASCOSTA. Contaminazione che avanza alla velocità del pedone nelle zone nascoste; TTL della memoria; fantasmi per ogni pedone sparito; riconciliazione se riappare |
| `policy.py` | Fisica: tempo di arresto, `v_safe = a·(TTR − T)`, curva di frenata, minimo sul percorso, livelli, cause, affidabilità (frame fermo, salute scena) |
| `engine.py` | `Oracle.step(t, seen, vis_mask, s, pts, health, frame_age) → Decision`: l'API unica per simulatore e pipeline reale |
| `machine.py` | `MachineCommand`, bus con ritardo/jitter/perdita, UDP, macchina virtuale con watchdog TTL |
| `sim.py` | Simulatore a ciclo chiuso, 4 modalità: `none`, `static_zone`, `reactive`, `oracolo` |
| `bench.py`, `render.py` | Benchmark a tabella; immagini/frame per README e video |
| `cad.py` | Import DXF → `Scene`: perimetro (layer PERIMETRO/MURI), ostacoli = polilinee chiuse e cerchi; altezza dal nome del layer (`SCAFFALI_H3000`); unità da INSUNITS |
| `warehouse.py` | Scenario magazzino (CAD + camere fisse + carrello + persone) e `coverage()` = quota di area vista dalle camere |
| `cab.py` | Ricevitore "cabina": server web per l'iPhone con watchdog nella pagina |
| `contracts.py` | `Observation` e `FrameEvent`: l'interfaccia tra visione e motore |

## Livelli
Con `r = limite / v_max`: **r < 0,05 → 3 FERMA; r < 0,60 → 2 RALLENTA; r < 0,95 → 1 ATTENZIONE; altrimenti 0 NORMALE.** Le cause: `osservato`, `persona_nascosta`, `zona_non_osservata`, `affidabilita_persa`, `scena_degradata`.

## Parametri (ipotesi dichiarate, `VehicleParams`)
v_max 2,2 m/s (~8 km/h), a_brake 1,5 m/s², t_sys 0,25 s, t_act 0,15 s, margine 0,5 m, semi-larghezza 0,6 m, orizzonte 12 m, frame_age massimo 0,30 s; pedone: 1,5 m/s, raggio 0,3 m. Vanno ricalibrati per ogni macchina reale.

## Perché è affidabile (e dove no)
- 42 test: la formula `v_safe` e la curva di frenata sono verificate in modo indipendente; il watchdog, la perdita di messaggi e l'ordine dei comandi sono testati.
- **Limiti noti:** identità dei pedoni perfetta in simulazione; dilatazione 3×3 conservativa (sulle diagonali il fronte avanza fino a 1,41× più veloce); un solo piano 2D con altezze; modello di frenata a decelerazione costante; nessun rumore del sensore nel simulatore.

## Come usarlo
```python
from oracolo.engine import Oracle
from oracolo.scenes import t_junction
oracle = Oracle(t_junction())
# ad ogni frame:
dec = oracle.step(t, seen, vis_mask, s, pts, health=1.0, frame_age=0.05)
print(dec.level_name, dec.limit, dec.cause)
```
