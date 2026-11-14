import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { createCameraRig, anglesFromTarget, anglesFromViewDir, applyCameraPov, bindCamFields, createSceneHelpers } from '/room_cam.js';

const { snap, rnd, polySpan, polyArea, ensureCCW, cleanRing, translatePoly, scalePolyTo, rotatePoly,
  insertVertexAt, longestEdgeIdx, removeVertexAt, extrudeEdge, defaultCamDir, cube, flashSave } = window.OracoloGeom;

const $ = (id) => document.getElementById(id), viewEl = $('view'), CACHE_KEY = 'oracolo_calib_cache';
const msg = (t) => { const el = $('msg'); el.className = ''; el.textContent = t; };
const cleanName = (s) => { const n = (s || '').replace(/#\d+$/, '').replace(/_H\d+(?:[.,]\d+)?$/i, '').toLowerCase(); return /^ostacolo_\d+$/.test(n) ? '' : n; };
const dispName = (o, i) => (o.name || '').trim() || `Cubo #${i + 1}`;
const fEl = { n: $('fn'), w: $('fw'), d: $('fd'), h: $('fh'), x: $('fx'), y: $('fy') };
const sEl = { w: $('sw'), d: $('sd'), h: $('sh') }, rwEl = $('rw'), rdEl = $('rd');
const renderer = new THREE.WebGLRenderer({ antialias: true, stencil: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2)); viewEl.appendChild(renderer.domElement);
const scene3d = new THREE.Scene(); scene3d.background = new THREE.Color('#090c12');
const camera = new THREE.PerspectiveCamera(46, 1, 0.05, 200), orbit = new OrbitControls(camera, renderer.domElement);
orbit.enableDamping = true; orbit.maxPolarAngle = Math.PI / 2 - 0.03;
scene3d.add(new THREE.AmbientLight('#ffffff', 0.9));
const sun = new THREE.DirectionalLight('#fff8eb', 1.15); sun.position.set(6, 12, 8); scene3d.add(sun);
const [roomGroup, shadowGroup, obsGroup, roomHandleGroup, handleGroup, camGroup] = Array.from({ length: 6 }, () => new THREE.Group());
scene3d.add(roomGroup, shadowGroup, obsGroup, roomHandleGroup, handleGroup, camGroup);
let bounds = [[0, 0], [5, 0], [5, 4], [0, 4]], obstacles = [], camInfo = { xy: [4.5, 1.1], h: 1.8, dir: 165, pitch: -28, fov: 75 }, fovPts = null;
let sel = -1, selCam = false, selObsVtx = -1, selObsEdge = -1, selRoomVtx = -1, entries = [], obsHandles = [], roomHandles = [], drag = null;
let viewMode = '3d', lastPtr = { x: 0, y: 0 }, undoStack = [], clearConfirm = false, clearT = null;
const hSphere = new THREE.SphereGeometry(0.10, 14, 10), mSphere = new THREE.SphereGeometry(0.08, 12, 8);

function pushHistory() {
  undoStack.push(JSON.stringify({ bounds, obstacles, camInfo }));
  if (undoStack.length > 20) undoStack.shift();
  const uBtn = $('undoRoom'); if (uBtn) uBtn.disabled = !undoStack.length;
}
function popHistory() {
  if (!undoStack.length) return;
  const st = JSON.parse(undoStack.pop());
  bounds = st.bounds; obstacles = st.obstacles; camInfo = st.camInfo;
  sel = -1; selObsVtx = -1; selObsEdge = -1; selRoomVtx = -1;
  const uBtn = $('undoRoom'); if (uBtn) uBtn.disabled = !undoStack.length;
  buildRoom(); syncCamVisual(); syncCamFields(); rebuildObstacles();
  saveScene(uBtn, 'Annullamento ripristinato');
}

const { drawSprite, makeSprite, flatShape, makeObstacleGeo } = createSceneHelpers(THREE, ensureCCW);
function setCameraView(mode = '3d') {
  viewMode = mode === true ? 'top' : (mode === false ? '3d' : mode);
  if (viewMode === 'cam') {
    camGroup.visible = false; orbit.enabled = false;
    applyCameraPov(camera, orbit, camInfo, (viewEl.clientWidth || 1) / (viewEl.clientHeight || 1));
  } else {
    camGroup.visible = true; orbit.enabled = true; camera.fov = 46; camera.updateProjectionMatrix();
    const b = polySpan(bounds), span = Math.max(b.w, b.d, 3), top = viewMode === 'top';
    orbit.target.set(b.cx, 0.35, -b.cy);
    camera.position.set(b.cx + (top ? 0 : span * 0.72), top ? span * 1.45 : span * 0.88, -b.cy + (top ? 0.01 : span * 0.98));
    orbit.update();
  }
  $('v3d')?.classList.toggle('active', viewMode === '3d');
  $('vTop')?.classList.toggle('active', viewMode === 'top');
  $('vCam')?.classList.toggle('active', viewMode === 'cam');
  $('toggleCamView')?.classList.toggle('act', viewMode === 'cam');
}
function addRingHandles(group, pts, y, selVtxIdx, selEdgeIdx, vCol, mCol, vKind, mKind) {
  const out = [];
  pts.forEach((p, idx) => {
    const vh = new THREE.Mesh(hSphere, new THREE.MeshBasicMaterial({ color: idx === selVtxIdx ? '#fbbf24' : vCol }));
    vh.position.set(p[0], y, -p[1]); vh.userData = { kind: vKind, idx };
    const q = pts[(idx + 1) % pts.length], mh = new THREE.Mesh(mSphere, new THREE.MeshBasicMaterial({ color: idx === selEdgeIdx ? '#fbbf24' : mCol }));
    mh.position.set((p[0] + q[0]) / 2, y, -(p[1] + q[1]) / 2); mh.userData = { kind: mKind, idx };
    group.add(vh, mh); out.push(vh, mh);
  });
  return out;
}
const syncRoomHandles = () => { roomHandleGroup.clear(); roomHandles = addRingHandles(roomHandleGroup, bounds, 0.08, selRoomVtx, -1, '#f8fafc', '#818cf8', 'rVtx', 'rMid'); };
const syncRoomFields = () => { const b = polySpan(bounds); rwEl.value = rnd(b.w); rdEl.value = rnd(b.d); $('rvCnt').textContent = bounds.length; $('delRoomVtx').disabled = !(bounds.length > 3 && selRoomVtx >= 0); };

const camRig = createCameraRig({ THREE, camGroup, shadowGroup, makeSprite, drawSprite, flatShape, OracoloGeom: window.OracoloGeom });
const syncShadows = () => camRig.syncShadows(bounds, obstacles, camInfo);
const syncCamVisual = () => {
  camRig.syncCamVisual(bounds, obstacles, camInfo, selCam);
  if (viewMode === 'cam') applyCameraPov(camera, orbit, camInfo, (viewEl.clientWidth || 1) / (viewEl.clientHeight || 1));
};
function buildRoom() {
  roomGroup.traverse((c) => { if (c.geometry) c.geometry.dispose(); }); roomGroup.clear();
  const b = polySpan(bounds), gx0 = Math.floor(b.minx) - 1, gx1 = Math.ceil(b.maxx) + 1, gy0 = Math.floor(b.miny) - 1, gy1 = Math.ceil(b.maxy) + 1, gPts = [];
  for (let x = gx0; x <= gx1 + 1e-6; x += 0.5) gPts.push(x, 0, -gy0, x, 0, -gy1);
  for (let y = gy0; y <= gy1 + 1e-6; y += 0.5) gPts.push(gx0, 0, -y, gx1, 0, -y);
  const gGeo = new THREE.BufferGeometry(); gGeo.setAttribute('position', new THREE.Float32BufferAttribute(gPts, 3));
  const floorMat = new THREE.MeshStandardMaterial({ color: '#141b29', roughness: 0.9, side: THREE.DoubleSide, stencilWrite: true, stencilRef: 1, stencilFunc: THREE.AlwaysStencilFunc, stencilZPass: THREE.ReplaceStencilOp, stencilFail: THREE.KeepStencilOp, stencilZFail: THREE.KeepStencilOp });
  const floor = flatShape(bounds, floorMat, 0.002); floor.renderOrder = 1;
  roomGroup.add(new THREE.LineSegments(gGeo, new THREE.LineBasicMaterial({ color: '#1f293d' })), floor);
  const sgn = polyArea(bounds) >= 0 ? 1 : -1, wallH = 2.4, wallMat = new THREE.MeshStandardMaterial({ color: '#263248', roughness: 0.95, side: THREE.FrontSide });
  bounds.forEach((p, i) => {
    const q = bounds[(i + 1) % bounds.length], dx = q[0] - p[0], dy = q[1] - p[1], len = Math.hypot(dx, dy);
    if (len < 0.05) return;
    const wall = new THREE.Mesh(new THREE.PlaneGeometry(len, wallH), wallMat);
    wall.position.set((p[0] + q[0]) / 2, wallH / 2, -(p[1] + q[1]) / 2); wall.rotation.y = Math.atan2(-dy * sgn, -dx * sgn);
    const lbl = makeSprite(`${len.toFixed(2)} m`, '', 0.85); lbl.position.set(wall.position.x, 0.16, wall.position.z); roomGroup.add(wall, lbl);
  });
  roomGroup.add(new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(bounds.map((p) => new THREE.Vector3(p[0], 0.008, -p[1]))), new THREE.LineBasicMaterial({ color: '#cbd5e1' })));
  if (fovPts && fovPts.length >= 3) { const f = flatShape(fovPts, new THREE.MeshBasicMaterial({ color: '#56b4e9', transparent: true, opacity: 0.16, side: THREE.DoubleSide, depthWrite: false }), 0.008); f.renderOrder = 1; roomGroup.add(f); }
  syncRoomHandles(); syncRoomFields(); syncShadows();
}
const syncCamFields = bindCamFields($, rnd, () => camInfo, syncCamVisual, () => saveScene(null, 'Misura salvata'));
function syncHandles() {
  handleGroup.clear(); obsHandles = [];
  if (sel < 0 || !obstacles[sel]) return;
  const o = obstacles[sel], s = polySpan(o.coords), top = new THREE.Mesh(hSphere, new THREE.MeshBasicMaterial({ color: '#34d399' }));
  top.position.set(s.cx, o.height, -s.cy); top.userData = { kind: 'oTop' }; handleGroup.add(top);
  obsHandles = [top, ...addRingHandles(handleGroup, o.coords, o.height / 2, selObsVtx, selObsEdge, '#38bdf8', '#c084fc', 'oVtx', 'oEdge')];
}
function placeObstacle(o, i, entry) {
  const geo = makeObstacleGeo(o), s = polySpan(o.coords);
  entry.mesh.geometry.dispose(); entry.mesh.geometry = geo; entry.edges.geometry.dispose(); entry.edges.geometry = new THREE.EdgesGeometry(geo);
  entry.label.position.set(s.cx, o.height + 0.25, -s.cy); drawSprite(entry.label, dispName(o, i), `${rnd(s.w)}x${rnd(s.d)} · H ${rnd(o.height)}m`);
}
function rebuildObstacles() {
  entries.forEach((e) => { e.mesh.geometry.dispose(); e.edges.geometry.dispose(); }); obsGroup.clear();
  entries = obstacles.map((o, i) => {
    const mesh = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshStandardMaterial({ color: i === sel ? '#ea580c' : '#9a3412', transparent: true, opacity: 0.90, roughness: 0.6, side: THREE.DoubleSide }));
    mesh.renderOrder = 2; const edges = new THREE.LineSegments(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ color: i === sel ? '#93c5fd' : '#fbbf24' }));
    mesh.add(edges); mesh.userData.idx = i; const entry = { mesh, edges, label: makeSprite('', '') };
    placeObstacle(o, i, entry); obsGroup.add(mesh, entry.label); return entry;
  });
  syncHandles(); syncInspector(); syncShadows();
}
function updateSelectedVisual() { if (sel >= 0 && entries[sel]) { placeObstacle(obstacles[sel], sel, entries[sel]); syncHandles(); syncShadows(); } }
function select(i) {
  sel = i; if (i >= 0) selCam = false; selObsVtx = -1; selObsEdge = -1;
  entries.forEach((e, k) => { e.mesh.material.color.set(k === sel ? '#ea580c' : '#9a3412'); e.edges.material.color.set(k === sel ? '#93c5fd' : '#fbbf24'); });
  syncHandles(); syncInspector(); syncCamVisual();
  if (i >= 0) window.OracoloUI?.setTab?.('obs');
}
function syncList() {
  $('cnt').textContent = obstacles.length; const list = $('olist'); list.innerHTML = '';
  obstacles.forEach((ob, i) => {
    const s = polySpan(ob.coords), div = document.createElement('div'), info = document.createElement('div'), b = document.createElement('b'), sm = document.createElement('small'), del = document.createElement('button');
    div.className = 'item' + (i === sel ? ' sel' : ''); b.textContent = dispName(ob, i); sm.textContent = `${rnd(s.w)} x ${rnd(s.d)} m · ${ob.coords.length} vert. · H ${rnd(ob.height)} m`;
    del.textContent = 'Elimina'; del.type = 'button'; del.onclick = (e) => { e.stopPropagation(); pushHistory(); obstacles.splice(i, 1); if (sel === i) sel = -1; else if (sel > i) sel--; rebuildObstacles(); saveScene(null, 'Oggetto eliminato'); };
    info.append(b, sm); div.append(info, del); div.onclick = () => select(i); list.appendChild(div);
  });
}
function syncFields() {
  const o = obstacles[sel]; $('none').style.display = o ? 'none' : 'block'; $('form').style.display = o ? 'block' : 'none';
  $('dupCube').disabled = !o;
  if (!o) return;
  const s = polySpan(o.coords);
  fEl.n.value = o.name; fEl.w.value = rnd(s.w); fEl.d.value = rnd(s.d); fEl.h.value = rnd(o.height); fEl.x.value = rnd(s.minx); fEl.y.value = rnd(s.miny);
  $('delVtx').disabled = o.coords.length <= 3;
  [['w', 5, s.w], ['d', 5, s.d], ['h', 3.5, o.height]].forEach(([k, m, v]) => { sEl[k].max = Math.max(m, Math.ceil(v)); sEl[k].value = v; });
}
const syncInspector = () => { syncFields(); syncList(); };
const ray = new THREE.Raycaster(), ptr = new THREE.Vector2(), hitPt = new THREE.Vector3(), UP = new THREE.Vector3(0, 1, 0), floorPlane = new THREE.Plane(UP, 0);
const yPlane = (y) => new THREE.Plane(UP, -y), snapHit = () => [rnd(snap(hitPt.x)), rnd(snap(-hitPt.z))];
const beginDrag = (d) => { pushHistory(); drag = d; orbit.enabled = false; renderer.domElement.style.cursor = 'grabbing'; };
const dragObs = (ud, plane) => { const o = obstacles[sel]; ray.ray.intersectPlane(plane, hitPt); return beginDrag({ ...ud, plane, start: [hitPt.x, -hitPt.z], orig: o.coords.map((p) => [...p]) }); };
const setPtr = (e) => { const r = renderer.domElement.getBoundingClientRect(); ptr.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1); ray.setFromCamera(ptr, camera); };

