let scene = null, im = new Image(), imgPts = [], worldPts = [], pending = null, cam = [4.5, 1.1], camH = 1.8;
let camMode = false, resetConfirm = false, resetT = null, overlay = null, calibW = 0, calibSize = [960, 540];
let dragImg = -1, dragMap = null, toastT = null, selPt = -1, hoverImg = null, snapMap = null, ptErrs = [];
let inflight = false, queuedLive = false, lastLiveAt = 0;
const CACHE_KEY = 'oracolo_calib_cache', rnd = (v) => Math.round(v * 100) / 100, $ = (id) => document.getElementById(id);
const ci = $('img'), cm = $('map'), msgEl = $('msg'), toastEl = $('toast'), saveBtn = $('save'), setCamBtn = $('setcam');
const cxEl = $('cx'), cyEl = $('cy'), chEl = $('ch'), zModeEl = $('zmode'), fitDistEl = $('fitdist'), fitInfoEl = $('fitinfo');
const nowStr = () => new Date().toLocaleTimeString('it-IT');
const msg = (t) => { msgEl.className = ''; msgEl.textContent = t; };
const readCache = () => { try { return JSON.parse(localStorage.getItem(CACHE_KEY) || '{}') || {}; } catch { return {}; } };
const writeCache = (p) => { const c = { ...readCache(), ...p }; try { localStorage.setItem(CACHE_KEY, JSON.stringify(c)); } catch {} return c; };
function flashBtn(btn, okText = '[OK] Salvato', ms = 1800) {
  if (!btn) return;
  if (!btn.dataset.orig) btn.dataset.orig = btn.textContent;
  clearTimeout(btn._t); btn.classList.add('ok'); btn.textContent = okText;
  btn._t = setTimeout(() => { btn.classList.remove('ok'); btn.textContent = btn.dataset.orig; delete btn.dataset.orig; updLabels(); }, ms);
}
function notify(text, isErr = false) {
  const tag = isErr ? '[ERRORE]' : '[OK]';
  msgEl.className = isErr ? 'err' : 'ok'; msgEl.textContent = `[${nowStr()}] ${tag} ${text}`;
  toastEl.textContent = `${tag} ${text}`; toastEl.className = 'show' + (isErr ? ' err' : '');
  clearTimeout(toastT); toastT = setTimeout(() => { toastEl.className = ''; }, 2600);
}
function syncCamInputs() { cxEl.value = rnd(cam[0]); cyEl.value = rnd(cam[1]); chEl.value = rnd(camH); }
function updLabels() {
  const n = imgPts.length, ready = n >= 4 && worldPts.length === n && !pending;
  if (!saveBtn.classList.contains('ok')) saveBtn.textContent = ready ? 'Calcola e salva' : 'Salva camera';
  if (!setCamBtn.classList.contains('ok')) setCamBtn.textContent = camMode ? 'Clicca sulla mappa...' : 'Posiziona camera';
}
function mview() {
  const xs = scene.bounds.map((p) => p[0]), ys = scene.bounds.map((p) => p[1]);
  const minx = Math.min(...xs), maxx = Math.max(...xs), miny = Math.min(...ys), maxy = Math.max(...ys);
  const w = cm.width, h = cm.height, pad = 26, sc = Math.min((w - 2 * pad) / Math.max(maxx - minx, 0.1), (h - 2 * pad) / Math.max(maxy - miny, 0.1));
  const ox = (w - sc * (maxx - minx)) / 2, oy = (h - sc * (maxy - miny)) / 2;
  return { sc, X: (x) => ox + (x - minx) * sc, Y: (y) => h - oy - (y - miny) * sc, ix: (px) => (px - ox) / sc + minx, iy: (py) => (h - oy - py) / sc + miny };
}
function collectCadVertices() {
  const out = [];
  if (!scene) return out;
  (scene.bounds || []).forEach((p) => out.push({ x: p[0], y: p[1], h: 0, label: 'Muro' }));
  (scene.occluders || []).forEach((o) => {
    const nm = (o.name || '').replace(/#\d+$/, '').replace(/_H[\d.,]+$/i, '').toLowerCase() || 'ostacolo';
    (o.coords || []).forEach((p) => out.push({ x: p[0], y: p[1], h: Number(o.height) || 0, label: nm }));
  });
  return out;
}
function findSnap(v, px, py, sc, noSnap) {
  if (noSnap) return null;
  const maxD = 15 * sc;
  let best = null, bestD = maxD;
  for (const vt of collectCadVertices()) {
    const d = Math.hypot(v.X(vt.x) - px, v.Y(vt.y) - py);
    if (d < bestD) { bestD = d; best = vt; }
  }
  if (!best) return null;
  const z = (zModeEl.value === 'top' && best.h > 0.05) ? rnd(best.h) : 0;
  return { x: rnd(best.x), y: rnd(best.y), z, label: `${best.label} (${z > 0 ? 'cima ' + z + 'm' : 'terra'})` };
}
function strokePoly(c, pts, col, lw, sc = 1) {
  if (!pts || pts.length < 2) return;
  c.beginPath(); pts.forEach((p, i) => (i ? c.lineTo(p[0] * sc, p[1] * sc) : c.moveTo(p[0] * sc, p[1] * sc)));
  c.closePath(); c.strokeStyle = col; c.lineWidth = lw; c.stroke();
}
function drawLoupe(c) {
  if (!hoverImg || !im.naturalWidth) return;
  const [hx, hy] = hoverImg, sz = 128, srcR = 26, pad = 12;
  const lx = hx < ci.width * 0.35 ? ci.width - sz - pad : pad, ly = pad;
  c.save(); c.beginPath(); c.rect(lx, ly, sz, sz); c.clip();
  c.fillStyle = '#07090e'; c.fillRect(lx, ly, sz, sz);
  c.drawImage(im, hx - srcR, hy - srcR, srcR * 2, srcR * 2, lx, ly, sz, sz);
  c.strokeStyle = 'rgba(56,189,248,0.85)'; c.lineWidth = 1.5;
  c.beginPath(); c.moveTo(lx + sz / 2, ly); c.lineTo(lx + sz / 2, ly + sz); c.moveTo(lx, ly + sz / 2); c.lineTo(lx + sz, ly + sz / 2); c.stroke();
  c.restore(); c.strokeStyle = '#38bdf8'; c.lineWidth = 2; c.strokeRect(lx, ly, sz, sz);
}
function drawImg() {
  if (!im.naturalWidth) {
    ci.width = 640; ci.height = 360; const c = ci.getContext('2d'); c.fillStyle = '#07090e'; c.fillRect(0, 0, 640, 360);
    c.fillStyle = '#cbd5e1'; c.font = '15px sans-serif'; c.fillText('Nessun fotogramma: apri /camera sulla camera, poi premi "Aggiorna immagine"', 20, 180); return;
  }
  ci.width = im.naturalWidth; ci.height = im.naturalHeight; const c = ci.getContext('2d'); c.drawImage(im, 0, 0);
  if (overlay) {
    const sc = calibW ? ci.width / calibW : 1;
    strokePoly(c, overlay.bounds, 'rgba(255,255,255,0.9)', 2, sc);
    (overlay.occluders || []).forEach((o) => {
      strokePoly(c, o.floor, 'rgba(230,159,0,0.95)', 2.2, sc);
      if (o.top && o.top.length >= 3) strokePoly(c, o.top, 'rgba(86,180,233,0.88)', 1.6, sc);
    });
  }
  imgPts.forEach((p, i) => {
    const active = i === dragImg || i === selPt;
    c.fillStyle = active ? '#38bdf8' : '#d55e00'; c.beginPath(); c.arc(p[0], p[1], active ? 10 : 8, 0, 7); c.fill();
    c.strokeStyle = '#ffffff'; c.lineWidth = 2; c.stroke();
    c.fillStyle = '#ffffff'; c.font = 'bold 17px sans-serif'; c.fillText(String(i + 1), p[0] + 11, p[1] - 9);
  });
  if (pending) { c.strokeStyle = '#f59e0b'; c.lineWidth = 3; c.beginPath(); c.arc(pending[0], pending[1], 13, 0, 7); c.stroke(); }
  drawLoupe(c);
}
function drawMap() {
  if (!scene) return;
  cm.width = 900; cm.height = Math.round(900 * 0.72); const c = cm.getContext('2d'), v = mview();
  c.fillStyle = '#0d111a'; c.fillRect(0, 0, cm.width, cm.height);
  const poly = (pts, f, s, lw = 2) => {
    c.beginPath(); pts.forEach((p, i) => (i ? c.lineTo(v.X(p[0]), v.Y(p[1])) : c.moveTo(v.X(p[0]), v.Y(p[1]))));
    c.closePath(); if (f) { c.fillStyle = f; c.fill(); } if (s) { c.strokeStyle = s; c.lineWidth = lw; c.stroke(); }
  };
  poly(scene.bounds, '#141b29', '#94a3b8');
  if (scene.fov && scene.fov.length >= 3) poly(scene.fov, 'rgba(86,180,233,0.16)', 'rgba(86,180,233,0.78)', 1.6);
  scene.occluders.forEach((o) => { if (o.coords.length) poly(o.coords, '#3b230c', '#f59e0b'); });
  worldPts.forEach((p, i) => {
    const x = v.X(p[0]), y = v.Y(p[1]), is3d = (p[2] || 0) > 0.01;
    c.fillStyle = (dragMap && dragMap.kind === 'pt' && dragMap.idx === i) || i === selPt ? '#38bdf8' : (is3d ? '#10b981' : '#0072b2');
    c.fillRect(x - 8, y - 8, 16, 16); c.strokeStyle = '#ffffff'; c.lineWidth = 2; c.strokeRect(x - 8, y - 8, 16, 16);
    c.fillStyle = '#ffffff'; c.font = 'bold 17px sans-serif'; c.fillText(`${i + 1}${is3d ? '↑' : ''}`, x + 11, y - 7);
  });
  if (snapMap) {
    const sx = v.X(snapMap.x), sy = v.Y(snapMap.y);
    c.strokeStyle = '#38bdf8'; c.lineWidth = 2.5; c.beginPath(); c.arc(sx, sy, 12, 0, 7); c.stroke();
    c.fillStyle = 'rgba(15,23,42,0.92)'; c.fillRect(sx + 12, sy - 26, snapMap.label.length * 8 + 14, 22);
    c.fillStyle = '#38bdf8'; c.font = '600 13px sans-serif'; c.fillText(snapMap.label, sx + 18, sy - 11);
  }
  if (scene.anchors && scene.anchors.anchors) {
    for (const [id, a] of Object.entries(scene.anchors.anchors)) {
      const h = Math.max(6, scene.anchors.size_m * v.sc / 2);
      c.strokeStyle = '#e879f9'; c.lineWidth = 3; c.strokeRect(v.X(a.x) - h, v.Y(a.y) - h, 2 * h, 2 * h);
      c.fillStyle = '#e879f9'; c.font = 'bold 14px sans-serif'; c.fillText('A' + id, v.X(a.x) + h + 4, v.Y(a.y) - h);
    }
  }
  if (cam) {
    const x = v.X(cam[0]), y = v.Y(cam[1]);
    c.fillStyle = (dragMap && dragMap.kind === 'cam') ? '#f59e0b' : '#009e73';
    c.beginPath(); c.moveTo(x, y - 11); c.lineTo(x + 11, y); c.lineTo(x, y + 11); c.lineTo(x - 11, y); c.closePath(); c.fill();
    c.strokeStyle = '#ffffff'; c.lineWidth = 2; c.stroke();
    c.fillStyle = '#ffffff'; c.font = '600 15px sans-serif'; c.fillText(`Camera (H ${camH.toFixed(2)}m)`, x + 14, y - 8);
  }
}
function renderPtsList() {
  $('ptcnt').textContent = imgPts.length;
  const el = $('ptslist');
  if (!imgPts.length) { el.innerHTML = '<span style="font-size:12px;color:#94a3b8">Nessun punto selezionato.</span>'; return; }
  el.innerHTML = '';
  imgPts.forEach((p, i) => {
    const w = worldPts[i] || [0, 0, 0], z = Number(w[2] || 0), err = ptErrs[i];
    const chip = document.createElement('div'); chip.className = 'pt-chip' + (i === selPt ? ' sel' : '');
    chip.onclick = () => { selPt = i; drawImg(); drawMap(); renderPtsList(); };
    const eCls = err == null ? '' : (err <= 5 ? 'err-ok' : (err <= 12 ? 'err-warn' : 'err-bad'));
    chip.innerHTML = `<b>#${i + 1}</b><span>(${Math.round(p[0])},${Math.round(p[1])}) → (${rnd(w[0])},${rnd(w[1])})</span><label>Z<input type="number" step="0.05" min="0" value="${rnd(z)}"></label>${err != null ? `<span class="err-tag ${eCls}">${err.toFixed(1)}px</span>` : ''}<button type="button" title="Elimina">×</button>`;
    const zin = chip.querySelector('input');
    zin.onclick = (e) => e.stopPropagation();
    zin.onchange = () => { worldPts[i][2] = Math.max(0, parseFloat(zin.value) || 0); drawMap(); if (imgPts.length >= 4) saveCalib(saveBtn); };
    chip.querySelector('button').onclick = (e) => { e.stopPropagation(); imgPts.splice(i, 1); worldPts.splice(i, 1); ptErrs.splice(i, 1); if (selPt === i) selPt = -1; else if (selPt > i) selPt--; if (imgPts.length < 4) overlay = null; upd(); if (imgPts.length >= 4) saveCalib(saveBtn); };
    el.appendChild(chip);
  });
}
function upd() {
  const n = imgPts.length; saveBtn.disabled = false; setCamBtn.classList.toggle('act', camMode); updLabels();
  $('step').textContent = camMode ? 'Modalita Camera: clicca sulla PLANIMETRIA 2D dove si trova la camera' : (pending ? `Punto #${n + 1}: clicca lo spigolo corrispondente sulla PLANIMETRIA 2D (snap azzurro)` : `Punto #${n + 1}: clicca uno spigolo sul video (o trascina i punti 1..${n})`);
  drawImg(); drawMap(); renderPtsList();
}
async function saveCamOnly(btn = saveBtn) {
  if (!scene) return;
  saveBtn.textContent = 'Salvataggio in corso...';
  const c = writeCache({ cam_xy: cam, cam_h: camH }), body = { bounds: scene.bounds, obstacles: (scene.occluders || []).filter((o) => o.coords && o.coords.length >= 3), cam: { xy: cam, h: camH } };
  try {
    const j = await (await fetch('/scene', { method: 'POST', body: JSON.stringify(body) })).json();
    let calOk = false;
    if (c.img && c.world && c.img.length >= 4 && c.img.length === c.world.length) {
      const sz = im.naturalWidth ? [im.naturalWidth, im.naturalHeight] : (c.image_size || calibSize);
      const cj = await (await fetch('/calib', { method: 'POST', body: JSON.stringify({ img: c.img, world: c.world, image_size: sz, cam_xy: cam, cam_h: camH, fit_distortion: fitDistEl.checked }) })).json();
      if (cj.ok) { calOk = true; overlay = cj.overlay || overlay; calibW = sz[0]; if (cj.fov) scene.fov = cj.fov; ptErrs = cj.point_errors_px || []; upd(); }
    }
    if (j.ok || calOk) { flashBtn(saveBtn, '[OK] Camera salvata'); if (btn && btn !== saveBtn) flashBtn(btn, '[OK] Camera salvata'); notify(`Posizione camera salvata (${rnd(cam[0])}, ${rnd(cam[1])} m · H ${rnd(camH)} m).`); }
    else { updLabels(); notify('Errore: ' + j.error, true); }
  } catch (e) { updLabels(); notify('Errore di rete: ' + e, true); }
}
async function saveCalib(btn = saveBtn, silent = false) {
  const n = imgPts.length; if (!(n >= 4 && worldPts.length === n && !pending)) return silent ? null : saveCamOnly(btn);
  const sz = im.naturalWidth ? [im.naturalWidth, im.naturalHeight] : calibSize;
  if (!silent) saveBtn.textContent = 'Salvataggio in corso...';
  writeCache({ img: imgPts, world: worldPts, image_size: sz, cam_xy: cam, cam_h: camH });
  const body = { img: imgPts, world: worldPts, image_size: sz, cam_xy: cam, cam_h: camH, fit_distortion: fitDistEl.checked };
  try {
    const j = await (await fetch('/calib', { method: 'POST', body: JSON.stringify(body) })).json();
    if (j.ok) {
      overlay = j.overlay || null; calibW = sz[0]; calibSize = sz; if (j.fov) scene.fov = j.fov;
      ptErrs = j.point_errors_px || [];
      if (j.cam_xy && j.cam_h && worldPts.some((w) => (w[2] || 0) > 0.01)) { cam = [rnd(j.cam_xy[0]), rnd(j.cam_xy[1])]; camH = rnd(j.cam_h); syncCamInputs(); }
      fitInfoEl.textContent = `${j.rms_px != null ? 'RMS ' + j.rms_px.toFixed(1) + 'px' : ''}${j.fov_deg ? ' · FOV ' + j.fov_deg + '°' : ''}${j.k1 ? ' · k1 ' + j.k1.toFixed(3) : ''}`;
      upd();
      if (!silent) {
        if (scene) fetch('/scene', { method: 'POST', body: JSON.stringify({ bounds: scene.bounds, obstacles: (scene.occluders || []).filter((o) => o.coords && o.coords.length >= 3), cam: { xy: cam, h: camH } }) }).catch(() => {});
        flashBtn(saveBtn, '[OK] Salvato'); if (btn && btn !== saveBtn) flashBtn(btn, '[OK] Salvato');
        notify(`Calibrazione salvata. RMS: ${(j.rms_m * 100).toFixed(1)} cm${j.rms_px != null ? ` (${j.rms_px.toFixed(1)} px)` : ''}${n === 4 ? ' (aggiungi 2-4 punti per verificare residui e distorsione)' : ''}.`);
      }
    } else if (!silent) { updLabels(); notify('Errore: ' + j.error, true); }
  } catch (e) { if (!silent) { updLabels(); notify('Errore di rete: ' + e, true); } }
}
function triggerLiveCalib() {
  if (imgPts.length < 4 || Date.now() - lastLiveAt < 110) { queuedLive = true; return; }
  if (inflight) { queuedLive = true; return; }
  inflight = true; lastLiveAt = Date.now(); queuedLive = false;
  saveCalib(saveBtn, true).finally(() => { inflight = false; if (queuedLive) triggerLiveCalib(); });
}
const saveCameraOrCalib = (btn = saveBtn) => (imgPts.length >= 4 && worldPts.length === imgPts.length && !pending ? saveCalib(btn) : saveCamOnly(btn));
const pos = (e, cv) => { const r = cv.getBoundingClientRect(); return [(e.clientX - r.left) * cv.width / r.width, (e.clientY - r.top) * cv.height / r.height, cv.width / r.width]; };
const hitIdx = (pts, px, py, rad) => pts.findIndex((p) => Math.hypot(p[0] - px, p[1] - py) <= rad);
ci.addEventListener('pointerdown', (e) => {
  if (!im.naturalWidth) return; const [px, py, sc] = pos(e, ci), hi = hitIdx(imgPts, px, py, 16 * sc);
  if (hi >= 0 && !camMode) { dragImg = hi; selPt = hi; ci.setPointerCapture(e.pointerId); upd(); return; }
  if (camMode || pending) return; pending = [px, py]; upd();
});
ci.addEventListener('pointermove', (e) => {
  if (!im.naturalWidth) return; const [px, py, sc] = pos(e, ci); hoverImg = [px, py];
  if (dragImg >= 0) { imgPts[dragImg] = [px, py]; drawImg(); triggerLiveCalib(); return; }
  ci.style.cursor = (!camMode && hitIdx(imgPts, px, py, 16 * sc) >= 0) ? 'grab' : 'crosshair'; drawImg();
});
ci.addEventListener('pointerleave', () => { hoverImg = null; drawImg(); });
ci.addEventListener('pointerup', () => { if (dragImg < 0) return; dragImg = -1; upd(); saveCalib(saveBtn); });
cm.addEventListener('pointerdown', (e) => {
  if (!scene) return; const v = mview(), [px, py, sc] = pos(e, cm), sn = findSnap(v, px, py, sc, e.altKey);
  const w = sn ? [sn.x, sn.y, sn.z] : [v.ix(px), v.iy(py), 0];
  if (window.OracoloAnchorsPick && window.OracoloAnchorsPick(w[0], w[1])) return;
  if (camMode) { cam = [rnd(w[0]), rnd(w[1])]; camMode = false; syncCamInputs(); upd(); saveCameraOrCalib(setCamBtn); return; }
  if (!pending) {
    const rad = 16 * sc;
    if (cam && Math.hypot(v.X(cam[0]) - px, v.Y(cam[1]) - py) <= rad) { dragMap = { kind: 'cam' }; cm.setPointerCapture(e.pointerId); drawMap(); return; }
    const hi = worldPts.findIndex((p) => Math.hypot(v.X(p[0]) - px, v.Y(p[1]) - py) <= rad);
    if (hi >= 0) { dragMap = { kind: 'pt', idx: hi }; selPt = hi; cm.setPointerCapture(e.pointerId); upd(); return; }
    msg('Prima clicca un punto sul fotogramma video (oppure trascina un punto numerato o la camera).'); return;
  }
  imgPts.push(pending); worldPts.push(w); selPt = imgPts.length - 1; pending = null; snapMap = null; msg(''); upd();
  if (worldPts.length >= 4) saveCalib(saveBtn);
});
cm.addEventListener('pointermove', (e) => {
  if (!scene) return; const v = mview(), [px, py, sc] = pos(e, cm);
  if (dragMap) {
    if (dragMap.kind === 'cam') { cam = [rnd(v.ix(px)), rnd(v.iy(py))]; syncCamInputs(); }
    else { const sn = findSnap(v, px, py, sc, e.altKey); worldPts[dragMap.idx] = sn ? [sn.x, sn.y, sn.z] : [v.ix(px), v.iy(py), worldPts[dragMap.idx][2] || 0]; snapMap = sn; }
    drawMap(); return;
  }
  snapMap = (pending || !camMode) ? findSnap(v, px, py, sc, e.altKey) : null;
  const rad = 16 * sc, over = !pending && !camMode && ((cam && Math.hypot(v.X(cam[0]) - px, v.Y(cam[1]) - py) <= rad) || worldPts.some((p) => Math.hypot(v.X(p[0]) - px, v.Y(p[1]) - py) <= rad));
  cm.style.cursor = over ? 'grab' : 'crosshair'; drawMap();
});
cm.addEventListener('pointerup', () => { if (!dragMap) return; const isCam = dragMap.kind === 'cam'; dragMap = null; snapMap = null; upd(); if (isCam) saveCameraOrCalib(saveBtn); else saveCalib(saveBtn); });
window.addEventListener('keydown', (e) => {
  if (selPt < 0 || selPt >= imgPts.length || ['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement?.tagName)) return;
  const step = e.shiftKey ? 5 : 0.5, d = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.key];
  if (!d) return; e.preventDefault(); imgPts[selPt] = [imgPts[selPt][0] + d[0], imgPts[selPt][1] + d[1]]; drawImg(); triggerLiveCalib();
});
function onCamField(saveNow) {
  const x = parseFloat(cxEl.value), y = parseFloat(cyEl.value), h = parseFloat(chEl.value);
  if (Number.isFinite(x)) cam[0] = x; if (Number.isFinite(y)) cam[1] = y; if (Number.isFinite(h) && h >= 0.2) camH = h;
  drawMap(); if (saveNow) saveCameraOrCalib(saveBtn);
}
[cxEl, cyEl, chEl].forEach((el) => { el.addEventListener('input', () => onCamField(false)); el.addEventListener('change', () => onCamField(true)); });
fitDistEl.addEventListener('change', () => { if (imgPts.length >= 4) saveCalib(saveBtn); });
setCamBtn.onclick = () => { camMode = !camMode; upd(); };
$('undo').onclick = () => { if (pending) pending = null; else if (camMode) camMode = false; else { imgPts.pop(); worldPts.pop(); ptErrs.pop(); if (imgPts.length < 4) overlay = null; } upd(); if (imgPts.length >= 4) saveCalib($('undo')); else { writeCache({ img: imgPts, world: worldPts }); flashBtn($('undo'), '[OK] Annullato', 1200); } };
$('reset').onclick = () => {
  const b = $('reset');
  if (!resetConfirm) { resetConfirm = true; b.classList.add('dan'); b.textContent = 'Conferma azzera?'; clearTimeout(resetT); resetT = setTimeout(() => { resetConfirm = false; b.classList.remove('dan'); b.textContent = 'Ricomincia'; }, 3000); return; }
  resetConfirm = false; b.classList.remove('dan'); b.textContent = 'Ricomincia'; imgPts = []; worldPts = []; ptErrs = []; selPt = -1; pending = null; camMode = false; overlay = null; writeCache({ img: [], world: [] }); msg('Punti di calibrazione azzerati.'); upd(); flashBtn(b, '[OK] Azzerato', 1200);
};
$('refresh').onclick = () => { im = new Image(); im.onload = () => { upd(); flashBtn($('refresh'), '[OK] Aggiornata', 1200); notify('Fotogramma aggiornato.'); }; im.onerror = () => { notify('Nessun fotogramma disponibile.', true); upd(); }; im.src = '/snapshot.jpg?_=' + Date.now(); };
saveBtn.onclick = () => saveCameraOrCalib(saveBtn);
window.OracoloCalibReload = async () => { try { scene = await (await fetch('/scene')).json(); upd(); } catch {} };
window.OracoloSetCamFromAnchors = (c) => { if (!c) return; cam = [rnd(c[0]), rnd(c[1])]; camH = rnd(c[2]); syncCamInputs(); };
(async () => {
  const qrc = $('qrcard'), c = readCache(); $('qrbtn').onclick = () => { qrc.style.display = qrc.style.display === 'block' ? 'none' : 'block'; }; qrc.onclick = () => { qrc.style.display = 'none'; };
  try {
    const r = await fetch('/scene'); scene = await r.json(); $('qru').textContent = scene.camera_url || '';
    if (scene.cam) { cam = scene.cam.xy; camH = scene.cam.h; } else if (Array.isArray(c.cam_xy)) { cam = c.cam_xy; camH = c.cam_h || camH; }
    syncCamInputs();
    if (scene.calib) {
      calibSize = scene.calib.image_size || calibSize; calibW = calibSize[0] || 0; overlay = scene.calib.overlay || null; ptErrs = scene.calib.point_errors_px || [];
      const ip = scene.calib.img_pts, wp = scene.calib.world_pts;
      if (ip && wp && ip.length >= 4) { imgPts = ip.map((p) => [p[0], p[1]]); worldPts = wp.map((p) => [p[0], p[1], p[2] || 0]); writeCache({ img: imgPts, world: worldPts, image_size: calibSize, cam_xy: cam, cam_h: camH }); }
      else if (c.img && c.world && c.img.length >= 4) { imgPts = c.img; worldPts = c.world; }
      if (scene.calib.rms_m != null) msg(`Calibrazione attiva (RMS ${(scene.calib.rms_m * 100).toFixed(1)} cm${scene.calib.rms_px != null ? ` / ${scene.calib.rms_px.toFixed(1)} px` : ''}). Trascina i marcatori o aggiungi punti 3D per rifinire.`);
    } else if (c.img && c.world && c.img.length >= 4) { imgPts = c.img; worldPts = c.world; }
  } catch { msg('Planimetria non disponibile'); }
  im.onload = () => { qrc.style.display = 'none'; calibSize = [im.naturalWidth, im.naturalHeight]; if (calibW && im.naturalWidth && calibW !== im.naturalWidth) { const s = im.naturalWidth / calibW; imgPts = imgPts.map((p) => [p[0] * s, p[1] * s]); calibW = im.naturalWidth; } upd(); };
  im.onerror = () => { qrc.style.display = 'block'; upd(); }; im.src = '/snapshot.jpg?_=' + Date.now(); upd();
})();
