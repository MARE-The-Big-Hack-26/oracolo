# 09 · Tutto per l'hackathon (regole, rubrica, "Possiamo vincere?", giuria, video, checklist)

Contesto: The Big Hack 2026, **Challenge 03 FieldVision (Mare Group)**, Città della Scienza, Napoli. Team di 3 "jolly". Dettaglio regolamento nel documento «FieldVision — Guida definitiva» (stessa fonte di questa tabella).

## 1. Regole che cambiano il piano
| Regola | Cosa implica |
|---|---|
| Consegna entro **dom 15/11 ore 12:00 CET**; dopo si blocca tutto | Consegnare entro le **11:15** |
| Campi obbligatori: challenge, titolo (≤ 100 car.), descrizione (200–5.000 car.), link video, link repo, telefono referente, ≥ 2 membri | Checklist 7/7; senza non si attiva «Consegna il progetto» |
| Video ≤ **3 minuti**, pena l'esclusione | Montare a 2:45 e verificare il file finale |
| Voto: 5 criteri da 1 a 5 per ogni giurato | Design e chiarezza pesano quanto l'algoritmo |
| **≥ 2 checkpoint con i mentor**, altrimenti progetto non valido | Prenotare subito i due slot |
| Presenza in sede 14–15/11; almeno un rappresentante alla chiusura | Allontanamenti da concordare |
| Progetto originale; team conserva i diritti; organizzatore e partner possono pubblicarlo (licenza gratuita non esclusiva) | Dichiarare librerie, modelli e uso dell'AI |
| Partner con opzione di acquisto di 12 mesi sul vincitore | Evitare licenze restrittive o dichiararle |
| Lingua ufficiale italiana | Video, descrizione e audio in italiano, con sottotitoli |
| Una sola challenge per team | — |
| Nei video solo i compagni di squadra, con consenso | Niente riprese di terzi |
| Iscrizioni chiuse sabato 16:30 | Verificato prima di tutto |

## 2. Rubrica (5 criteri) → come li provate
| Criterio | Cosa deve vedere il giurato | Dove lo provate |
|---|---|---|
| **Utilità / Valore** | Un problema con un costo reale (infortuni nei magazzini) e una garanzia: la macchina rallenta *prima* di vedere il pedone | Primi 25 s del video; tabella con 0 collisioni; costo e fattibilità |
| **Attinenza alla challenge** | I 4 obiettivi spuntati uno a uno: rilevare, gestire l'occlusione, distinguere osservato da incerto, segnalare la perdita di affidabilità | Una riga per obiettivo in descrizione e video (tabella in `00-visione.md`) |
| **Chiarezza e completezza** | Un comando per la demo (`make demo`), immagine di architettura, limiti dichiarati | README + descrizione |
| **Design / UX** | Schermo leggibile in 2 secondi, stati distinguibili anche in bianco e nero | HUD + cabina |
| **Creatività / Innovazione** | Limite di velocità derivato dal punto cieco, "ignoto ≠ libero", comando fail-safe, misura del prezzo della sicurezza | Secondo atto del video; confronto con le baseline |

## 3. Possiamo vincere? (valutazione onesta, rifatta per questa idea)
**In breve:** sì, è un'idea da podio *se* la demo fisica funziona e il video è chiaro. Non è una garanzia e non possiamo sapere cosa porteranno gli altri team.

**Perché è forte**
- **Concreta e comprensibile in 10 secondi:** «la macchina rallenta prima di vedere il pedone». Una giuria generica la capisce senza spiegazioni.
- **Prove, non promesse:** codice testato (42 test), simulazione sul magazzino con confronto contro baseline (con camera che vede poco: 0/30 collisioni contro 13/30 senza sistema, 10/30 con zona fissa, 7/30 solo reattivo) e un compromesso misurato (copertura delle camere vs produttività).
- **Onestà tecnica:** dichiariamo cosa non è (non certificato) e i limiti. Questo di solito *aumenta* la credibilità con giurati tecnici.
- **Tema sociale e industriale** (sicurezza sul lavoro), costo e fattibilità già pensati, e percorso di adozione a gradini: piace al partner.
- **Il motore non dipende da una AI** specifica: nessun rischio di licenza o di modello che non funziona.

**Perché potrebbe non bastare**
- **Il concetto non è nuovo:** esistono limitatori per zone e rilevamento pedoni; i fantasmi/occlusioni vengono dalla guida autonoma. Va detto in modo preciso (sezione 6) e il vantaggio è nell'integrazione e nella misura.
- **FieldVision è una sfida di visione:** se nel video "la visione" è solo un marker colorato, un giurato può dire che la parte di computer vision è debole. Mitigazione: mostrare almeno **una clip reale** con un rilevatore di persone vero (anche con limiti dichiarati) e spiegare che il motore è indipendente dal rilevatore.
- **Rischio demo:** un modellino che non funziona dal vivo pesa molto. Mitigazione: piani B/C e clip registrate.
- **Rischio di sembrare "solo geometria":** serve la parte visiva (HUD, atto 2 con la collisione senza sistema).

