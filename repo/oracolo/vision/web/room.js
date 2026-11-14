import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const $ = (id) => document.getElementById(id), viewEl = $('view');
const msg = (t) => { $('msg').textContent = t; };
const snap = (v) => Math.round(v * 20) / 20, rnd = (v) => Math.round(v * 100) / 100;
const cleanName = (s) => { const n = (s || '').replace(/#\d+$/, '').replace(/_H\d+(?:[.,]\d+)?$/i, '').toLowerCase(); return /^ostacolo_\d+$/.test(n) ? '' : n; };
const dispName = (o, i) => (o.name || '').trim() || `#${i + 1}`;
const fEl = { n: $('fn'), w: $('fw'), d: $('fd'), h: $('fh'), x: $('fx'), y: $('fy') };
const sEl = { w: $('sw'), d: $('sd'), h: $('sh') }, rwEl = $('rw'), rdEl = $('rd');

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
viewEl.appendChild(renderer.domElement);
const scene3d = new THREE.Scene(); scene3d.background = new THREE.Color('#0d1016');
const camera = new THREE.PerspectiveCamera(46, 1, 0.05, 200);
const orbit = new OrbitControls(camera, renderer.domElement);
orbit.enableDamping = true; orbit.maxPolarAngle = Math.PI / 2 - 0.03;
scene3d.add(new THREE.AmbientLight('#ffffff', 0.9));
const sun = new THREE.DirectionalLight('#fff8eb', 1.15); sun.position.set(6, 12, 8); scene3d.add(sun);

const roomGroup = new THREE.Group(), obsGroup = new THREE.Group(), handleGroup = new THREE.Group();
scene3d.add(roomGroup, obsGroup, handleGroup);
let bounds = [[0, 0], [5, 0], [5, 4], [0, 4]], obstacles = [], camInfo = null, fovPts = null, sel = -1, entries = [], drag = null;

function drawSprite(sp, l1, l2) {
  const c = sp.userData.canvas, ctx = c.getContext('2d');
  ctx.clearRect(0, 0, c.width, c.height);
  ctx.fillStyle = 'rgba(15,17,21,0.84)';
  ctx.strokeStyle = '#475569';
  ctx.lineWidth = 2;
  ctx.beginPath(); ctx.roundRect(4, 4, c.width - 8, c.height - 8, 12); ctx.fill(); ctx.stroke();
  ctx.textAlign = 'center';
  ctx.fillStyle = '#f8fafc'; ctx.font = 'bold 22px sans-serif'; ctx.fillText(l1, c.width / 2, 30);
  if (l2) { ctx.fillStyle = '#fde68a'; ctx.font = '18px sans-serif'; ctx.fillText(l2, c.width / 2, 54); }
  sp.material.map.needsUpdate = true;
}
function makeSprite(l1, l2, w = 1.25) {
  const c = document.createElement('canvas'); c.width = 320; c.height = l2 ? 72 : 46;
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(c), depthTest: false }));
  sp.scale.set(w, w * c.height / c.width, 1);
  sp.userData.canvas = c;
  drawSprite(sp, l1, l2);
  return sp;
}
function flatShape(pts, mat, y) {
  const sh = new THREE.Shape();
  pts.forEach((p, i) => (i ? sh.lineTo(p[0], p[1]) : sh.moveTo(p[0], p[1])));
  sh.closePath();
  const m = new THREE.Mesh(new THREE.ShapeGeometry(sh), mat);
  m.rotation.x = -Math.PI / 2;
  m.position.y = y;
  return m;
}
function roomSpan() {
  const xs = bounds.map((p) => p[0]), ys = bounds.map((p) => p[1]);
  const minx = Math.min(...xs), maxx = Math.max(...xs), miny = Math.min(...ys), maxy = Math.max(...ys);
  return { minx, maxx, miny, maxy, cx: (minx + maxx) / 2, cy: (miny + maxy) / 2 };
}
function setCameraView(top = false) {
  const b = roomSpan(), span = Math.max(b.maxx - b.minx, b.maxy - b.miny, 3);
  orbit.target.set(b.cx, 0.35, -b.cy);
  camera.position.set(b.cx + (top ? 0 : span * 0.72), top ? span * 1.45 : span * 0.88, -b.cy + (top ? 0.01 : span * 0.98));
  orbit.update();
}

