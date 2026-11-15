(() => {
  const COL = ['#007a5a', '#b46900', '#b84a00', '#991b1b'];
  const NAME = ['L0 · NORMALE', 'L1 · ATTENZIONE', 'L2 · RALLENTA', 'L3 · FERMA'];
  const SHORT = ['L0 Normale', 'L1 Attenzione', 'L2 Rallenta', 'L3 Ferma'];

  let scene = null, ver = -1, last = null, qrManual = null, qrMode = 'camera';
  let feedMode = '', lastSnapAt = 0, lastPollOk = Date.now(), prevLogKey = '';
  const events = [];

  const $ = (id) => document.getElementById(id);
  const qrcard = $('qrcard'), vid = $('v'), vempty = $('vempty'), vstat = $('vstat'), alarm = $('alarm');
  const cv = $('map'), ctx = cv.getContext('2d');

  function showQr(mode) {
    const same = qrMode === mode && qrcard.style.display === 'block';
    qrMode = mode;
    qrManual = !same;
    qrcard.style.display = qrManual ? 'block' : 'none';
    if (!qrManual) return;
    const isCab = mode === 'cab';
    $('qrtitle').textContent = isCab ? 'Connetti Sensore Muletto' : 'Connetti Camera';
    $('qrimg').src = isCab ? '/cab_qr.png' : '/qr.png';
    $('qru').textContent = scene ? (isCab ? (scene.cab_url || '') : (scene.camera_url || '')) : '';
    $('qrhint').textContent = isCab
      ? 'Inquadra con il dispositivo sul muletto per ricevere comandi e allarmi.'
      : 'Inquadra con la camera fissa, accetta il certificato e premi Avvia.';
  }
  $('qrbtn').onclick = () => showQr('camera');
  $('cabbtn').onclick = () => showQr('cab');
  qrcard.onclick = () => { qrManual = false; qrcard.style.display = 'none'; };

  function setFeed(mode) {
    feedMode = mode;
    if (mode === 'snap') { lastSnapAt = Date.now(); vid.src = '/snapshot.jpg?_=' + lastSnapAt; }
    else { vid.src = '/video.mjpg?_=' + Date.now(); }
  }
  vid.onload = () => { if (vid.src.indexOf('data:') === 0) return; vid.style.display = 'block'; vempty.style.display = 'none'; };
  vid.onerror = () => { if (feedMode === 'mjpg') setFeed('snap'); else { vid.style.display = 'none'; vempty.style.display = 'block'; } };
  window.addEventListener('pageshow', (e) => { if (e.persisted) setFeed('mjpg'); });
  setTimeout(() => { if ((!vid.naturalWidth || vid.naturalWidth <= 1) && feedMode === 'mjpg') setFeed('snap'); }, 1200);
  setFeed('mjpg');

  const cleanObs = (s) => {
    const n = (s || '').replace(/#\d+$/, '').replace(/_H\d+(?:[.,]\d+)?$/i, '').replace(/_/g, ' ').trim();
    return /^ostacolo \d+$/i.test(n) ? '' : n;
  };

  function view() {
    const r = cv.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
    cv.width = Math.max(1, r.width * dpr); cv.height = Math.max(1, r.height * dpr);
    const xs = scene.bounds.map((p) => p[0]), ys = scene.bounds.map((p) => p[1]);
    const minx = Math.min(...xs), maxx = Math.max(...xs), miny = Math.min(...ys), maxy = Math.max(...ys);
    const pad = 26 * dpr;
    const sc = Math.min((cv.width - 2 * pad) / Math.max(maxx - minx, 0.1), (cv.height - 2 * pad) / Math.max(maxy - miny, 0.1));
    const ox = (cv.width - sc * (maxx - minx)) / 2, oy = (cv.height - sc * (maxy - miny)) / 2;
    return { sc, dpr, minx, maxx, miny, maxy, w: maxx - minx, h: maxy - miny, X: (x) => ox + (x - minx) * sc, Y: (y) => cv.height - oy - (y - miny) * sc };
  }

  function poly(v, pts, fill, stroke, lw) {
    ctx.beginPath();
    pts.forEach((p, i) => (i ? ctx.lineTo(v.X(p[0]), v.Y(p[1])) : ctx.moveTo(v.X(p[0]), v.Y(p[1]))));
    ctx.closePath();
    if (fill) { ctx.fillStyle = fill; ctx.fill(); }
    if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = lw || 1; ctx.stroke(); }
  }

  function arrow(x0, y0, x1, y1, color, lw, head) {
    const dx = x1 - x0, dy = y1 - y0, a = Math.atan2(dy, dx);
    ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = lw;
    ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x1 - head * Math.cos(a - 0.45), y1 - head * Math.sin(a - 0.45));
    ctx.lineTo(x1 - head * Math.cos(a + 0.45), y1 - head * Math.sin(a + 0.45));
    ctx.closePath(); ctx.fill();
  }

  function draw() {
    if (!scene) return;
    const v = view();
    ctx.clearRect(0, 0, cv.width, cv.height);
    poly(v, scene.bounds, '#0d111a', '#94a3b8', 2 * v.dpr);

    // Griglia metrica 1m x 1m per leggibilità immediata delle distanze
    ctx.save();
    ctx.beginPath();
    scene.bounds.forEach((p, i) => (i ? ctx.lineTo(v.X(p[0]), v.Y(p[1])) : ctx.moveTo(v.X(p[0]), v.Y(p[1]))));
    ctx.closePath(); ctx.clip();
    ctx.strokeStyle = 'rgba(148,163,184,0.10)'; ctx.lineWidth = 1;
    for (let gx = Math.ceil(v.minx); gx <= Math.floor(v.maxx); gx++) {
      ctx.beginPath(); ctx.moveTo(v.X(gx), v.Y(v.miny)); ctx.lineTo(v.X(gx), v.Y(v.maxy)); ctx.stroke();
    }
    for (let gy = Math.ceil(v.miny); gy <= Math.floor(v.maxy); gy++) {
      ctx.beginPath(); ctx.moveTo(v.X(v.minx), v.Y(gy)); ctx.lineTo(v.X(v.maxx), v.Y(gy)); ctx.stroke();
    }
    if (last && last.fog) {
      const f = last.fog, bin = atob(f.b64);
      for (let iy = 0; iy < f.ny; iy++) for (let ix = 0; ix < f.nx; ix++) {
        const s = bin.charCodeAt(iy * f.nx + ix); if (!s) continue;
        ctx.fillStyle = s === 1 ? 'rgba(0,158,115,.32)' : s === 2 ? 'rgba(148,163,184,.20)' : s === 3 ? 'rgba(230,159,0,.32)' : 'rgba(204,51,17,.58)';
        const x0 = v.X(f.minx + ix * f.res), y0 = v.Y(f.miny + iy * f.res), x1 = v.X(f.minx + (ix + 1) * f.res), y1 = v.Y(f.miny + (iy + 1) * f.res);
        ctx.fillRect(Math.min(x0, x1), Math.min(y0, y1), Math.abs(x1 - x0) + 1, Math.abs(y1 - y0) + 1);
      }
    } else if (scene.shadows) { scene.shadows.forEach((s) => poly(v, s, 'rgba(255,200,0,.25)', null, 0)); }
    ctx.restore();

    scene.occluders.forEach((o) => {
      if (!o.coords.length) return;
      poly(v, o.coords, '#3b230c', '#f59e0b', 2 * v.dpr);
      const lbl = cleanObs(o.name); if (!lbl) return;
      const xs = o.coords.map((p) => p[0]), ys = o.coords.map((p) => p[1]);
      ctx.fillStyle = '#fef3c7'; ctx.font = '600 ' + (11 * v.dpr) + 'px sans-serif';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(lbl, v.X((Math.min(...xs) + Math.max(...xs)) / 2), v.Y((Math.min(...ys) + Math.max(...ys)) / 2));
    });
    ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';

    if (scene.fov) poly(v, scene.fov, null, 'rgba(86,180,233,.72)', 1.5 * v.dpr);
    if (scene.cam) {
      const c = scene.cam.xy, dir = ((scene.cam.dir ?? 0) * Math.PI) / 180, hf = (((scene.cam.fov ?? 75) * Math.PI) / 180) / 2;
      if (hf < Math.PI - 0.02) {
        const r = 1.4; ctx.strokeStyle = 'rgba(86,180,233,.7)'; ctx.lineWidth = 1.5 * v.dpr; ctx.beginPath();
        ctx.moveTo(v.X(c[0] + r * Math.cos(dir - hf)), v.Y(c[1] + r * Math.sin(dir - hf)));
        ctx.lineTo(v.X(c[0]), v.Y(c[1]));
        ctx.lineTo(v.X(c[0] + r * Math.cos(dir + hf)), v.Y(c[1] + r * Math.sin(dir + hf))); ctx.stroke();
      }
      ctx.fillStyle = '#93c5fd'; ctx.beginPath(); ctx.arc(v.X(c[0]), v.Y(c[1]), 6.5 * v.dpr, 0, 7); ctx.fill();
      ctx.font = (11.5 * v.dpr) + 'px sans-serif';
      ctx.fillText(`Cam (${(scene.cam.h || 1.8).toFixed(1)}m)`, v.X(c[0]) + 10 * v.dpr, v.Y(c[1]) - 6 * v.dpr);
    }
    ctx.fillStyle = '#94a3b8'; ctx.font = (11 * v.dpr) + 'px sans-serif'; ctx.textAlign = 'right';
    ctx.fillText(`Area ${v.w.toFixed(1)} × ${v.h.toFixed(1)} m · griglia 1 m`, cv.width - 10 * v.dpr, cv.height - 8 * v.dpr);
    ctx.textAlign = 'left';
    if (!last) return;

    const lv = last.decision ? last.decision.level : 0, col = COL[lv];
    if (last.path && last.path.length > 1) {
      ctx.beginPath();
      last.path.forEach((p, i) => (i ? ctx.lineTo(v.X(p[0]), v.Y(p[1])) : ctx.moveTo(v.X(p[0]), v.Y(p[1]))));
      ctx.strokeStyle = col; ctx.lineWidth = 5 * v.dpr; ctx.lineCap = 'round'; ctx.stroke();
    }
    (last.persons || []).forEach((p) => {
      if (!p.xy) return;
      const px = v.X(p.xy[0]), py = v.Y(p.xy[1]), mv = p.speed > 0.25;
      if (mv && (p.vx || p.vy)) {
        arrow(px, py, v.X(p.xy[0] + p.vx * 0.7), v.Y(p.xy[1] + p.vy * 0.7), '#fde047', 2.2 * v.dpr, 7 * v.dpr);
      }
      ctx.fillStyle = mv ? '#38bdf8' : '#56b4e9';
      ctx.beginPath(); ctx.arc(px, py, 8 * v.dpr, 0, 7); ctx.fill();
      ctx.strokeStyle = mv ? '#fde047' : '#ffffff'; ctx.lineWidth = 2 * v.dpr; ctx.stroke();
      ctx.fillStyle = '#f8fafc'; ctx.font = '700 ' + (11.5 * v.dpr) + 'px sans-serif';
      ctx.fillText(mv ? `P${p.id} · ${p.speed.toFixed(1)}m/s` : `P${p.id}`, px + 11 * v.dpr, py + 4 * v.dpr);
    });
    if (last.vehicle) {
      const q = last.vehicle, x = v.X(q.xy[0]), y = v.Y(q.xy[1]);
      ctx.save(); ctx.translate(x, y); ctx.rotate(-q.heading);
      ctx.fillStyle = q.tracked ? col : '#64748b';
      ctx.fillRect(-13 * v.dpr, -9 * v.dpr, 26 * v.dpr, 18 * v.dpr);
      ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 1.8 * v.dpr;
      ctx.strokeRect(-13 * v.dpr, -9 * v.dpr, 26 * v.dpr, 18 * v.dpr);
      ctx.fillStyle = '#ffffff'; ctx.beginPath();
      ctx.moveTo(19 * v.dpr, 0); ctx.lineTo(8 * v.dpr, -7 * v.dpr); ctx.lineTo(8 * v.dpr, 7 * v.dpr); ctx.fill();
      ctx.restore();
      ctx.fillStyle = '#ffffff'; ctx.font = '700 ' + (11 * v.dpr) + 'px sans-serif';
      ctx.fillText(`${q.speed.toFixed(1)} m/s`, x + 16 * v.dpr, y - 12 * v.dpr);
    }
  }

  function updateRailTelemetry(s) {
    const v = s.vehicle, d = s.decision;
    const vBadge = $('vbadge'), vSpd = $('vspd'), vBar = $('vbar'), vLim = $('vlimlbl');
    if (v) {
      vBadge.textContent = v.tracked ? 'TRACCIATO' : 'PERSO';
      vBadge.className = 'pill ' + (v.tracked ? 'ok' : 'bad');
      const sp = v.speed || 0, lim = d ? d.limit : 1.0;
      vSpd.textContent = `${sp.toFixed(2)} m/s (${(sp * 3.6).toFixed(1)} km/h)`;
      vLim.textContent = d ? `Limite: ${lim.toFixed(2)} m/s` : 'Limite: --';
      const pct = Math.min(1, sp / Math.max(lim, 0.25));
      vBar.style.transform = `scaleX(${pct.toFixed(3)})`;
      vBar.style.background = sp > lim + 0.15 ? '#ef4444' : sp > lim * 0.85 ? '#f59e0b' : '#22c55e';
    } else {
      vBadge.textContent = s.calibrated ? 'NON VISIBILE' : 'NON CALIBRATO';
      vBadge.className = 'pill warn';
      vSpd.textContent = '-- m/s';
      vLim.textContent = 'Limite: --';
      vBar.style.transform = 'scaleX(0)';
    }

    const ps = s.persons || [];
    $('pcnt').textContent = String(ps.length);
    const plist = $('plist');
    if (!ps.length) plist.innerHTML = '<div class="empty-msg">Nessun pedone nell\'area</div>';
    else {
      plist.innerHTML = ps.map((p) => {
        const mv = p.speed > 0.25, dist = (v && p.xy) ? Math.hypot(p.xy[0] - v.xy[0], p.xy[1] - v.xy[1]).toFixed(1) + ' m' : '--';
        return `<div class="prow"><span class="pid">P${p.id}</span><span class="pmv ${mv ? 'mv' : ''}">${mv ? 'In movimento' : 'Fermo'}</span><span class="pdata">${p.speed.toFixed(1)} m/s · ${dist}</span></div>`;
      }).join('');
    }

    const evKey = d ? `${d.level}:${d.cause}` : (s.calibrated ? 'NOMARKER' : 'NOCAL');
    if (evKey !== prevLogKey) {
      prevLogKey = evKey;
      const ts = new Date().toTimeString().slice(0, 8);
      const txt = d ? `${SHORT[d.level]} — ${d.cause_it}` : (s.calibrated ? 'Muletto non visibile' : 'Calibrazione mancante');
      events.unshift({ ts, txt, lv: d ? d.level : -1 });
      if (events.length > 4) events.pop();
      $('evlog').innerHTML = events.map((e) => `<div class="erow"><span class="ts">${e.ts}</span><span>${e.txt}</span></div>`).join('');
    }
  }

  const cadrep = $('cadrep'), cadinfo = $('cadinfo');
  const showRep = (rep, title) => { oracoloReportInto(cadrep, rep, title); cadrep.style.display = 'block'; };
  cadrep.onclick = () => { cadrep.style.display = 'none'; };
  cadinfo.onclick = () => { if (scene && scene.cad) cadrep.style.display = cadrep.style.display === 'block' ? 'none' : 'block'; };
  const pickDxf = () => oracoloPickDxf($('dxffile'), (rep) => { showRep(rep); if (rep.ok) loadScene(); });
  $('dxfbtn').onclick = pickDxf; $('dxfbtn2').onclick = pickDxf;

  function updCad() {
    const c = scene && scene.cad;
    if (!c) { cadinfo.textContent = scene && scene.no_scene ? 'nessuna' : '--'; return; }
    const st = c.stats || {}, n = (c.warnings || []).length;
    cadinfo.textContent = `${(st.size_m || []).join('×')} m · ${st.occluders ?? '?'} ostacoli` + (n ? ` · ${n} avvisi` : '');
    oracoloReportInto(cadrep, c);
  }

  async function loadScene() {
    try {
      scene = await (await fetch('/scene')).json();
      updCad();
      $('cam').textContent = scene.camera_url || '';
      $('qru').textContent = (qrMode === 'cab' ? scene.cab_url : scene.camera_url) || '';
      $('nocal').style.display = scene.calibrated ? 'none' : 'block';
      draw();
    } catch (e) {}
  }

  function setActiveStep(lv) {
    for (let i = 0; i < 4; i++) $('lv' + i)?.classList.toggle('active', i === lv);
  }

  async function poll() {
    try {
      last = await (await fetch('/state?_=' + Date.now(), { cache: 'no-store' })).json();
      lastPollOk = Date.now();
      if ((last.version !== undefined && last.version !== ver) || (scene && scene.no_scene && !last.no_scene)) {
        ver = last.version; loadScene(); if (last.stale && feedMode === 'snap') setFeed('snap');
      }
      $('choose').style.display = last.no_scene ? 'flex' : 'none';
      if (qrManual === null) qrcard.style.display = (!last.no_scene && (last.age === null || last.age === undefined)) ? 'block' : 'none';
      if (last.stale) {
        vstat.style.display = 'block';
        vstat.textContent = '[PAUSA FLUSSO] Ultimo frame congelato — riapri /camera o premi "QR Camera"';
        alarm.style.display = 'block';
        if ((!vid.naturalWidth || vid.naturalWidth <= 1 || feedMode === 'snap') && Date.now() - lastSnapAt > 2000) setFeed('snap');
      } else {
        vstat.style.display = 'none'; alarm.style.display = 'none';
        if (last.age !== null && last.age !== undefined && last.age < 1.5 && (feedMode !== 'mjpg' || !vid.naturalWidth || vid.naturalWidth <= 1)) setFeed('mjpg');
      }
      const d = last.decision, bar = $('bar');
      if (d) {
        bar.style.background = COL[d.level];
        $('lvl').textContent = NAME[d.level];
        setActiveStep(d.level);
        $('lim').textContent = `Limite ${d.limit.toFixed(2)} m/s (${(d.limit * 3.6).toFixed(1)} km/h)`;
        $('cause').textContent = d.cause_it;
      } else {
        bar.style.background = '#334155';
        $('lvl').textContent = last.calibrated ? 'MULETTO NON RILEVATO' : 'NON CALIBRATO';
        setActiveStep(-1);
        $('lim').textContent = 'Limite -- m/s';
        $('cause').textContent = last.calibrated ? 'Marker ArUco non visibile nell\'inquadratura' : 'Esegui la calibrazione camera';
      }
      const al = last.align, ab = $('alignbar'), alst = $('alst');
      if (al && (al.status === 'NON_COINCIDE' || al.status === 'DEGRADATO')) {
        ab.style.display = 'block'; ab.className = al.status === 'NON_COINCIDE' ? 'bad' : 'warn';
        ab.textContent = (al.status === 'DEGRADATO' ? 'Allineamento degradato — ' : '') + (al.message || '');
      } else ab.style.display = 'none';
      alst.textContent = !al ? '--' : al.status === 'NON_VERIFICATO' ? 'non verificato'
        : al.status === 'SENZA_CALIBRAZIONE' ? `ancore ${al.n_seen}/${al.n_anchors}`
        : al.status + (al.rms_m != null ? ` (${(al.rms_m * 100).toFixed(1)} cm)` : '');
      $('fps').textContent = last.fps ?? '--';
      $('lat').textContent = last.latency !== undefined ? Math.round(last.latency * 1000) + ' ms' : '--';
      $('vio').textContent = last.violations ?? 0;
      updateRailTelemetry(last);
      draw();
    } catch (e) {
      if (Date.now() - lastPollOk > 1200) {
        $('bar').style.background = COL[3]; $('lvl').textContent = NAME[3]; setActiveStep(3);
        $('lim').textContent = 'Limite 0.00 m/s (0.0 km/h)';
        $('cause').textContent = 'Connessione server interrotta — arresto fail-safe';
        alarm.style.display = 'block';
      }
    } finally {
      setTimeout(poll, 45);
    }
  }

  window.addEventListener('resize', draw); loadScene(); poll();
})();