renderer.domElement.addEventListener('pointerdown', (e) => {
  if (drag?.kind === 'camModal') { if (e.button === 2) { camInfo.dir = drag.origDir; camInfo.pitch = drag.origPitch; syncCamVisual(); syncCamFields(); } drag = null; orbit.enabled = viewMode !== 'cam'; renderer.domElement.style.cursor = 'default'; if (e.button === 0) saveScene(null, 'Camera orientata'); return; }
  if (e.button !== 0) return;
  if (viewMode === 'cam') { pushHistory(); drag = { kind: 'camPov', x: e.clientX, y: e.clientY, origDir: camInfo.dir, origPitch: camInfo.pitch }; renderer.domElement.style.cursor = 'grabbing'; return; }
  setPtr(e);
  const rh = ray.intersectObjects(roomHandles, false);
  if (rh.length) { const ud = rh[0].object.userData; window.OracoloUI?.setTab?.('room'); if (ud.kind === 'rMid') { bounds = insertVertexAt(bounds, ud.idx); buildRoom(); selRoomVtx = ud.idx + 1; } else { selRoomVtx = ud.idx; syncRoomHandles(); syncRoomFields(); } return beginDrag({ kind: 'rVtx', idx: selRoomVtx, plane: floorPlane }); }
  const hh = obsHandles.length ? ray.intersectObjects(obsHandles, false) : [];
  if (hh.length) {
    const ud = hh[0].object.userData, fwd = new THREE.Vector3(); camera.getWorldDirection(fwd); fwd.y = 0; fwd.normalize();
    if (ud.kind === 'oVtx') { selObsVtx = ud.idx; selObsEdge = -1; syncHandles(); }
    else if (ud.kind === 'oEdge') { selObsEdge = ud.idx; selObsVtx = -1; syncHandles(); }
    return dragObs(ud, ud.kind === 'oTop' ? new THREE.Plane().setFromNormalAndCoplanarPoint(fwd, hh[0].point) : yPlane(obstacles[sel].height / 2));
  }
  const selectCam = () => { selCam = true; select(-1); window.OracoloUI?.setTab?.('cam'); };
  if (ray.intersectObject(camRig.camPitchHandle, false).length) { selectCam(); return beginDrag({ kind: 'camPitch', y: e.clientY, origPitch: camInfo.pitch }); }
  if (ray.intersectObject(camRig.camYawRing, false).length) { selectCam(); return beginDrag({ kind: 'camYaw', plane: yPlane(camInfo.h) }); }
  if (ray.intersectObject(camRig.camDirHandle, false).length) { selectCam(); return beginDrag({ kind: 'camDir', plane: floorPlane }); }
  if (ray.intersectObject(camRig.camSphere, false).length) { selectCam(); const plane = yPlane(camInfo.h); ray.ray.intersectPlane(plane, hitPt); return beginDrag({ kind: 'cam', plane, dx: hitPt.x - camInfo.xy[0], dy: -hitPt.z - camInfo.xy[1] }); }
  const mh = ray.intersectObjects(entries.map((x) => x.mesh), false);
  if (!mh.length) { drag = { kind: 'orbit', x: e.clientX, y: e.clientY }; return; }
  select(mh[0].object.userData.idx); dragObs({ kind: 'move' }, yPlane(obstacles[sel].height / 2));
});
window.addEventListener('pointermove', (e) => {
  lastPtr = { x: e.clientX, y: e.clientY }; setPtr(e);
  if (!drag) {
    if (viewMode === 'cam') { renderer.domElement.style.cursor = 'grab'; return; }
    const overH = ray.intersectObjects([...roomHandles, ...obsHandles, camRig.camDirHandle, camRig.camYawRing, camRig.camPitchHandle], false).length;
    const overG = ray.intersectObject(camRig.camSphere, false).length || ray.intersectObjects(entries.map((x) => x.mesh), false).length;
    renderer.domElement.style.cursor = overH ? 'pointer' : (overG ? 'grab' : 'default'); return;
  }
  if (drag.kind === 'camPitch') { camInfo.pitch = Math.max(-85, Math.min(25, Math.round(drag.origPitch - (e.clientY - drag.y) * 0.35))); syncCamVisual(); syncCamFields(); return; }
  if (drag.kind === 'camPov' || drag.kind === 'camModal') {
    camInfo.dir = ((Math.round(drag.origDir - (e.clientX - drag.x) * 0.35) + 180) % 360 + 360) % 360 - 180;
    camInfo.pitch = Math.max(-85, Math.min(25, Math.round(drag.origPitch - (e.clientY - drag.y) * 0.3)));
    syncCamVisual(); syncCamFields(); return;
  }
  if (drag.kind === 'orbit' || !ray.ray.intersectPlane(drag.plane, hitPt)) return;
  if (drag.kind === 'camDir') { const a = anglesFromTarget(camInfo, hitPt.x, -hitPt.z, 0); camInfo.dir = a.dir; camInfo.pitch = a.pitch; syncCamVisual(); syncCamFields(); return; }
  if (drag.kind === 'camYaw') { camInfo.dir = Math.round((Math.atan2(-hitPt.z - camInfo.xy[1], hitPt.x - camInfo.xy[0]) * 180) / Math.PI); syncCamVisual(); syncCamFields(); return; }
  if (drag.kind === 'cam') { camInfo.xy = [rnd(snap(hitPt.x - drag.dx)), rnd(snap(-hitPt.z - drag.dy))]; syncCamVisual(); syncCamFields(); return; }
  if (drag.kind === 'rVtx') { bounds[drag.idx] = snapHit(); buildRoom(); return; }
  const o = obstacles[sel]; if (!o) return;
  if (drag.kind === 'move') o.coords = translatePoly(drag.orig, snap(hitPt.x - drag.start[0]), snap(-hitPt.z - drag.start[1]));
  else if (drag.kind === 'oVtx') o.coords[drag.idx] = snapHit();
  else if (drag.kind === 'oEdge') { const dx = snap(hitPt.x - drag.start[0]), dy = snap(-hitPt.z - drag.start[1]), j = (drag.idx + 1) % o.coords.length; o.coords[drag.idx] = [rnd(drag.orig[drag.idx][0] + dx), rnd(drag.orig[drag.idx][1] + dy)]; o.coords[j] = [rnd(drag.orig[j][0] + dx), rnd(drag.orig[j][1] + dy)]; }
  else if (drag.kind === 'oTop') o.height = rnd(Math.max(0.1, snap(hitPt.y)));
  updateSelectedVisual(); syncFields();
});
window.addEventListener('pointerup', (e) => {
  if (!drag || drag.kind === 'camModal') return;
  const d = drag; drag = null; orbit.enabled = viewMode !== 'cam'; renderer.domElement.style.cursor = viewMode === 'cam' ? 'grab' : 'default';
  if (d.kind === 'orbit') { if (Math.hypot(e.clientX - d.x, e.clientY - d.y) < 5) { selCam = false; select(-1); selRoomVtx = -1; syncRoomHandles(); syncRoomFields(); } return; }
  if (d.kind === 'rVtx') { bounds = ensureCCW(bounds); buildRoom(); } else if (!d.kind.startsWith('cam')) syncList();
  saveScene(null, 'Posizione salvata');
});
function applyObsDim(k, v, fromSlider) {
  const o = obstacles[sel]; if (!o || !Number.isFinite(v)) return; const s = polySpan(o.coords);
  if (k === 'w' || k === 'd') o.coords = scalePolyTo(o.coords, k === 'w' ? Math.max(0.1, v) : s.w, k === 'd' ? Math.max(0.1, v) : s.d);
  else if (k === 'x' || k === 'y') o.coords = translatePoly(o.coords, k === 'x' ? v - s.minx : 0, k === 'y' ? v - s.miny : 0);
  else if (k === 'h') o.height = Math.max(0.1, v);
  if (fromSlider) fEl[k].value = rnd(v); else if (sEl[k]) { sEl[k].max = Math.max(parseFloat(sEl[k].max), v); sEl[k].value = v; }
  updateSelectedVisual(); syncList();
}
Object.entries(fEl).forEach(([k, el]) => el.addEventListener('input', () => { if (k === 'n') { if (obstacles[sel]) { obstacles[sel].name = el.value; updateSelectedVisual(); syncList(); } } else applyObsDim(k, parseFloat(el.value), false); }));
Object.entries(sEl).forEach(([k, el]) => el.addEventListener('input', () => applyObsDim(k, parseFloat(el.value), true)));
const scaleRoom = () => { const w = parseFloat(rwEl.value), d = parseFloat(rdEl.value); if (w > 0 && d > 0) { bounds = scalePolyTo(bounds, w, d); buildRoom(); } };
rwEl.addEventListener('input', scaleRoom); rdEl.addEventListener('input', scaleRoom);
[...Object.values(fEl), ...Object.values(sEl), rwEl, rdEl].forEach((el) => el.addEventListener('change', () => saveScene(null, 'Misura salvata')));
const spawnCenter = () => { const b = polySpan(bounds), off = (obstacles.length % 4) * 0.15 - 0.2; return [snap(b.cx + off), snap(b.cy + off)]; };
const addCube = (focusName = true) => { pushHistory(); const [x, y] = spawnCenter(); obstacles.push({ name: '', coords: cube(x, y, 1, 1), height: 1.0 }); sel = obstacles.length - 1; selObsVtx = -1; selObsEdge = -1; rebuildObstacles(); if (focusName) fEl.n.focus(); saveScene($('addCube'), 'Cubo aggiunto'); };
const dupCube = () => { const o = obstacles[sel]; if (!o) return; pushHistory(); obstacles.push({ name: o.name ? o.name + '_copia' : '', coords: translatePoly(o.coords, 0.25, 0.25), height: o.height }); sel = obstacles.length - 1; selObsVtx = -1; selObsEdge = -1; rebuildObstacles(); saveScene($('dupCube'), 'Cubo duplicato'); };
const subdivEdge = () => { const o = obstacles[sel]; if (!o) return; pushHistory(); const idx = selObsEdge >= 0 ? selObsEdge : longestEdgeIdx(o.coords); o.coords = insertVertexAt(o.coords, idx); selObsEdge = idx; selObsVtx = -1; updateSelectedVisual(); syncInspector(); saveScene($('subdivEdge'), 'Faccia suddivisa'); };
const extrudeSelEdge = () => { const o = obstacles[sel]; if (!o) return; pushHistory(); const idx = selObsEdge >= 0 ? selObsEdge : longestEdgeIdx(o.coords); o.coords = extrudeEdge(o.coords, idx, 0.5); selObsEdge = idx + 1; selObsVtx = -1; updateSelectedVisual(); syncInspector(); saveScene($('extrudeEdge'), 'Faccia estrusa'); };
const modSelObs = (id, fn) => () => { const o = obstacles[sel]; if (o) { pushHistory(); o.coords = fn(o.coords); updateSelectedVisual(); syncInspector(); saveScene($(id), 'Modifica salvata'); } };
const delSelVtx = () => { const o = obstacles[sel]; if (o && o.coords.length > 3) { pushHistory(); o.coords = removeVertexAt(o.coords, selObsVtx >= 0 ? selObsVtx : o.coords.length - 1); selObsVtx = -1; selObsEdge = -1; updateSelectedVisual(); syncInspector(); saveScene($('delVtx'), 'Vertice dissolto'); } };
const delSelObs = () => { if (sel >= 0) { pushHistory(); obstacles.splice(sel, 1); sel = -1; rebuildObstacles(); saveScene($('del'), 'Cubo eliminato'); } };
const clearBtn = $('clearobs');
const alignCamToView = () => { pushHistory(); const v = new THREE.Vector3(); camera.getWorldDirection(v); const a = anglesFromViewDir(v); camInfo.dir = a.dir; camInfo.pitch = a.pitch; syncCamVisual(); syncCamFields(); saveScene($('alignCam'), 'Camera allineata alla vista'); };
Object.entries({
  addCube: () => addCube(true), dupCube, subdivEdge, extrudeEdge: extrudeSelEdge,
  v3d: () => setCameraView('3d'), vTop: () => setCameraView('top'), vCam: () => setCameraView('cam'),
  toggleCamView: () => setCameraView(viewMode === 'cam' ? '3d' : 'cam'), alignCam: alignCamToView,
  undoRoom: popHistory,
  clearobs: () => {
    if (!clearConfirm) { clearConfirm = true; clearBtn.classList.add('dan'); clearBtn.textContent = 'Conferma svuota?'; clearTimeout(clearT); clearT = setTimeout(() => { clearConfirm = false; clearBtn.classList.remove('dan'); clearBtn.textContent = 'Svuota'; }, 3000); return; }
    clearConfirm = false; clearBtn.classList.remove('dan'); clearBtn.textContent = 'Svuota'; pushHistory(); obstacles = []; sel = -1; rebuildObstacles(); saveScene(clearBtn, 'Stanza svuotata');
  },
  delRoomVtx: () => { if (selRoomVtx >= 0 && bounds.length > 3) { pushHistory(); bounds = removeVertexAt(bounds, selRoomVtx); selRoomVtx = -1; buildRoom(); saveScene($('delRoomVtx'), 'Modifica salvata'); } },
  rot15: modSelObs('rot15', (c) => rotatePoly(c, 15)), rot: modSelObs('rot', (c) => rotatePoly(c, 90)),
  delVtx: delSelVtx, del: delSelObs, save: () => saveScene($('save')), saveCam: () => saveScene($('saveCam'), 'Camera e planimetria salvate'),
}).forEach(([id, fn]) => { if ($(id)) $(id).onclick = fn; });
window.addEventListener('keydown', (e) => {
  if (['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement?.tagName)) return;
  const k = e.key.toLowerCase();
  if ((e.ctrlKey || e.metaKey) && k === 'z') { e.preventDefault(); popHistory(); return; }
  if (e.ctrlKey || e.metaKey) return;
  if (k === '0') { e.preventDefault(); setCameraView(viewMode === 'cam' ? '3d' : 'cam'); }
  else if (k === 'escape') {
    if (drag?.kind === 'camModal') { camInfo.dir = drag.origDir; camInfo.pitch = drag.origPitch; drag = null; orbit.enabled = viewMode !== 'cam'; renderer.domElement.style.cursor = 'default'; syncCamVisual(); syncCamFields(); }
    else if (viewMode === 'cam') setCameraView('3d');
  } else if (k === 'enter' && drag?.kind === 'camModal') { drag = null; orbit.enabled = viewMode !== 'cam'; renderer.domElement.style.cursor = 'default'; saveScene(null, 'Camera orientata'); }
  else if (e.shiftKey && k === 'a') { e.preventDefault(); addCube(false); }
  else if (e.shiftKey && k === 'd') { e.preventDefault(); dupCube(); }
  else if (k === 'k') { e.preventDefault(); subdivEdge(); }
  else if (k === 'e') { e.preventDefault(); extrudeSelEdge(); }
  else if (k === 'r') {
    e.preventDefault();
    if (sel >= 0 && obstacles[sel]) modSelObs(e.shiftKey ? 'rot' : 'rot15', (c) => rotatePoly(c, e.shiftKey ? 90 : 15))();
    else { pushHistory(); drag = { kind: 'camModal', x: lastPtr.x, y: lastPtr.y, origDir: camInfo.dir, origPitch: camInfo.pitch }; orbit.enabled = false; renderer.domElement.style.cursor = 'move'; msg('Rotazione camera: muovi il mouse, clicca per confermare o Esc per annullare.'); }
  } else if (e.key === 'Delete' || e.key === 'Backspace' || k === 'x') { e.preventDefault(); if (sel >= 0 && obstacles[sel]) (selObsVtx >= 0 && obstacles[sel].coords.length > 3 ? delSelVtx : delSelObs)(); }
});
async function saveScene(btn, label = 'Planimetria salvata') {
  if (btn && btn.tagName === 'BUTTON') { if (!btn.dataset.orig && btn.textContent !== 'Salvataggio in corso...') btn.dataset.orig = btn.textContent; btn.textContent = 'Salvataggio in corso...'; }
  try {
    const j = await (await fetch('/scene', { method: 'POST', body: JSON.stringify({ bounds: ensureCCW(bounds), obstacles: obstacles.map((o) => ({ name: o.name, coords: ensureCCW(o.coords), height: o.height })), cam: camInfo }) })).json();
    try { const c = JSON.parse(localStorage.getItem(CACHE_KEY) || '{}') || {}; c.cam_xy = camInfo.xy; c.cam_h = camInfo.h; c.cam_pitch = camInfo.pitch; localStorage.setItem(CACHE_KEY, JSON.stringify(c)); } catch {}
    if (j.fov !== undefined) { fovPts = j.fov; buildRoom(); }
    flashSave(btn, j.ok ? `${label} (${j.occluders} oggetti · Camera ${rnd(camInfo.xy[0])}, ${rnd(camInfo.xy[1])} m · H ${rnd(camInfo.h)} m)` : `Errore: ${j.error}`, !j.ok);
  } catch (e) { flashSave(btn, `Errore di rete: ${e}`, true); }
}
const resize = () => { const w = viewEl.clientWidth || 1, h = viewEl.clientHeight || 1; camera.aspect = w / h; camera.updateProjectionMatrix(); renderer.setSize(w, h, false); };
window.addEventListener('resize', resize);
(async () => {
  try {
    const sc = await (await fetch('/scene')).json();
    if (sc.bounds && sc.bounds.length >= 3) bounds = cleanRing(sc.bounds);
    if (sc.cam && Array.isArray(sc.cam.xy)) camInfo = { xy: [rnd(sc.cam.xy[0]), rnd(sc.cam.xy[1])], h: rnd(sc.cam.h || 1.8), dir: Number.isFinite(Number(sc.cam.dir)) ? Math.round(sc.cam.dir) : defaultCamDir(bounds, sc.cam.xy), pitch: Number.isFinite(Number(sc.cam.pitch)) ? Math.round(sc.cam.pitch) : -28, fov: Number.isFinite(Number(sc.cam.fov)) ? Math.round(sc.cam.fov) : 75 };
    else camInfo.dir = defaultCamDir(bounds, camInfo.xy);
    try { const c = JSON.parse(localStorage.getItem(CACHE_KEY) || '{}'); if (!sc.calibrated && Array.isArray(c.cam_xy)) camInfo = { ...camInfo, xy: [rnd(c.cam_xy[0]), rnd(c.cam_xy[1])], h: rnd(c.cam_h || camInfo.h) }; if (Number.isFinite(Number(c.cam_pitch))) camInfo.pitch = Math.round(c.cam_pitch); } catch {}
    fovPts = sc.fov || null;
    obstacles = (sc.occluders || []).map((o) => { const pts = cleanRing(o.coords); return { name: cleanName(o.name), coords: pts.length >= 3 ? pts : cube(1, 1), height: rnd(o.height || 1.8) }; });
    msg('Pronto: premi Shift+A per aggiungere un cubo, K per suddividere una faccia, E per estrudere, Ctrl+Z per annullare.');
  } catch (e) { msg('Errore nel caricamento della planimetria.'); }
  resize(); buildRoom(); syncCamVisual(); syncCamFields(); setCameraView(false); rebuildObstacles();
  (function loop() { requestAnimationFrame(loop); orbit.update(); renderer.render(scene3d, camera); }());
})();
