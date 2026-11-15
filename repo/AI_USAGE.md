# Uso dell'AI nel progetto (dichiarazione)

- Assistente di sviluppo: Claude (Anthropic) per pianificazione, scrittura e revisione di codice e documenti.
- Il codice generato è stato letto, eseguito e testato dal team; la sezione "Cosa fa il sistema e cosa no" è stata verificata a mano.
- Normalizzazione CAD (`cad_norm.py`), caricamento DXF, ancore ArUco e allineamento CAD-video (`vision/align.py`) scritti con Claude Code su richiesta del team (14/11); soglie e dimensioni dei marker sono ipotesi/simulazioni dichiarate in `docs/13`.
- Ottimizzazione prestazioni del pannello (cache contorni in `vision/viz.py`, fog su canvas e polling sequenziale in `web/panel.html`) scritta con Claude Code (15/11); misure fatte in sandbox, non su Mac.
- Modelli di visione (se usati nella pipeline reale): elencati in THIRD_PARTY.md con licenza.
- Il motore di decisione (visibilità, zone cieche, limite di velocità) è deterministico e NON usa modelli di AI.

TODO prima della consegna: aggiungere i nomi dei membri che hanno verificato ogni parte.
