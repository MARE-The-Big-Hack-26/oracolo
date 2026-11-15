import {
  VERT, SCENE_FRAG, BLUR_FRAG, COMPOSITE_FRAG,
  SHAPE_MODES, INTRO_END
} from './waves-glsl.js';

const SETTINGS = {
  shapes: 'mixed', cellSize: 10, dotSize: 0.75, color: '#1b2622',
  hoverColor: '#2ecc71', backgroundColor: '#0c0f0e',
  speed: 1, scale: 1, contrast: 1, brightness: 0.4, flow: 0, direction: 0,
  fade: 0.25, interactive: true, splashRadius: 45, splashStrength: 0.65,
  glow: 0.45, intro: true, introDuration: 1.6
};

const MAX_DPR = 2;
const PIXEL_BUDGET = 8.3e6;
const TIME_RATE = 0.1;
const SIMULATION_STEP = 1 / 60;
const WAVE_SPEED = 0.42;
const WAVE_FRICTION = 0.94;
const WAVE_DECAY = 0.972;
const SETTLED_THRESHOLD = 0.01;

function makeGL(canvas, opts) {
  const gl = canvas.getContext('webgl2', opts);
  if (!gl) return null;
  gl.bindVertexArray(gl.createVertexArray());
  const attr = (data, loc) => {
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(data), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  };
  attr([-1, -1, 3, -1, -1, 3], 0);
  attr([0, 0, 2, 0, 0, 2], 1);
  return gl;
}

function makeProgram(gl, fragment) {
  const compile = (type, src) => {
    const sh = gl.createShader(type);
    gl.shaderSource(sh, src);
    gl.compileShader(sh);
    return sh;
  };
  const p = gl.createProgram();
  gl.attachShader(p, compile(gl.VERTEX_SHADER, VERT));
  gl.attachShader(p, compile(gl.FRAGMENT_SHADER, fragment));
  gl.linkProgram(p);
  const locs = {};
  return { p, u: (name) => locs[name] || (locs[name] = gl.getUniformLocation(p, name)) };
}

function makeTarget(gl) {
  const t = gl.createTexture(), fb = gl.createFramebuffer();
  gl.bindTexture(gl.TEXTURE_2D, t);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  const target = { t, fb, size: [1, 1] };
  target.resize = (w, h) => {
    target.size = [w, h];
    gl.bindTexture(gl.TEXTURE_2D, t);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, w, h, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
    gl.bindFramebuffer(gl.FRAMEBUFFER, fb);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, t, 0);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  };
  target.resize(1, 1);
  return target;
}

const parseColor = (val) => {
  const hex = String(val).replace('#', '');
  return [0, 2, 4].map(o => parseInt(hex.slice(o, o + 2), 16) / 255);
};