function buildRoom() {
  roomGroup.clear();
  const b = roomSpan();
  const gx0 = Math.floor(b.minx) - 1, gx1 = Math.ceil(b.maxx) + 1, gy0 = Math.floor(b.miny) - 1, gy1 = Math.ceil(b.maxy) + 1;
  const gPts = [];
  for (let x = gx0; x <= gx1 + 1e-6; x += 0.5) gPts.push(x, 0, -gy0, x, 0, -gy1);
  for (let y = gy0; y <= gy1 + 1e-6; y += 0.5) gPts.push(gx0, 0, -y, gx1, 0, -y);
  const gGeo = new THREE.BufferGeometry();
  gGeo.setAttribute('position', new THREE.Float32BufferAttribute(gPts, 3));
  roomGroup.add(new THREE.LineSegments(gGeo, new THREE.LineBasicMaterial({ color: '#212838' })));
  roomGroup.add(flatShape(bounds, new THREE.MeshStandardMaterial({ color: '#1c2333', roughness: 0.9, side: THREE.DoubleSide }), 0.002));

  let area2 = 0;
  for (let i = 0; i < bounds.length; i++) {
    const p = bounds[i], q = bounds[(i + 1) % bounds.length];
    area2 += p[0] * q[1] - q[0] * p[1];
  }
  const sgn = area2 >= 0 ? 1 : -1, wallH = 2.4;
  const wallMat = new THREE.MeshStandardMaterial({ color: '#2c364c', roughness: 0.95, side: THREE.FrontSide });
  for (let i = 0; i < bounds.length; i++) {
    const p = bounds[i], q = bounds[(i + 1) % bounds.length];
    const dx = q[0] - p[0], dy = q[1] - p[1], len = Math.hypot(dx, dy);
    if (len < 0.05) continue;
    const wall = new THREE.Mesh(new THREE.PlaneGeometry(len, wallH), wallMat);
    wall.position.set((p[0] + q[0]) / 2, wallH / 2, -(p[1] + q[1]) / 2);
    wall.rotation.y = Math.atan2(-dy * sgn, -dx * sgn);
    roomGroup.add(wall);
    const lbl = makeSprite(`${len.toFixed(2)} m`, '', 0.95);
    lbl.position.set((p[0] + q[0]) / 2, 0.16, -(p[1] + q[1]) / 2);
    roomGroup.add(lbl);
  }
  roomGroup.add(new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(bounds.map((p) => new THREE.Vector3(p[0], 0.008, -p[1]))), new THREE.LineBasicMaterial({ color: '#cbd5e1' })));
  if (fovPts && fovPts.length >= 3) {
    roomGroup.add(flatShape(fovPts, new THREE.MeshBasicMaterial({ color: '#38bdf8', transparent: true, opacity: 0.14, side: THREE.DoubleSide }), 0.01));
  }
  if (camInfo) {
    const cm = new THREE.Mesh(new THREE.SphereGeometry(0.11, 16, 12), new THREE.MeshBasicMaterial({ color: '#60a5fa' }));
    cm.position.set(camInfo.xy[0], camInfo.h, -camInfo.xy[1]);
    roomGroup.add(cm);
  }
}

const hSphere = new THREE.SphereGeometry(0.11, 16, 12);
const handles = ['east', 'west', 'north', 'south', 'top'].map((kind) => {
  const m = new THREE.Mesh(hSphere, new THREE.MeshBasicMaterial({ color: kind === 'top' ? '#34d399' : '#38bdf8' }));
  m.userData.handle = kind;
  handleGroup.add(m);
  return m;
});
function syncHandles() {
  handleGroup.visible = sel >= 0 && !!obstacles[sel];
  if (!handleGroup.visible) return;
  const o = obstacles[sel], cx = o.x + o.w / 2, cz = -(o.y + o.d / 2), cy = o.height / 2;
  handles[0].position.set(o.x + o.w, cy, cz);
  handles[1].position.set(o.x, cy, cz);
  handles[2].position.set(cx, cy, -(o.y + o.d));
  handles[3].position.set(cx, cy, -o.y);
  handles[4].position.set(cx, o.height, cz);
}

