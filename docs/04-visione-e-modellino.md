# 04 · Visione reale e modellino fisico

Il motore non conosce la camera: riceve `FrameEvent` (id, x, y in metri, confidenza). Qui si spiega come produrli con iPhone + Mac.

## 1. Modellino 1:20 (si monta in 1–2 ore)
- **Scala:** 1 cm = 0,2 m. Corsia principale 3,5 m (=17,5 cm), corsia trasversale 3 m (=15 cm), scaffali alti 3 m (=15 cm) e uno basso 1 m (=5 cm).
- **Materiali:** cartone, scatole, nastro, pianta su foglio quadrettato; **pedone** = tappo/dischetto con colore saturo (o marker ArUco); **macchina** = rettangolino mosso a mano o solo virtuale sull'HUD.
- **Sensori:**
  - *iPhone 1 (sensore):* fisso, obliquo, 25–35 cm di altezza, 35–45° verso il basso, con occlusioni vere dietro gli scaffali. Dà le osservazioni reali.
  - *iPhone 3 (verità a terra):* zenitale, vede tutto. Serve solo per le metriche offline (allineato a quello sensore con un battito di mani o un flash).
  - *iPhone 2:* riprese per il video.
- **Luce:** lampada diffusa, niente riflessi, **esposizione e messa a fuoco bloccate** (tocco prolungato).

## 2. Pipeline
```
VideoCapture (thread, coda di lunghezza 1) → ridimensiona 640×360 → HSV/ArUco → centroide px
 → omografia (4 punti noti) → (x, y) in m equivalenti → tracking id semplice → FrameEvent
 → oracolo.engine.Oracle.step → Decision → MachineCommand → bus → VirtualMachine / HUD
```
- **Omografia:** 4 angoli della pianta con coordinate note in `scenarios/*.json`; `cv2.getPerspectiveTransform`.
- **Maschera di visibilità reale:** dalla posizione e quota della camera sul modellino si calcola con `visibility_polygon` (stessa geometria della scena); non serve stimarla dall'immagine.
- **Salute della scena:** nitidezza (varianza del Laplaciano) e luminosità; se scendono → `health` < 0,7 → limite ridotto; < 0,3 → FERMA.
- **Frame fermo:** `frame_age` = tempo dall'ultimo frame nuovo; oltre 0,30 s → FERMA (`affidabilita_persa`).

## 3. Rilevatore: ordine di preferenza
1. **Marker colorato / ArUco** sul pedone (affidabile, zero licenze problematiche, spiegabile).
2. **Un rilevatore di persone** solo per una clip "vera" (es. RF-DETR, Apache-2.0; opzionale). **Non** usare Ultralytics YOLO senza dichiararlo: AGPL-3.0.
3. Mai addestrare un modello: non c'è tempo.
Dichiarate nel README quale è usato in quale clip.

## 4. Verità a terra e misure
Per ogni run: clip sensore + clip zenitale. Dalla zenitale si ricavano le posizioni reali (marker) → si calcolano distanza minima, tempo di margine e collisione "virtuale" tra pedone e macchina virtuale. Non serve etichettatura a mano.

## 5. Piano B/C (vedi 07-roadmap)
- B: clip registrate e replay.
- C: solo simulatore + una clip del modellino come prova di realismo.