export function shapeWaves(root, opts = {}) {
  const s = { ...SETTINGS, ...opts };
  const canvas = document.createElement('canvas');
  canvas.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;display:block;pointer-events:none;';
  root.appendChild(canvas);

  const gl = makeGL(canvas, { alpha: false, antialias: false, depth: false, powerPreference: 'low-power' });
  if (!gl) return;

  const color = parseColor(s.color), hover = parseColor(s.hoverColor), bg = parseColor(s.backgroundColor);
  const glowOn = s.glow > 0.05;
  const scene = makeProgram(gl, SCENE_FRAG);
  const blur = glowOn ? makeProgram(gl, BLUR_FRAG) : null;
  const composite = glowOn ? makeProgram(gl, COMPOSITE_FRAG) : null;
  const sceneTarget = glowOn ? makeTarget(gl) : null;
  const glowA = glowOn ? makeTarget(gl) : null, glowB = glowOn ? makeTarget(gl) : null;

  let frameId = 0, lastTime = 0, time = 0, drift = [0, 0], dpr = 1, k = 1;
  let cols = 1, rows = 1, cellPx = 10, origin = [0, 0];
  let charges = new Float32Array(1), heights = new Float32Array(1), prevHeights = new Float32Array(1);
  let backlog = 0, introStart = 0, introProg = s.intro ? 0 : INTRO_END, introArmed = s.intro;
  let chargesActive = false, onScreen = true;
  const pointer = { x: 0, y: 0, at: 0, inside: false };
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  const chargeTex = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, chargeTex);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);

  const writeCharges = (resize) => {
    gl.bindTexture(gl.TEXTURE_2D, chargeTex);
    if (resize) gl.texImage2D(gl.TEXTURE_2D, 0, gl.R32F, cols, rows, 0, gl.RED, gl.FLOAT, charges);
    else gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, 0, cols, rows, gl.RED, gl.FLOAT, charges);
  };
  writeCharges(true);

  const splash = (x, y, strength) => {
    const sigma = Math.max(0.5, ((s.splashRadius * k * dpr) / cellPx) * 0.5);
    const reach = Math.ceil(sigma * 2.5);
    const cCol = (x * dpr - origin[0]) / cellPx - 0.5, cRow = (y * dpr - origin[1]) / cellPx - 0.5;
    const minR = Math.max(0, Math.floor(cRow - reach)), maxR = Math.min(rows - 1, Math.ceil(cRow + reach));
    const minC = Math.max(0, Math.floor(cCol - reach)), maxC = Math.min(cols - 1, Math.ceil(cCol + reach));
    for (let r = minR; r <= maxR; r++) {
      const dy = r - cRow;
      for (let c = minC; c <= maxC; c++) {
        const dx = c - cCol;
        const bump = strength * Math.exp(-(dx * dx + dy * dy) / (2 * sigma * sigma));
        const idx = r * cols + c;
        heights[idx] = Math.min(1.2, heights[idx] + bump);
      }
    }
    chargesActive = true;
  };

  const handlePointer = (e) => {
    if (!s.interactive) return;
    const b = root.getBoundingClientRect(), now = performance.now();
    const x = e.clientX - b.left, y = e.clientY - b.top;
    if (x >= 0 && y >= 0 && x <= b.width && y <= b.height) {
      const elapsed = pointer.inside ? Math.max(8, now - pointer.at) : 16;
      const speed = (pointer.inside ? Math.hypot(x - pointer.x, y - pointer.y) / elapsed : 0) * 1000;
      splash(x, y, Math.min(1, 0.22 + speed * 0.0006) * s.splashStrength);
      wake();
      pointer.inside = true;
    } else { pointer.inside = false; }
    pointer.x = x; pointer.y = y; pointer.at = now;
  };

  const stepRipples = () => {
    const lastCol = cols - 1, lastRow = rows - 1; let peak = 0;
    for (let r = 0; r < rows; r++) {
      const up = (r === 0 ? r : r - 1) * cols, dn = (r === lastRow ? r : r + 1) * cols, base = r * cols;
      for (let c = 0; c < cols; c++) {
        const idx = base + c, l = base + (c === 0 ? c : c - 1), rt = base + (c === lastCol ? c : c + 1);
        const h = heights[idx];
        const lap = heights[l] + heights[rt] + heights[up + c] + heights[dn + c] - 4 * h;
        const next = (h + (h - prevHeights[idx]) * WAVE_FRICTION + WAVE_SPEED * lap) * WAVE_DECAY;
        prevHeights[idx] = next;
        const ch = Math.min(1, Math.max(0, next));
        charges[idx] = ch;
        if (ch > peak) peak = ch;
      }
    }
    const swp = heights; heights = prevHeights; prevHeights = swp;
    return peak;
  };

  const updateCharges = (dt) => {
    if (!chargesActive) return false;
    backlog = Math.min(backlog + dt, SIMULATION_STEP * 4);
    let peak = 1;
    while (backlog >= SIMULATION_STEP) { backlog -= SIMULATION_STEP; peak = stepRipples(); }
    if (peak < SETTLED_THRESHOLD) {
      heights.fill(0); prevHeights.fill(0); charges.fill(0); chargesActive = false;
    }
    writeCharges(false);
    return chargesActive;
  };

  const pass = (target, prog, sz) => {
    gl.bindFramebuffer(gl.FRAMEBUFFER, target ? target.fb : null);
    gl.viewport(0, 0, sz[0], sz[1]);
    gl.useProgram(prog.p);
  };

  const render = (now) => {
    frameId = 0;
    if (!onScreen) { lastTime = 0; return; }
    const dt = lastTime ? Math.min(0.1, (now - lastTime) / 1000) : 0;
    lastTime = now;
    const animating = !document.hidden && s.speed > 0 && !reduceMotion.matches;
    if (animating) {
      time += dt * TIME_RATE * s.speed;
      const rad = (s.direction * Math.PI) / 180, dist = s.flow * cellPx * dt;
      drift = [drift[0] + Math.cos(rad) * dist, drift[1] + Math.sin(rad) * dist];
    }
    const hovering = !document.hidden && updateCharges(dt);
    if (introArmed) { introArmed = false; introStart = now; introProg = 0; }
    const introPlaying = introProg < INTRO_END;
    if (introPlaying) introProg = Math.min(INTRO_END, ((now - introStart) / 1000 / s.introDuration) * INTRO_END);

    const W = canvas.width, H = canvas.height;
    pass(glowOn ? sceneTarget : null, scene, [W, H]);
    gl.uniform4f(scene.u('uResolution'), W, H, 1 / W, 1 / H);
    gl.uniform4f(scene.u('uPlacement'), origin[0], origin[1], rows, introProg);
    gl.uniform4f(scene.u('uGrid'), cellPx, Math.min(1, Math.max(0.1, s.dotSize)), SHAPE_MODES[s.shapes] ?? 0, cols);
    gl.uniform4f(scene.u('uField'), 32 * cellPx * s.scale, 0.5 - (s.brightness - 0.5) * 0.4, 2.8 * s.contrast, time);
    gl.uniform4f(scene.u('uMotion'), drift[0], drift[1], 0, s.fade);
    gl.uniform4f(scene.u('uColor'), color[0], color[1], color[2], 1);
    gl.uniform4f(scene.u('uHover'), hover[0], hover[1], hover[2], glowOn ? 1 : 0);
    gl.uniform4f(scene.u('uBackground'), bg[0], bg[1], bg[2], 1);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, chargeTex);
    gl.uniform1i(scene.u('tCharges'), 0);
    gl.drawArrays(gl.TRIANGLES, 0, 3);

    if (glowOn) {
      const half = glowA.size;
      pass(glowA, blur, half);
      gl.uniform4f(blur.u('uDirection'), 1 / half[0], 0, 4, 1);
      gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, sceneTarget.t);
      gl.uniform1i(blur.u('tSource'), 0);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      pass(glowB, blur, half);
      gl.uniform4f(blur.u('uDirection'), 0, 1 / half[1], 4, 0);
      gl.bindTexture(gl.TEXTURE_2D, glowA.t);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      pass(null, composite, [W, H]);
      gl.uniform4f(composite.u('uStrength'), 2 * s.glow, 0, 0, 0);
      gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, sceneTarget.t);
      gl.uniform1i(composite.u('tScene'), 0);
      gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, glowB.t);
      gl.uniform1i(composite.u('tGlow'), 1);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    }
    if (animating || hovering || introPlaying) frameId = requestAnimationFrame(render);
    else lastTime = 0;
  };

  function wake() { if (!frameId) frameId = requestAnimationFrame(render); }

  const configureGrid = () => {
    const W = canvas.width, H = canvas.height;
    const nextCols = Math.max(1, Math.round(W / (s.cellSize * k * dpr)));
    cellPx = W / nextCols;
    const nextRows = Math.max(1, Math.floor(H / cellPx));
    origin = [0, (H - nextRows * cellPx) / 2];
    if (nextCols === cols && nextRows === rows && charges.length === cols * rows) return;
    cols = nextCols; rows = nextRows;
    charges = new Float32Array(cols * rows);
    heights = new Float32Array(cols * rows);
    prevHeights = new Float32Array(cols * rows);
    chargesActive = false;
    writeCharges(true);
  };

  const resize = () => {
    const f = parseFloat(getComputedStyle(document.documentElement).fontSize);
    k = f > 0 ? f / 16 : 1;
    dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR);
    const area = Math.max(1, root.clientWidth * root.clientHeight);
    if (area * dpr * dpr > PIXEL_BUDGET) dpr = Math.max(0.75, Math.sqrt(PIXEL_BUDGET / area));
    const W = Math.max(1, Math.round(root.clientWidth * dpr));
    const H = Math.max(1, Math.round(root.clientHeight * dpr));
    canvas.width = W; canvas.height = H;
    if (glowOn) {
      sceneTarget.resize(W, H);
      glowA.resize(Math.max(1, Math.ceil(W / 2)), Math.max(1, Math.ceil(H / 2)));
      glowB.resize(Math.max(1, Math.ceil(W / 2)), Math.max(1, Math.ceil(H / 2)));
    }
    configureGrid();
    wake();
  };

  new ResizeObserver(resize).observe(root);
  new IntersectionObserver(([e]) => { onScreen = e.isIntersecting; if (onScreen) wake(); }).observe(root);
  document.addEventListener('visibilitychange', wake);
  reduceMotion.addEventListener('change', wake);
  window.addEventListener('pointermove', handlePointer, { passive: true });
  if (s.intro && !reduceMotion.matches) introArmed = true;
  resize();
}

export function initializeWaves() {
  document.querySelectorAll('.waves').forEach(el => shapeWaves(el));
}