const boxGeo = new THREE.BoxGeometry(1, 1, 1), edgeGeo = new THREE.EdgesGeometry(boxGeo);
function rebuildObstacles() {
  obsGroup.clear(); entries = [];
  obstacles.forEach((o, i) => {
    const mesh = new THREE.Mesh(boxGeo, new THREE.MeshStandardMaterial({ color: i === sel ? '#f97316' : '#b45309', transparent: true, opacity: 0.88, roughness: 0.6 }));
    mesh.add(new THREE.LineSegments(edgeGeo, new THREE.LineBasicMaterial({ color: i === sel ? '#93c5fd' : '#fbbf24' })));
    mesh.scale.set(o.w, o.height, o.d);
    mesh.position.set(o.x + o.w / 2, o.height / 2, -(o.y + o.d / 2));
    mesh.userData.idx = i;
    obsGroup.add(mesh);
    const label = makeSprite(dispName(o, i), `${rnd(o.w)}×${rnd(o.d)} · H ${rnd(o.height)}m`);
    label.position.set(mesh.position.x, o.height + 0.25, mesh.position.z);
    obsGroup.add(label);
    entries.push({ mesh, label });
  });
  syncHandles();
  syncInspector();
}
function updateSelectedVisual() {
  if (sel < 0 || !entries[sel]) return;
  const o = obstacles[sel], { mesh, label } = entries[sel];
  mesh.scale.set(o.w, o.height, o.d);
  mesh.position.set(o.x + o.w / 2, o.height / 2, -(o.y + o.d / 2));
  label.position.set(mesh.position.x, o.height + 0.25, mesh.position.z);
  drawSprite(label, dispName(o, sel), `${rnd(o.w)}×${rnd(o.d)} · H ${rnd(o.height)}m`);
  syncHandles();
}
function select(i) {
  sel = i;
  entries.forEach((e, k) => {
    e.mesh.material.color.set(k === sel ? '#f97316' : '#b45309');
    e.mesh.children[0].material.color.set(k === sel ? '#93c5fd' : '#fbbf24');
  });
  syncHandles();
  syncInspector();
}
function syncList() {
  $('cnt').textContent = obstacles.length;
  const list = $('olist'); list.innerHTML = '';
  obstacles.forEach((ob, i) => {
    const div = document.createElement('div'); div.className = 'item' + (i === sel ? ' sel' : '');
    const info = document.createElement('div'), b = document.createElement('b'), sm = document.createElement('small');
    b.textContent = dispName(ob, i);
    sm.textContent = `${rnd(ob.w)} × ${rnd(ob.d)} m · H ${rnd(ob.height)} m`;
    info.append(b, sm); div.appendChild(info);
    const del = document.createElement('button'); del.textContent = '×'; del.type = 'button';
    del.onclick = (e) => { e.stopPropagation(); obstacles.splice(i, 1); if (sel === i) sel = -1; else if (sel > i) sel--; rebuildObstacles(); };
    div.appendChild(del); div.onclick = () => select(i); list.appendChild(div);
  });
}
function syncFields() {
  const o = obstacles[sel];
  $('none').style.display = o ? 'none' : 'block';
  $('form').style.display = o ? 'block' : 'none';
  if (!o) return;
  fEl.n.value = o.name; fEl.w.value = rnd(o.w); fEl.d.value = rnd(o.d); fEl.h.value = rnd(o.height);
  fEl.x.value = rnd(o.x); fEl.y.value = rnd(o.y);
  [['w', 5], ['d', 5], ['h', 3.5]].forEach(([k, m]) => { const v = k === 'h' ? o.height : o[k]; sEl[k].max = Math.max(m, Math.ceil(v)); sEl[k].value = v; });
}
function syncInspector() { syncFields(); syncList(); }

