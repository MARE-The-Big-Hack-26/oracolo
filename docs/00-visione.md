# 00 · Visione del progetto

**ClearCorner** — *rilevazione dei punti ciechi per macchine industriali.*

## In una frase
Una camera segnala quattro livelli di pericolo per possibili collisioni tra pedoni e macchine industriali, **anche quando il pedone non si vede ancora**, e invia alla macchina un comando che la rallenta o la ferma, con la regola che *ignoto non significa libero*.

## Il problema
Carrelli, AGV e mezzi di cantiere uccidono e feriscono soprattutto negli **incroci ciechi**: scaffali, angoli, carichi alti. Un sistema che reagisce solo a ciò che *vede* arriva tardi: quando il pedone compare, spesso non c'è più spazio per frenare.

## Il workflow
1. Si importa il **CAD** del magazzino (DXF) con scaffali, pilastri e carichi.
2. Una o più **camere fisse** vedono carrelli, persone e le **zone d'ombra** (punti ciechi) calcolate dalla geometria.
3. Ogni carrello ha un **ricevitore** che riceve il comando della camera e **rallenta o ferma** in base al grado di pericolo.
4. Non avendo un carrello reale, si **simula**: il Mac produce il comando e lo invia a un **iPhone** (Safari) che fa da ricevitore/cabina.

## L'idea (tre mosse)
1. **Sapere cosa non si vede.** Dalla geometria dell'ambiente e dalla posizione dei sensori si calcola, in ogni istante, quali zone sono visibili e quali no (visibilità 2.5D: conta anche l'altezza dell'occhio e del bersaglio).
2. **Ricordare e non fidarsi.** Se un pedone sparisce dietro uno scaffale, nasce un "fantasma" che si allarga alla velocità di camminata; le zone mai viste o viste troppo tempo fa sono "sconosciute" e trattate come potenzialmente occupate.
3. **Dalla fisica ai livelli.** La macchina deve poter sempre fermarsi *prima* che una persona possa raggiungere la sua traiettoria. Da questo si ricava la **velocità massima ammessa** e quindi il livello: 0 NORMALE, 1 ATTENZIONE, 2 RALLENTA, 3 FERMA. Il comando viaggia con una scadenza (TTL): se smette di arrivare, la macchina si ferma da sola.

## Cosa lo rende diverso
- Non è un "rilevatore di pedoni con allarme": è un limite di velocità **calcolato dal punto cieco**.
- Il comando è **fail-safe** (permissivo con scadenza), non un messaggio "stop" che può perdersi.
- Il motore è deterministico e **non usa AI**: è spiegabile e verificabile (i test confrontano la formula con la fisica a forza bruta). L'AI serve solo per vedere le persone, ed è sostituibile.
- Misura il **prezzo della sicurezza**: quanto tempo di produzione si perde e come lo riduce la posizione delle camere. In simulazione sul magazzino: 1 camera a fine corsia (44% di copertura) → 0 collisioni ma 40,8 s di transito; 2 camere sugli incroci (73%) → 0 collisioni e 19,8 s (13,8 s senza sistema). `coverage()` indica dove montarle.

## Cosa NON è (da dire sempre)
Non è un sistema di sicurezza certificato. Le norme per la sicurezza funzionale (ISO 13849, IEC 62061, IEC 61508) non prevedono oggi requisiti specifici per l'AI; per uno stop reale serve una catena certificata (relè/PLC di sicurezza, sensori safety). ClearCorner è un livello **sopra**: avvisa, limita, registra. Percorso realistico: modalità ombra → solo avvisi → limitatore morbido → integrazione con la catena di sicurezza.

## Collegamento con FieldVision (Challenge 03, Mare Group)
| Obiettivo della challenge | Cosa mostra ClearCorner |
|---|---|
| Rilevare elementi mobili | Pedoni (e macchina) tracciati dalla camera |
| Gestire l'occlusione | Zone cieche, fantasmi, memoria con scadenza |
| Distinguere osservato da incerto | Mappa visibile / ricordato / sconosciuto / persona nascosta |
| Segnalare la perdita di affidabilità | Frame fermo o scena degradata → FERMA, dichiarato sull'HUD |

## Scelte modellistiche dichiarate
Concept base *ClearCorner dell'Angolo* + variante 1 **Limite di Visibilità** (velocità massima dalla distanza di visibilità) + variante 2 **Sguardo Asimmetrico** (altezza dell'occhio: chi vede chi). Opzionale: variante 4 **Scatola Nera** (replay della scena). La macchina è un *digital twin* nel prototipo.
