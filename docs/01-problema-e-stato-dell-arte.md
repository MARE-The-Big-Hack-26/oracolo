# 01 · Problema e stato dell'arte (da usare nella sezione "Lavori correlati" del README)

Ricerca del 14/11/2026, rapida: «non trovato» non significa «non esiste». Se un giurato chiede «è già stato fatto?»:
**«Il concetto di base sì. Questo è ciò che cambia: …»** (vedi la tabella).

## Cosa esiste già
| Cosa | Esempi | Cosa fa | Limite rispetto a noi |
|---|---|---|---|
| Rilevamento pedoni a bordo/retrofit | Blaxtair, Powerfleet, Davis Derby AI Alert, VIA Mobile360 | Camera AI sul mezzo, allerta e talvolta riduce la velocità | Reagisce a ciò che vede; zone fisse |
| Controllo velocità per zone | Linde Safety Guard, retrofit tipo FleetRabbit, RCT | Velocità massima in aree definite | Zona statica, non dipende da cosa si vede |
| Prossimità con tag | UWB (Trio Mobil) | Distanza dai tag indossati | Richiede tag a tutte le persone |
| Pianificazione con zone cieche | FRENETIX-Occlusion, Scene Informer (guida autonoma) | Agenti fantasma nelle zone non viste | Pensata per auto, non per carrelli/magazzini |

Fonti: pagine prodotto citate nella sezione "Fonti" in fondo; per FRENETIX-Occlusion arXiv 2402.01507, Scene Informer arXiv 2309.13893.

## Cosa aggiungiamo (e cosa no)
- **Aggiungiamo:** un limite di velocità *derivato* dal punto cieco con fisica esplicita, memoria con scadenza ("ignoto ≠ libero"), comando fail-safe con TTL, e la misura del compromesso sicurezza–produttività.
- **Non aggiungiamo:** un sensore nuovo, un nuovo rilevatore di persone, un prodotto certificato.
- **Onestà:** i concetti di fantasma/occlusione vengono dalla guida autonoma; la trasposizione al contesto industriale e il confronto con zone fisse sono il contributo.

## Standard e limiti
- ISO 13849-1, IEC 62061 e IEC 61508 non contengono requisiti specifici per l'AI (DGUV Test Information n. 05, 2021). ISO/IEC TR 5469:2024 è un rapporto tecnico su sicurezza funzionale e AI.
- Il consiglio ricorrente nell'industria: non promuovere un sistema di visione AI generico a funzione di sicurezza; usarlo come livello non-safety che informa il controllo, con la catena di sicurezza separata.
