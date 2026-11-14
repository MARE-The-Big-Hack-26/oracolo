"""Pipeline reale: camera fissa (iPhone) -> persone e muletto -> coordinate della planimetria -> motore.

Moduli:
  calib      omografia pixel -> pavimento (4 punti cliccati), posizione della camera, impronta visiva
  detectors  marker ArUco (muletto) e rilevatori di persone (HOG di base, RF-DETR opzionale)
  tracker    identità stabili per le persone, posa e velocità del muletto
  pipeline   un frame in ingresso -> stato (livello, limite, fantasmi, mappa) in uscita
  viz        disegno del CAD e degli indicatori sopra il video
  server     server HTTPS: pagina iPhone, pannello Mac, calibrazione
"""
