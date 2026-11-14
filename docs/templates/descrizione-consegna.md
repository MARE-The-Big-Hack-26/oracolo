# Bozza descrizione di consegna (200–5.000 caratteri) — da aggiornare coi numeri veri

**Titolo (≤ 100 car.):** Oracolo — la macchina che rallenta prima di vedere il pedone

**Descrizione:**

Nei magazzini e nei cantieri il pericolo più grande non è la persona che si vede, ma quella che non si può vedere: dietro uno scaffale, a un incrocio cieco. Un sistema che reagisce solo a ciò che vede arriva sempre tardi.

Oracolo è un sistema di rilevazione dei punti ciechi per macchine industriali. Una camera segnala quattro livelli di pericolo (normale, attenzione, rallenta, ferma) per possibili collisioni tra pedoni e macchine e invia alla macchina un comando che la rallenta o la ferma.

Come funziona. (1) Dalla geometria dell'ambiente e dalla posizione dei sensori calcola, istante per istante, quali zone sono visibili e quali no. (2) Ricorda le persone sparite dietro un ostacolo ("fantasmi") e tratta le zone non osservate come potenzialmente occupate: ignoto non significa libero. (3) Dalla fisica dello spazio di arresto ricava la velocità massima ammessa, da cui il livello di pericolo. (4) Il comando ha una scadenza: se smette di arrivare, la macchina si ferma da sola.

Attinenza alla challenge FieldVision: rileva elementi mobili (pedoni), gestisce l'occlusione (zone cieche e memoria), distingue osservato da incerto (mappa visibile / ricordato / sconosciuto / persona nascosta) e segnala la perdita di affidabilità (frame fermo o scena degradata → stato sicuro).

Workflow: si importa il CAD del magazzino, le camere fisse vedono carrelli, persone e zone d'ombra, e il comando raggiunge il ricevitore del carrello (nel prototipo un iPhone). Risultati (simulazione, 30 casi con tempi casuali): dove la camera vede poco, 0 collisioni con Oracolo contro 13 senza sistema, 10 con zona fissa e 7 con un sistema che reagisce solo a ciò che vede; il costo in produttività dipende dalla copertura delle camere (44% → 40,8 s, 73% → 19,8 s, senza sistema 13,8 s). [AGGIUNGERE I NUMERI SULLE CLIP REALI]

Si può provare con un comando (make test && make demo). Gira su un Mac con iPhone come camera, ma il motore è indipendente dal dispositivo: riceve solo eventi (identificatore, posizione).

Limiti dichiarati: è un prototipo di ricerca, non un sistema di sicurezza certificato; per uno stop reale serve una catena di sicurezza certificata. Il motore è deterministico e non usa modelli di AI; l'AI serve solo per vedere le persone ed è sostituibile. Librerie, modelli e uso dell'AI sono dichiarati nel repository.
