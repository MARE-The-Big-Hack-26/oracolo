# Uso dell'AI nel progetto (dichiarazione)

- Assistente di sviluppo: Claude (Anthropic) per pianificazione, scrittura e revisione di codice e documenti.
- Il codice generato è stato letto, eseguito e testato dal team; la sezione "Cosa fa il sistema e cosa no" è stata verificata a mano.
- Normalizzazione CAD (`cad_norm.py`), caricamento DXF, ancore ArUco e allineamento CAD-video (`vision/align.py`) scritti con Claude Code su richiesta del team (14/11); soglie e dimensioni dei marker sono ipotesi/simulazioni dichiarate in `docs/13`.
- Cartello-lavoratore a disegno (`vision/detectors.py`, `TagMatcher`), marker lavoratore ArUco id 1-9 e planimetrie di prova selezionabili (15/11) scritti con Claude Code su richiesta del team; soglie tarate solo su immagini simulate.
- Ottimizzazione prestazioni del pannello (cache contorni in `vision/viz.py`, fog su canvas e polling sequenziale in `web/panel.html`) scritta con Claude Code (15/11); misure fatte in sandbox, non su Mac.
- Riduzione del lag (HOG con passo di scala 1,1 al posto di 1,05; JPEG della camera a qualità 0,62) deciso con Claude Code il 15/11 su misure di tempo fatte in sandbox, non sul Mac.
- Modelli di visione (se usati nella pipeline reale): elencati in THIRD_PARTY.md con licenza.
- Il motore di decisione (visibilità, zone cieche, limite di velocità) è deterministico e NON usa modelli di AI.

Verifica: il team ha letto, eseguito e testato il codice (135 test automatici). Le prove con camera reale sono descritte nel README.
