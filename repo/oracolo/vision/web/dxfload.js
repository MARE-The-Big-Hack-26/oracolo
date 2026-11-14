// «Carica DXF»: invia il file a POST /dxf e mostra gli avvisi di normalizzazione.
// Condiviso da pannello (/) ed editor (/room). Il testo dei file (nomi layer) va SOLO in textContent.
async function oracoloLoadDxf(file) {
  if (!/\.dxf$/i.test(file.name)) return { ok: false, errors: ['Serve un file .dxf (DWG e altri formati non sono supportati).'], warnings: [] };
  try {
    const r = await fetch('/dxf', { method: 'POST', headers: { 'X-Filename': encodeURIComponent(file.name) }, body: file });
    return await r.json();
  } catch (e) { return { ok: false, errors: ['Errore di rete: ' + e], warnings: [] }; }
}
function oracoloReportInto(el, rep, title) {
  el.textContent = '';
  const h = document.createElement('b');
  const st = (rep && rep.stats) || {};
  h.textContent = title || (rep && rep.ok
    ? `Planimetria caricata: ${(st.size_m || []).join(' × ')} m, ${st.occluders ?? '?'} ostacoli`
    : 'Planimetria NON caricata');
  el.appendChild(h);
  for (const [cls, list] of [['err', (rep && rep.errors) || []], ['warn', (rep && rep.warnings) || []]]) {
    for (const t of list) { const d = document.createElement('div'); d.className = cls; d.textContent = (cls === 'err' ? '✖ ' : '⚠ ') + t; el.appendChild(d); }
  }
  if (rep && rep.ok && !(rep.warnings || []).length) { const d = document.createElement('div'); d.textContent = 'Nessun avviso.'; el.appendChild(d); }
}
function oracoloPickDxf(input, onDone) {
  input.onchange = async () => { const f = input.files[0]; input.value = ''; if (f) onDone(await oracoloLoadDxf(f), f); };
  input.click();
}