**Stima mia (non una misura), 1–5:** Utilità 4–5 · Attinenza 4 · Chiarezza 4–5 (dipende dal README) · Design/UX 3–4 (dipende da quanto curate l'HUD) · Innovazione 3–4. Con esecuzione pulita: candidata realistica al podio della challenge; con una demo traballante scende in fretta.

**Cosa sposta di più la probabilità:** (1) una demo ripetibile e bella, (2) un video da 2:45 senza tempi morti, (3) i numeri onesti con baseline, (4) rispondere bene a «è già stato fatto?» e a «è sicuro?».

## 4. Domande che può fare la giuria (e risposte)
| Domanda | Risposta breve |
|---|---|
| È già stato fatto? | Il concetto di zone di velocità e il rilevamento pedoni sì. Qui il limite deriva dalla **zona cieca** e dalla fisica dello spazio di arresto, con memoria "ignoto ≠ libero" e comando fail-safe; e misuriamo il compromesso sicurezza–produttività. |
| È un sistema di sicurezza certificato? | No. È un prototipo di ricerca. Per uno stop reale serve una catena certificata (relè/PLC di sicurezza); Oracolo è un livello che avvisa e limita. |
| Perché non usare un modello AI per tutto? | Il motore è deterministico e verificabile; l'AI serve solo per vedere le persone ed è sostituibile. Così il comportamento si può spiegare e testare. |
| Come funziona se la rete cade? | Il comando ha una scadenza: se non ne arriva uno nuovo la macchina si ferma da sola (watchdog). Lo mostriamo nel video. |
| Quanto costa per un'azienda? | Ordine di grandezza di centinaia–migliaia di € a veicolo per un retrofit; il nostro prototipo usa camere già presenti. Cifre indicative e da verificare (vedi `02`). |
| E se il rilevatore sbaglia? | Se la scena si degrada o il frame è fermo, il sistema va in stato sicuro; il rilevatore sbagliato è un caso dichiarato nei limiti. |
| Quanto è veloce? | Latenza misurata e dichiarata (p50/p95), con FPS e CPU. |
| Funziona con altri dispositivi? | Sì: il motore riceve eventi (id, posizione); la camera può essere qualsiasi. Il comando è su UDP/JSON, con adattatori OPC UA/Modbus come percorso. |
| Cosa non funziona? | Identità dei pedoni sotto occlusione lunga, più pedoni vicini, ambienti molto grandi. Li dichiariamo. |
| Come avete usato l'AI? | Come assistente per scrivere e rivedere codice e documenti; il team ha letto, eseguito e testato. Dichiarato in `AI_USAGE.md`. |
| Qual è il passo successivo? | Modalità ombra su un impianto reale, poi avvisi, poi limitatore morbido, poi integrazione con la catena di sicurezza. |

## 5. Frase guida
> «Una macchina non deve rallentare solo quando vede una persona, ma anche quando **non può vedere**: ignoto non significa libero.»

## 6. Risposta a «è già stato fatto?» da mettere nel README
«Esistono limitatori di velocità per zone fisse e sistemi di rilevamento pedoni su carrelli; la pianificazione con zone cieche è studiata nella guida autonoma. Il nostro contributo è portare la logica delle zone cieche nel contesto industriale, derivare il limite di velocità dalla fisica dello spazio di arresto e misurare il compromesso con la produttività, con un comando fail-safe.»

## 7. Script del video (2:45) — italiano
| Tempo | Immagine | Voce |
|---|---|---|
| 0:00–0:20 | Magazzino/modellino, carrello che arriva a un incrocio cieco | «In un magazzino, il pericolo più grande non è la persona che vedi. È quella che non puoi vedere.» |
| 0:20–0:40 | Zoom sull'angolo: scaffale che copre | «Un sistema che reagisce solo a ciò che vede arriva sempre tardi.» |
| 0:40–1:05 | HUD: zone verdi e arancio | «Oracolo sa cosa vede e cosa no. Le zone non osservate sono trattate come potenzialmente occupate: ignoto non significa libero.» |
| 1:05–1:35 | Atto 1: livelli 0→1→2, limite che scende | «Dalla fisica dello spazio di arresto calcola la velocità massima. Quattro livelli: normale, attenzione, rallenta, ferma.» |
| 1:35–2:00 | Atto 2: pedone esce, macchina si ferma; stesso caso senza Oracolo: collisione | «Con Oracolo la macchina era già lenta. Senza, la collisione.» |
| 2:00–2:20 | Atto 3: link tagliato / camera coperta → FERMA | «Il comando ha una scadenza: se smette di arrivare, la macchina si ferma da sola.» |
| 2:20–2:40 | Tabella e grafico | «In simulazione: zero collisioni dove la camera vede poco, contro 7 su 30 per chi reagisce solo a ciò che vede; e il prezzo in produttività dipende da dove metti le camere.» |
| 2:40–2:45 | Titolo e limiti | «Prototipo di ricerca, non certificato. Oracolo: sapere cosa non vedi.» |

Sottotitoli in italiano sempre. Riprendere solo i compagni di squadra, con consenso.

## 8. Checklist finale
- [ ] Iscrizione verificata; team confermato con il telefono del referente
- [ ] 2 checkpoint con i mentor fatti
- [ ] Video ≤ 3:00 (file finale controllato), in italiano con sottotitoli, link accessibile
- [ ] Repo leggibile dalla giuria (prova da finestra privata)
- [ ] README con limiti, risultati (simulazione + clip), lavori correlati, licenze e AI
- [ ] Titolo ≤ 100 car.; descrizione 200–5.000 car.
- [ ] Checklist piattaforma 7/7; **«Consegna il progetto» premuto; screenshot della conferma**
- [ ] Chi sarà alla chiusura è deciso

## 9. Rischi del processo
Vedi la tabella in `07-roadmap.md` §5.
