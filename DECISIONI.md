# Registro delle decisioni

| Data/ora | Decisione | Motivo | Chi |
|---|---|---|---|
| 14/11 | Idea: **Oracolo** (Oracolo dell'Angolo + Limite di Visibilità + Sguardo Asimmetrico) | Tema sicurezza sul lavoro, concreta, testabile con iPhone+Mac | team |
| 14/11 | Tecnologia generica (Python/numpy/shapely/OpenCV), non API Apple | Portabilità: "per qualsiasi dispositivo" | team |
| 14/11 | Motore deterministico, senza AI | Spiegabile e verificabile; licenze semplici | team |
| 14/11 | Comando fail-safe con TTL e watchdog | Lo stop non deve dipendere dal messaggio che arriva | team |
| 14/11 | Dichiarare "non certificato" | Onestà e conformità alle norme | team |
| 14/11 | Evitare Ultralytics YOLO (AGPL-3.0) | Diritto di opzione del partner | team |
| 14/11 | Workflow: CAD del magazzino + camere FISSE (non a bordo) + ricevitore sul carrello | Requisito del team: camera da punto fisso; sensore sul mezzo riceve il comando | team |
| 14/11 | Simulazione: Mac → iPhone (Safari) come ricevitore con watchdog nella pagina | Nessun carrello reale disponibile | team |
| 14/11 | Collisione = contatto con mezzo in moto (v > 0,15 m/s); sfioramenti a parte | Un pedone che urta un mezzo già fermo non è un rischio cinetico; dichiarare entrambi | team |
| 14/11 | Nessuna nuova funzione dopo il blocco del codice (dom 07:30) | Rischio consegna | team |
| 14/11 | Camera = iPhone su treppiede che invia i frame al Mac via pagina web HTTPS | iPhone dell'organizzazione (Apple ID diverso): niente Continuity Camera | team |
| 14/11 | Riconoscimento con modello locale sul Mac (RF-DETR/HOG), non API cloud | Latenza e rete non adatte a un comando di frenata | team |
| 14/11 | Muletto simulato = sedia con marker ArUco; conducente escluso dai pedoni | Identità e direzione certe; chi spinge non è un pedone da proteggere | team |
| 14/11 | Il muletto non ha display; pannello di controllo solo sul Mac | Nel reale arriva solo il comando (relè/PLC) | team |
| 14/11 | Mappa stanza: misure o scansione LiDAR → DXF; calibrazione camera con 4 coppie di punti | Non esiste il CAD della stanza; si evita il metro per la camera | team |
| 14/11 | Telefoni/tag UWB (stile ELOshield): fuori scopo, solo estensione futura | La challenge è visione; i tag non vedono chi non li porta | team |
| 14/11 | Repo pubblica: github.com/MARE-The-Big-Hack-26/oracolo | Tutti i colleghi lavorano sugli stessi file | team |
| 14/11 | Nessuna stanza predefinita: all'avvio si sceglie «Carica DXF» (solo DXF) o «Disegna planimetria»; `scenarios/` = esempi e fixture | Il prodotto lavora sul CAD dell'utente; l'editor `/room` non sovrascrive più gli esempi (salva in `planimetria.dxf`) | team (impl. Claude) |
| 14/11 | Allineamento CAD-video con 4 ancore ArUco (id 10-13) a terra; calibrazione a 4 clic resta come alternativa | Misura di coincidenza robusta e rilevamento di camera spostata; soglie (10/25 cm) sono ipotesi da tarare | team (impl. Claude) |
| 14/11 | La posizione della camera NON si stima dalle ancore: si indica (x, y, h) | Stima da un solo piano misurata inaffidabile (~0,5 m di errore con 0,5 px di rumore) | team (impl. Claude) |
| 14/11 | Ancore: nero 20 cm consigliato (A3), 15 cm minimo (A4) | Simulazione a 960x540 (indicativa): da confermare con iPhone | team (impl. Claude) |
| 15/11 | Nome del progetto: **ClearCorner** (al posto di *Oracolo* per UI, brand e docs; pacchetto Python `oracolo/` invariato per evitare conflitti) | Più immediato e auto-esplicativo per giuria e utenti industriali | team |

Aggiungere una riga a ogni scelta importante (data, motivo, chi).
