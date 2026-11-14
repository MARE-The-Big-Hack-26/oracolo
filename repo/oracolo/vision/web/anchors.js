(() => {
  const ANCH_IDS = [10, 11, 12, 13, 14, 15, 16, 17], $ = (id) => document.getElementById(id);
  let pickAnchor = null;
  const setMsg = (t, err = false) => { const m = $('msg'); if (m) { m.className = err ? 'err' : 'ok'; m.textContent = t; } };
  window.OracoloAnchorsPick = (x, y) => {
    if (pickAnchor === null) return false;
    $('ax' + pickAnchor).value = x.toFixed(2);
    $('ay' + pickAnchor).value = y.toFixed(2);
    pickAnchor = null;
    setMsg('Coordinate dell\'ancora impostate: premi «Salva ancore».');
    return true;
  };
  $('anrows').innerHTML = ANCH_IDS.map((i) => `<div class="r"><b>id ${i}</b><label>x <input id="ax${i}" type="number" step="0.01"></label><label>y <input id="ay${i}" type="number" step="0.01"></label><label>rot ° <input id="ar${i}" type="number" step="1" value="0" style="width:60px"></label><button type="button" data-pick="${i}">sulla mappa</button></div>`).join('');
  document.querySelectorAll('[data-pick]').forEach((b) => { b.onclick = () => { pickAnchor = b.dataset.pick; setMsg('Clicca sulla MAPPA il centro del marker id ' + b.dataset.pick + '.'); }; });
  function anchorBody() {
    const o = {};
    ANCH_IDS.forEach((i) => { const x = parseFloat($('ax' + i).value), y = parseFloat($('ay' + i).value); if (isFinite(x) && isFinite(y)) o[i] = { x, y, rot_deg: parseFloat($('ar' + i).value) || 0 }; });
    const b = { size_m: (parseFloat($('ansz').value) || 20) / 100, anchors: o };
    const cx = parseFloat($('acx').value), cy = parseFloat($('acy').value), ch = parseFloat($('ach').value);
    if (isFinite(cx) && isFinite(cy) && isFinite(ch)) b.camera = { x: cx, y: cy, h: ch };
    return b;
  }
  function fillAnchors(a) {
    if (!a) return;
    $('ansz').value = Math.round(a.size_m * 1000) / 10;
    for (const [id, v] of Object.entries(a.anchors || {})) { if ($('ax' + id)) { $('ax' + id).value = v.x; $('ay' + id).value = v.y; $('ar' + id).value = v.rot_deg || 0; } }
    if (a.camera) { $('acx').value = a.camera.x; $('acy').value = a.camera.y; $('ach').value = a.camera.h; }
  }
  async function post(url, body) {
    try { const r = await fetch(url, { method: 'POST', body: JSON.stringify(body) }); return await r.json(); }
    catch (e) { return { ok: false, error: 'Errore di rete: ' + e }; }
  }
  $('ansave').onclick = async () => {
    const j = await post('/anchors', anchorBody());
    setMsg(j.ok ? ('Ancore salvate.' + ((j.warnings || []).length ? ' ⚠ ' + j.warnings.join(' ') : '')) : ('Errore: ' + j.error), !j.ok);
    if (j.ok && window.OracoloCalibReload) window.OracoloCalibReload();
  };
  $('anclr').onclick = async () => {
    const j = await post('/anchors', { clear: true });
    setMsg(j.ok ? 'Ancore rimosse (l\'allineamento CAD-video non sarà verificato).' : ('Errore: ' + j.error), !j.ok);
    if (window.OracoloCalibReload) window.OracoloCalibReload();
  };
  $('ancal').onclick = async () => {
    let j = await post('/anchors', anchorBody());
    if (!j.ok) { setMsg('Errore: ' + j.error, true); return; }
    const b = anchorBody();
    j = await post('/calib_anchors', b.camera ? { camera: b.camera } : {});
    setMsg(j.ok ? `Calibrazione dalle ancore salvata. Errore sugli angoli: ${(j.rms_m * 100).toFixed(1)} cm; camera (${j.cam.join(', ')}) ${j.cam_source}.` : ('Errore: ' + j.error), !j.ok);
    if (j.ok) {
      if (j.cam && window.OracoloSetCamFromAnchors) window.OracoloSetCamFromAnchors(j.cam);
      if (window.OracoloCalibReload) window.OracoloCalibReload();
    }
  };
  (async () => {
    try {
      const a = await (await fetch('/anchors')).json();
      fillAnchors(a.anchors);
      if (a.anchors) $('anch').open = true;
      const sc = await (await fetch('/scene')).json();
      if (sc.cam && !$('acx').value) { $('acx').value = sc.cam.xy[0]; $('acy').value = sc.cam.xy[1]; $('ach').value = sc.cam.h; }
    } catch {}
    setInterval(async () => {
      try {
        const a = (await (await fetch('/state?_=' + Date.now())).json()).align, el = $('anst');
        if (!a || a.status === 'NON_VERIFICATO') { el.textContent = ''; return; }
        el.className = a.status === 'OK' ? 'ok' : (a.status === 'NON_COINCIDE' ? 'bad' : 'warn');
        el.textContent = '— ' + a.status + ': ' + (a.message || '');
      } catch {}
    }, 800);
  })();
})();