const ray = new THREE.Raycaster(), ptr = new THREE.Vector2(), hitPt = new THREE.Vector3();
function setPtr(e) {
  const r = renderer.domElement.getBoundingClientRect();
  ptr.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
  ray.setFromCamera(ptr, camera);
}
renderer.domElement.addEventListener('pointerdown', (e) => {
  if (e.button !== 0) return;
  setPtr(e);
  if (handleGroup.visible) {
    const hh = ray.intersectObjects(handles, false);
    if (hh.length) {
      const o = obstacles[sel], kind = hh[0].object.userData.handle;
      const fwd = new THREE.Vector3(); camera.getWorldDirection(fwd); fwd.y = 0; fwd.normalize();
      const plane = kind === 'top' ? new THREE.Plane().setFromNormalAndCoplanarPoint(fwd, hh[0].point) : new THREE.Plane(new THREE.Vector3(0, 1, 0), -o.height / 2);
      drag = { kind, plane }; orbit.enabled = false; renderer.domElement.style.cursor = 'grabbing'; return;
    }
  }
  const mh = ray.intersectObjects(entries.map((x) => x.mesh), false);
  if (mh.length) {
    select(mh[0].object.userData.idx);
    const o = obstacles[sel], plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -o.height / 2);
    ray.ray.intersectPlane(plane, hitPt);
    drag = { kind: 'move', plane, dx: hitPt.x - o.x, dy: -hitPt.z - o.y };
    orbit.enabled = false; renderer.domElement.style.cursor = 'grabbing';
  } else drag = { kind: 'orbit', x: e.clientX, y: e.clientY };
});
window.addEventListener('pointermove', (e) => {
  setPtr(e);
  if (!drag) {
    renderer.domElement.style.cursor = (handleGroup.visible && ray.intersectObjects(handles, false).length)
      ? 'ew-resize' : (ray.intersectObjects(entries.map((x) => x.mesh), false).length ? 'grab' : 'default');
    return;
  }
  if (drag.kind === 'orbit' || !ray.ray.intersectPlane(drag.plane, hitPt)) return;
  const o = obstacles[sel], b = roomSpan();
  if (drag.kind === 'move') { o.x = rnd(Math.max(b.minx, Math.min(b.maxx - o.w, snap(hitPt.x - drag.dx)))); o.y = rnd(Math.max(b.miny, Math.min(b.maxy - o.d, snap(-hitPt.z - drag.dy)))); }
  else if (drag.kind === 'east') o.w = rnd(Math.max(0.1, snap(hitPt.x - o.x)));
  else if (drag.kind === 'west') { const r = o.x + o.w, nx = Math.min(r - 0.1, snap(hitPt.x)); o.x = rnd(nx); o.w = rnd(r - nx); }
  else if (drag.kind === 'north') o.d = rnd(Math.max(0.1, snap(-hitPt.z - o.y)));
  else if (drag.kind === 'south') { const t = o.y + o.d, ny = Math.min(t - 0.1, snap(-hitPt.z)); o.y = rnd(ny); o.d = rnd(t - ny); }
  else if (drag.kind === 'top') o.height = rnd(Math.max(0.1, snap(hitPt.y)));
  updateSelectedVisual(); syncFields();
});
window.addEventListener('pointerup', (e) => {
  if (!drag) return;
  if (drag.kind === 'orbit' && Math.hypot(e.clientX - drag.x, e.clientY - drag.y) < 5) select(-1);
  else if (drag.kind !== 'orbit') syncList();
  drag = null; orbit.enabled = true; renderer.domElement.style.cursor = 'default';
});

