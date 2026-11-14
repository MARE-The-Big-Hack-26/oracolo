# 06 · Metriche e valutazione

Portate pochi numeri, tutti **calcolati dai log**, mai stimati a mano. Il numero più importante è uno: **quante volte il sistema ha segnalato "libero" quando una persona poteva comparire** (falso "libero"). Obiettivo: 0.

## Simulazione sul magazzino (già prodotta: `python -m oracolo.bench --runs 30`)
Magazzino 30 × 20 m importato dal DXF d'esempio, carrello lungo la corsia principale, 2 pedoni che escono dalle corsie laterali con tempi e velocità casuali. Collisione = contatto con il mezzo **in moto**; lo sfioramento con il mezzo fermo si conta a parte.

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

**Messaggio onesto:** (1) dove le camere non vedono, il sistema reattivo collide (7/30) e Oracolo no, ma il carrello deve strisciare (40,8 s); (2) la **copertura** decide il prezzo della sicurezza (44% → 40,8 s, 73% → 19,8 s); (3) con buona copertura anche il reattivo evita le collisioni in questo scenario, quindi il valore di Oracolo sta nei punti ciechi; (4) la zona fissa a 5 km/h ha 10/30 collisioni e 9 sfioramenti perché non guarda dov'è la gente.
Sono numeri di **simulazione** (identità perfetta, nessun rumore): da affiancare ai risultati sulle clip.

## Metriche da produrre sulle clip reali
| Metrica | Definizione | Obiettivo |
|---|---|---|
| Collisioni virtuali | Distanza pedone–macchina < contatto (da verità a terra) | 0 con Oracolo; > 0 con le baseline |
| Margine minimo | Distanza e tempo minimi pedone–macchina | maggiore delle baseline |
| Falso "libero" | Frame con livello 0 mentre una persona poteva raggiungere la traiettoria entro T | 0 |
| Rallentamento inutile | Tempo con velocità ridotta senza pedone nelle vicinanze | basso e dichiarato |
| Transito / velocità media | Tempo per attraversare il percorso | confronto + curva sicurezza‑produttività |
| Previsione di visibilità | Su celle del piano: previsto "visibile/non visibile" vs. osservato | > 90% (da misurare) |
| Latenza end‑to‑end | Frame → comando (p50, p95); FPS; CPU | p95 < 100 ms (obiettivo, da misurare) |
| Robustezza al link | Ritardo, perdita, jitter, perdita totale | fermata sempre entro lo spazio previsto |
| Riconciliazione fantasmi | Quota di fantasmi riconciliati correttamente | dichiarare |

Gli obiettivi sono ipotesi: se i risultati sono diversi, riportate quelli veri e spiegateli.

## Come ottenerle in poche ore
1. 25–30 run (vedi `07-roadmap.md`, P5) con clip sensore + zenitale.
2. Script che rielabora le clip con `oracolo.engine.Oracle` e scrive un JSONL per run.
3. Tabella Markdown + grafico (matplotlib) in README e nel video.
4. Un caso in cui il sistema *sbaglia*, spiegato: aumenta la credibilità.

## Onestà statistica
Campione piccolo (una scena, pochi operatori): scrivetelo. Separate sempre simulazione e clip.
