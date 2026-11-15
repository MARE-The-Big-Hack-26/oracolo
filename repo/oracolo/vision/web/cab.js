(() => {
  const NAME = ['L0 · NORMALE', 'L1 · ATTENZIONE', 'L2 · RALLENTA', 'L3 · FERMA'];
  const SYM = ['▶', '△', '▼', '■'];
  const TTL_MS = 1600;

  const app = document.getElementById('app');
  const dot = document.getElementById('dot');
  const linktxt = document.getElementById('linktxt');
  const agepill = document.getElementById('agepill');
  const audiobtn = document.getElementById('audiobtn');
  const alignwarn = document.getElementById('alignwarn');
  const sym = document.getElementById('sym');
  const lvl = document.getElementById('lvl');
  const spd = document.getElementById('spd');
  const spdkmh = document.getElementById('spdkmh');
  const cause = document.getElementById('cause');
  const vcur = document.getElementById('vcur');
  const np = document.getElementById('np');
  const al = document.getElementById('al');
  const rxEl = document.getElementById('rx');
  const fpsEl = document.getElementById('fps');
  const logEl = document.getElementById('log');

  let audioCtx = null, audioOn = false;
  let lastState = null, lastOkAt = 0, rxCount = 0;
  let prevKey = '', prevLevel = -1;

  function beep(level) {
    if (!audioOn || !audioCtx) return;
    try {
      const now = audioCtx.currentTime;
      const play = (freq, start, dur) => {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = level >= 3 ? 'square' : 'triangle';
        osc.frequency.value = freq;
        gain.gain.setValueAtTime(0.18, start);
        gain.gain.exponentialRampToValueAtTime(0.001, start + dur);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start(start);
        osc.stop(start + dur);
      };
      if (level >= 3) { play(880, now, 0.14); play(660, now + 0.17, 0.18); }
      else if (level === 2) { play(587, now, 0.14); }
    } catch (e) {}
  }

  audiobtn.onclick = async () => {
    audioOn = !audioOn;
    if (audioOn && !audioCtx) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (Ctx) audioCtx = new Ctx();
    }
    if (audioOn && audioCtx && audioCtx.state === 'suspended') {
      try { await audioCtx.resume(); } catch (e) {}
    }
    audiobtn.classList.toggle('on', audioOn);
    audiobtn.textContent = audioOn ? 'AUDIO ON' : 'AUDIO OFF';
    try { if (navigator.wakeLock) await navigator.wakeLock.request('screen'); } catch (e) {}
  };

  function addLog(tag, msg) {
    const t = new Date().toTimeString().slice(0, 8);
    const row = document.createElement('div');
    row.className = 'lrow';
    row.innerHTML = `<span class="ts">${t}</span><span class="tag">${tag}</span><span>${msg}</span>`;
    logEl.prepend(row);
    while (logEl.children.length > 18) logEl.removeChild(logEl.lastChild);
  }

  function setLevelClass(lv) {
    app.classList.remove('lv0', 'lv1', 'lv2', 'lv3');
    if (lv >= 0 && lv <= 3) app.classList.add('lv' + lv);
  }

  function pulseAlert() {
    app.classList.remove('pulse');
    void app.offsetWidth;
    app.classList.add('pulse');
    try { if (navigator.vibrate) navigator.vibrate([120, 60, 120]); } catch (e) {}
  }

  function render() {
    const now = performance.now();
    const ageMs = lastOkAt ? Math.round(now - lastOkAt) : null;
    const lost = lastOkAt > 0 && ageMs > TTL_MS;

    if (!lastState && !lost) return;

    if (lost || (lastState && lastState.stale)) {
      const why = lost
        ? 'SEGNALE PERSO — ARRESTO FAIL-SAFE'
        : (lastState.decision ? lastState.decision.cause_it : 'FLUSSO INTERROTTO — ARRESTO FAIL-SAFE');
      setLevelClass(3);
      dot.className = 'dot bad';
      linktxt.textContent = 'SEGNALE PERSO';
      agepill.textContent = ageMs !== null ? `${ageMs} ms` : '-- ms';
      sym.textContent = SYM[3];
      lvl.textContent = NAME[3];
      spd.textContent = '0.00 m/s';
      spdkmh.textContent = '0.0 km/h · ARRESTO AUTOMATICO';
      cause.textContent = why;
      const key = 'FAILSAFE:' + why;
      if (key !== prevKey) {
        prevKey = key;
        if (prevLevel < 3) { beep(3); pulseAlert(); }
        prevLevel = 3;
        addLog('[FAIL-SAFE]', why);
      }
      return;
    }

    const s = lastState;
    dot.className = 'dot ok';
    linktxt.textContent = 'LINK OK';
    agepill.textContent = (s.latency !== undefined ? Math.round(s.latency * 1000) : ageMs) + ' ms';
    rxEl.textContent = String(rxCount);
    fpsEl.textContent = (s.fps ?? '--') + ' fps';
    np.textContent = String((s.persons || []).length);
    vcur.textContent = s.vehicle ? s.vehicle.speed.toFixed(2) + ' m/s' : '--';

    const a = s.align;
    al.textContent = !a ? '--' : a.status === 'OK' ? 'OK' : a.status === 'NON_VERIFICATO' ? 'N/V' : a.status;
    if (a && (a.status === 'NON_COINCIDE' || a.status === 'DEGRADATO')) {
      alignwarn.style.display = 'block';
      alignwarn.textContent = `${a.status}: ${a.message || 'Verifica allineamento CAD'}`;
    } else {
      alignwarn.style.display = 'none';
    }

    const d = s.decision;
    if (d) {
      setLevelClass(d.level);
      sym.textContent = SYM[d.level];
      lvl.textContent = NAME[d.level];
      spd.textContent = d.limit.toFixed(2) + ' m/s';
      spdkmh.textContent = (d.limit * 3.6).toFixed(1) + ' km/h · LIMITE COMANDATO';
      cause.textContent = d.cause_it;
      const key = `${d.level}:${d.cause}:${d.limit.toFixed(2)}`;
      if (key !== prevKey) {
        prevKey = key;
        if (d.level >= 2 && d.level > prevLevel) { beep(d.level); pulseAlert(); }
        prevLevel = d.level;
        addLog(`[L${d.level}]`, `${d.limit.toFixed(2)} m/s · ${d.cause_it}`);
      }
    } else {
      setLevelClass(-1);
      sym.textContent = '●';
      lvl.textContent = s.no_scene ? 'NESSUNA PLANIMETRIA' : (s.calibrated ? 'MULETTO NON RILEVATO' : 'NON CALIBRATO');
      spd.textContent = '-- m/s';
      spdkmh.textContent = 'IN ATTESA DI RILEVAMENTO';
      cause.textContent = s.calibrated ? "Marker ArUco non visibile nell'inquadratura" : 'Esegui la calibrazione camera dal pannello';
      prevLevel = -1;
    }
  }

  async function poll() {
    try {
      const r = await fetch('/state?_=' + Date.now(), { cache: 'no-store' });
      if (!r.ok) return;
      lastState = await r.json();
      lastOkAt = performance.now();
      rxCount++;
      render();
    } catch (e) {}
  }

  addLog('[INIT]', 'Sensore muletto pronto · in attesa comandi');
  setInterval(poll, 100);
  setInterval(render, 120);
})();