Object.entries(fEl).forEach(([k, el]) => el.addEventListener('input', () => {
  const o = obstacles[sel]; if (!o) return;
  if (k === 'n') o.name = el.value;
  else {
    const v = parseFloat(el.value); if (!Number.isFinite(v)) return;
    if (k === 'w') o.w = Math.max(0.1, v); else if (k === 'd') o.d = Math.max(0.1, v);
    else if (k === 'h') o.height = Math.max(0.1, v); else if (k === 'x') o.x = v; else if (k === 'y') o.y = v;
    if (sEl[k]) { sEl[k].max = Math.max(parseFloat(sEl[k].max), v); sEl[k].value = v; }
  }
  updateSelectedVisual(); syncList();
}));
Object.entries(sEl).forEach(([k, el]) => el.addEventListener('input', () => {
  const o = obstacles[sel], v = parseFloat(el.value); if (!o || !Number.isFinite(v)) return;
  if (k === 'w') o.w = v; else if (k === 'd') o.d = v; else if (k === 'h') o.height = v;
  fEl[k].value = rnd(v); updateSelectedVisual(); syncList();
}));

function updateRoomRect() {
  const w = parseFloat(rwEl.value), d = parseFloat(rdEl.value);
  if (w > 0 && d > 0) { bounds = [[0, 0], [w, 0], [w, d], [0, d]]; buildRoom(); msg(`Stanza ${rnd(w)} × ${rnd(d)} m`); }
}
rwEl.addEventListener('input', updateRoomRect); rdEl.addEventListener('input', updateRoomRect);
$('v3d').onclick = () => setCameraView(false); $('vTop').onclick = () => setCameraView(true);
$('addobs').onclick = () => {
  const b = roomSpan(), off = (obstacles.length % 4) * 0.15 - 0.2;
  obstacles.push({ name: '', x: snap(Math.max(b.minx, b.cx - 0.5 + off)), y: snap(Math.max(b.miny, b.cy - 0.5 + off)), w: 1.0, d: 1.0, height: 1.5 });
  sel = obstacles.length - 1; rebuildObstacles(); fEl.n.focus();
};
$('clearobs').onclick = () => { obstacles = []; sel = -1; rebuildObstacles(); };
$('rot').onclick = () => { const o = obstacles[sel]; if (o) { [o.w, o.d] = [o.d, o.w]; updateSelectedVisual(); syncInspector(); } };
$('del').onclick = () => { if (sel >= 0) { obstacles.splice(sel, 1); sel = -1; rebuildObstacles(); } };
$('save').onclick = async () => {
  try {
    const j = await (await fetch('/scene', { method: 'POST', body: JSON.stringify({ bounds, obstacles }) })).json();
    msg(j.ok ? `Planimetria salvata (${j.occluders} oggetti). Ora puoi calibrare la camera.` : `Errore: ${j.error}`);
  } catch (e) { msg(`Errore di rete: ${e}`); }
};
function resize() { const w = viewEl.clientWidth || 1, h = viewEl.clientHeight || 1; camera.aspect = w / h; camera.updateProjectionMatrix(); renderer.setSize(w, h, false); }
window.addEventListener('resize', resize);

(async () => {
  try {
    const sc = await (await fetch('/scene')).json();
    if (sc.bounds && sc.bounds.length >= 4) { const b = sc.bounds; bounds = (b[0][0] === b[b.length - 1][0] && b[0][1] === b[b.length - 1][1]) ? b.slice(0, -1) : b; }
    camInfo = sc.cam || null; fovPts = sc.fov || null;
    obstacles = (sc.occluders || []).map((o, i) => {
      const xs = o.coords.map((p) => p[0]), ys = o.coords.map((p) => p[1]), minx = Math.min(...xs), miny = Math.min(...ys);
      return { name: cleanName(o.name), x: rnd(minx), y: rnd(miny), w: rnd(Math.max(...xs) - minx), d: rnd(Math.max(...ys) - miny), height: rnd(o.height || 1.8) };
    });
    const b = roomSpan(); rwEl.value = rnd(b.maxx - b.minx); rdEl.value = rnd(b.maxy - b.miny);
    msg('Pronto: trascina gli oggetti sul pavimento o usa i pallini per ridimensionare, poi premi «Salva planimetria».');
  } catch (e) { msg('Errore nel caricamento della planimetria.'); }
  resize(); buildRoom(); setCameraView(false); rebuildObstacles();
  (function loop() { requestAnimationFrame(loop); orbit.update(); renderer.render(scene3d, camera); }());
})();
