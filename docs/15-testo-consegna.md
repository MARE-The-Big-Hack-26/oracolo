# 15 · Bozza testo per il modulo di consegna

**Bozza, da rivedere.** Le frasi con [DA COMPILARE] vanno completate con risultati veri (nessun numero inventato).

## Titolo (≤ 100 caratteri)
Oracolo: la macchina rallenta anche per ciò che non vede (punti ciechi da CAD + camera)

(87 caratteri)

## Descrizione (200–5.000 caratteri)
Oracolo è un prototipo per la Challenge 03 FieldVision (Mare Group). Parte da un'idea: in un magazzino il pericolo più grande non è la persona che vedi, ma quella che non puoi vedere. Un sistema che reagisce solo a ciò che vede arriva sempre tardi.

Come funziona. L'utente importa la planimetria del magazzino (file DXF) oppure la disegna nell'editor integrato; il programma la normalizza e segnala ciò che ha scartato. Una camera fissa (nel prototipo un iPhone su treppiede) invia il video a un Mac. Dal CAD e dalla posizione della camera Oracolo calcola le zone d'ombra: le zone non osservate sono trattate come potenzialmente occupate ("ignoto non significa libero"). Dalla fisica dello spazio di arresto ricava la velocità massima con cui la macchina può ancora fermarsi in tempo, e la traduce in quattro livelli: NORMALE, ATTENZIONE, RALLENTA, FERMA. Il comando (limite di velocità, livello, causa, scadenza) arriva alla macchina, che non ha alcun display: se i comandi smettono di arrivare, si ferma da sola.

Allineamento CAD-video. Quattro marker ArUco a terra, in punti noti del CAD, calibrano la camera in automatico e verificano di continuo che CAD e video coincidano. Se la camera viene spostata o i marker non si vedono, il sistema avvisa e passa a FERMA invece di fidarsi di una mappa sbagliata.

Obiettivi della challenge: rilevare persone e macchina; gestire l'occlusione (ricorda chi è sparito dietro un ostacolo); distinguere osservato da incerto; segnalare la perdita di affidabilità (frame mancanti, camera spostata).

Risultati. In simulazione (30 casi, tempi e velocità casuali): 0 collisioni con Oracolo contro 7/30 per il solo sistema reattivo dove la camera vede poco; il prezzo in produttività dipende dalla copertura delle camere. Prova con camera reale: [DA COMPILARE con i risultati veri della prova in aula].

Limiti dichiarati: prototipo di ricerca, non certificato; simulazione e prove reali sono tenute separate; soglie di allineamento e dimensione dei marker sono ipotesi da tarare; una sola camera; solo formato DXF.

Tecnologie: Python, OpenCV (omografia, ArUco), shapely, ezdxf, RF-DETR/HOG per le persone (opzionale, licenze in THIRD_PARTY.md). L'AI (Claude) è stata usata come assistente di sviluppo: dichiarato in AI_USAGE.md. Il motore di decisione è deterministico e non usa modelli di AI.

(2332 caratteri)

## Da non dimenticare
- Link al video (≤ 3:00, in italiano con sottotitoli, accessibile senza login)
- Link alla repo (aperta da finestra privata)
- Telefono del referente; almeno 2 membri
