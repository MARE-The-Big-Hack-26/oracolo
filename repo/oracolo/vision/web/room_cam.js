export function camBasis(camInfo) {
  const dirRad = ((Number(camInfo.dir) || 0) * Math.PI) / 180;
  const pitchDeg = Number.isFinite(Number(camInfo.pitch)) ? Number(camInfo.pitch) : -28;
  const pitchRad = (pitchDeg * Math.PI) / 180;
  const cp = Math.cos(pitchRad), sp = Math.sin(pitchRad), cd = Math.cos(dirRad), sd = Math.sin(dirRad);
  const fwd = [cp * cd, sp, -cp * sd];
  const right = [sd, 0, cd];
  const up = [
    right[1] * fwd[2] - right[2] * fwd[1],
    right[2] * fwd[0] - right[0] * fwd[2],
    right[0] * fwd[1] - right[1] * fwd[0],
  ];
  return { dirRad, pitchDeg, pitchRad, fwd, right, up };
}

export function computeCamTarget(camInfo) {
  const [cx, cy] = camInfo.xy, ch = Math.max(0.1, Number(camInfo.h) || 1.8);
  const { dirRad, pitchRad } = camBasis(camInfo);
  if (pitchRad < -0.035) {
    const dist = Math.min(25, ch / Math.tan(-pitchRad));
    return { x: cx + Math.cos(dirRad) * dist, y: cy + Math.sin(dirRad) * dist, z: 0.02, dist };
  }
  const dist = 3.2;
  return { x: cx + Math.cos(dirRad) * dist, y: cy + Math.sin(dirRad) * dist, z: Math.max(0.02, ch + dist * Math.tan(pitchRad)), dist };
}

export function anglesFromTarget(camInfo, tx, ty, tz = 0) {
  const [cx, cy] = camInfo.xy, ch = Math.max(0.1, Number(camInfo.h) || 1.8);
  const dx = tx - cx, dy = ty - cy, dist = Math.hypot(dx, dy);
  const dir = Math.round((Math.atan2(dy, dx) * 180) / Math.PI);
  const pitch = Math.max(-85, Math.min(25, Math.round((Math.atan2(tz - ch, Math.max(dist, 0.08)) * 180) / Math.PI)));
  return { dir, pitch };
}

export function anglesFromViewDir(v) {
  const dir = Math.round((Math.atan2(-v.z, v.x) * 180) / Math.PI);
  const pitch = Math.max(-85, Math.min(25, Math.round((Math.asin(Math.max(-0.99, Math.min(0.99, v.y))) * 180) / Math.PI)));
  return { dir, pitch };
}

export function applyCameraPov(camera, orbit, camInfo, aspect) {
  const [x, y] = camInfo.xy, h = Math.max(0.1, Number(camInfo.h) || 1.8);
  const { fwd } = camBasis(camInfo);
  const hfov = (Math.min(145, Math.max(20, Number(camInfo.fov) || 75)) * Math.PI) / 180;
  const vfov = (2 * Math.atan(Math.tan(hfov / 2) / Math.max(0.3, aspect)) * 180) / Math.PI;
  camera.fov = Math.max(20, Math.min(120, vfov));
  camera.updateProjectionMatrix();
  camera.position.set(x, h, -y);
  orbit.target.set(x + fwd[0] * 2, h + fwd[1] * 2, -y + fwd[2] * 2);
  camera.lookAt(orbit.target);
}

export function bindCamFields($, rnd, getCam, onSync, onSave) {
  const els = ['cx', 'cy', 'ch', 'sch', 'cdir', 'scdir', 'cpitch', 'scpitch', 'cfov', 'scfov'].map($);
  const [cx, cy, ch, sch, cdir, scdir, cpitch, scpitch, cfov, scfov] = els;
  function sync() {
    const c = getCam();
    cx.value = rnd(c.xy[0]); cy.value = rnd(c.xy[1]); ch.value = rnd(c.h);
    sch.max = Math.max(3.5, Math.ceil(c.h)); sch.value = c.h;
    cdir.value = Math.round(c.dir); scdir.value = Math.round(c.dir);
    const p = Math.round(Number.isFinite(Number(c.pitch)) ? c.pitch : -28);
    if (cpitch) cpitch.value = p;
    if (scpitch) scpitch.value = p;
    cfov.value = Math.round(c.fov); scfov.value = Math.round(c.fov);
  }
  const onInput = (src) => () => {
    const c = getCam();
    const x = parseFloat(cx.value), y = parseFloat(cy.value), h = parseFloat(src === 's' ? sch.value : ch.value);
    const d = parseFloat(src === 'sd' ? scdir.value : cdir.value), p = parseFloat(src === 'sp' ? scpitch?.value : cpitch?.value), f = parseFloat(src === 'sf' ? scfov.value : cfov.value);
    if (Number.isFinite(x)) c.xy[0] = x; if (Number.isFinite(y)) c.xy[1] = y;
    if (Number.isFinite(h) && h >= 0.2) { c.h = h; if (src === 's') ch.value = rnd(h); else { sch.max = Math.max(3.5, Math.ceil(h)); sch.value = h; } }
    if (Number.isFinite(d)) { c.dir = ((Math.round(d) + 180) % 360 + 360) % 360 - 180; (src === 'sd' ? cdir : scdir).value = c.dir; }
    if (Number.isFinite(p)) { c.pitch = Math.max(-85, Math.min(25, Math.round(p))); if (cpitch && scpitch) (src === 'sp' ? cpitch : scpitch).value = c.pitch; }
    if (Number.isFinite(f)) { c.fov = Math.max(20, Math.min(360, Math.round(f))); (src === 'sf' ? cfov : scfov).value = c.fov; }
    onSync();
  };
  [cx, cy, ch].forEach((e) => e.addEventListener('input', onInput('n'))); sch.addEventListener('input', onInput('s'));
  cdir.addEventListener('input', onInput('d')); scdir.addEventListener('input', onInput('sd'));
  cpitch?.addEventListener('input', onInput('p')); scpitch?.addEventListener('input', onInput('sp'));
  cfov.addEventListener('input', onInput('f')); scfov.addEventListener('input', onInput('sf'));
  els.filter(Boolean).forEach((e) => e.addEventListener('change', onSave));
  return sync;
}

export function createSceneHelpers(THREE, ensureCCW) {
  function drawSprite(sp, l1, l2) {
    const c = sp.userData.canvas, ctx = c.getContext('2d');
    const f1 = 'bold 22px sans-serif', f2 = '17px sans-serif';
    ctx.font = f1; const w1 = ctx.measureText(l1 || '').width;
    ctx.font = f2; const w2 = l2 ? ctx.measureText(l2).width : 0;
    const targetW = Math.max(112, Math.ceil(Math.max(w1, w2) + 44)), targetH = l2 ? 76 : 46;
    if (c.width !== targetW || c.height !== targetH) {
      c.width = targetW; c.height = targetH;
      if (sp.material.map) sp.material.map.dispose();
      const tex = new THREE.CanvasTexture(c); tex.minFilter = THREE.LinearFilter; sp.material.map = tex;
    }
    ctx.clearRect(0, 0, c.width, c.height);
    ctx.fillStyle = 'rgba(15,17,21,0.90)'; ctx.strokeStyle = '#475569'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.roundRect(4, 4, c.width - 8, c.height - 8, 12); ctx.fill(); ctx.stroke();
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillStyle = '#f8fafc'; ctx.font = f1; ctx.fillText(l1 || '', c.width / 2, l2 ? 25 : c.height / 2);
    if (l2) { ctx.fillStyle = '#fde68a'; ctx.font = f2; ctx.fillText(l2, c.width / 2, 53); }
    sp.material.map.needsUpdate = true;
    const pxScale = sp.userData.pxScale ?? 0.0038;
    sp.scale.set(c.width * pxScale, c.height * pxScale, 1);
  }
  function makeSprite(l1, l2, scale = 1) {
    const c = document.createElement('canvas'), tex = new THREE.CanvasTexture(c);
    tex.minFilter = THREE.LinearFilter;
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false, depthWrite: false }));
    sp.renderOrder = 999; sp.userData.canvas = c; sp.userData.pxScale = 0.0038 * scale;
    drawSprite(sp, l1, l2); return sp;
  }
  const shapeOf = (pts) => { const sh = new THREE.Shape(); pts.forEach((p, i) => (i ? sh.lineTo(p[0], p[1]) : sh.moveTo(p[0], p[1]))); sh.closePath(); return sh; };
  const flatShape = (pts, mat, y) => { const m = new THREE.Mesh(new THREE.ShapeGeometry(shapeOf(pts)), mat); m.rotation.x = -Math.PI / 2; m.position.y = y; return m; };
  const makeObstacleGeo = (o) => { const g = new THREE.ExtrudeGeometry(shapeOf(ensureCCW(o.coords)), { depth: o.height, bevelEnabled: false }); g.rotateX(-Math.PI / 2); return g; };
  return { drawSprite, makeSprite, shapeOf, flatShape, makeObstacleGeo };
}

export function createCameraRig({ THREE, camGroup, shadowGroup, makeSprite, drawSprite, flatShape, OracoloGeom }) {
  const { rnd, computeFovWedges, computeShadows } = OracoloGeom;
  const stencil = { side: THREE.DoubleSide, depthWrite: false, stencilWrite: true, stencilRef: 1, stencilFunc: THREE.EqualStencilFunc };
  const shadowMats = {
    true: new THREE.MeshBasicMaterial({ color: '#cc3311', transparent: true, opacity: 0.44, ...stencil }),
    false: new THREE.MeshBasicMaterial({ color: '#e69f00', transparent: true, opacity: 0.36, ...stencil }),
  };
  const blindMat = new THREE.MeshBasicMaterial({ color: '#05070b', transparent: true, opacity: 0.58, ...stencil });
  const fovMat = new THREE.MeshBasicMaterial({ color: '#38bdf8', transparent: true, opacity: 0.16, ...stencil });
  const rayMat = new THREE.LineBasicMaterial({ color: '#fbbf24', transparent: true, opacity: 0.34 });
  const fovRayMat = new THREE.LineBasicMaterial({ color: '#38bdf8', transparent: true, opacity: 0.65 });

  const camSphere = new THREE.Mesh(new THREE.SphereGeometry(0.11, 16, 12), new THREE.MeshBasicMaterial({ color: '#60a5fa' }));
  camSphere.userData = { kind: 'cam' };

  const camStemGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3(0, 1, 0)]);
  const camStem = new THREE.Line(camStemGeo, new THREE.LineBasicMaterial({ color: '#60a5fa', transparent: true, opacity: 0.6 }));

  const camBase = new THREE.Mesh(new THREE.RingGeometry(0.08, 0.14, 20), new THREE.MeshBasicMaterial({ color: '#60a5fa', side: THREE.DoubleSide }));
  camBase.rotation.x = -Math.PI / 2; camBase.position.y = 0.012;

  // Blender-style camera frustum pyramid + up-triangle
  const frustumGeo = new THREE.BufferGeometry();
  const frustumMat = new THREE.LineBasicMaterial({ color: '#fbbf24' });
  const frustumLines = new THREE.LineSegments(frustumGeo, frustumMat);

  const upTriGeo = new THREE.BufferGeometry();
  const upTriMesh = new THREE.Mesh(upTriGeo, new THREE.MeshBasicMaterial({ color: '#fbbf24', transparent: true, opacity: 0.55, side: THREE.DoubleSide }));

  // Blender-style Yaw ring around camera + Pitch nose handle + Track-To target
  const camYawRing = new THREE.Mesh(
    new THREE.TorusGeometry(0.42, 0.022, 8, 40),
    new THREE.MeshBasicMaterial({ color: '#38bdf8', transparent: true, opacity: 0.72 }),
  );
  camYawRing.rotation.x = Math.PI / 2;
  camYawRing.userData = { kind: 'camYaw' };

  const camPitchHandle = new THREE.Mesh(
    new THREE.SphereGeometry(0.075, 14, 10),
    new THREE.MeshBasicMaterial({ color: '#f59e0b' }),
  );
  camPitchHandle.userData = { kind: 'camPitch' };

  const camTargetHandle = new THREE.Mesh(
    new THREE.SphereGeometry(0.10, 14, 10),
    new THREE.MeshBasicMaterial({ color: '#38bdf8' }),
  );
  camTargetHandle.userData = { kind: 'camDir' };

  const camTargetRing = new THREE.Mesh(
    new THREE.RingGeometry(0.14, 0.19, 24),
    new THREE.MeshBasicMaterial({ color: '#38bdf8', side: THREE.DoubleSide, transparent: true, opacity: 0.85 }),
  );
  camTargetRing.rotation.x = -Math.PI / 2;

  const camAimGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3(1, 0, 0)]);
  const camAimLine = new THREE.Line(camAimGeo, new THREE.LineBasicMaterial({ color: '#38bdf8', transparent: true, opacity: 0.7 }));

  const camLabel = makeSprite('Camera', 'H 1.8m', 1.1);
  camGroup.add(camSphere, camStem, camBase, frustumLines, upTriMesh, camYawRing, camPitchHandle, camTargetHandle, camTargetRing, camAimLine, camLabel);

  function syncShadows(bounds, obstacles, camInfo) {
    shadowGroup.traverse((c) => { if (c.geometry) c.geometry.dispose(); });
    shadowGroup.clear();
    const { fovPoly, blindPoly, fovRays } = computeFovWedges(bounds, camInfo);
    if (blindPoly.length >= 3) { const bm = flatShape(blindPoly, blindMat, 0.009); bm.renderOrder = 2; shadowGroup.add(bm); }
    if (fovPoly.length >= 3) { const fm = flatShape(fovPoly, fovMat, 0.009); fm.renderOrder = 2; shadowGroup.add(fm); }
    if (fovRays.length) {
      const fGeo = new THREE.BufferGeometry(); fGeo.setAttribute('position', new THREE.Float32BufferAttribute(fovRays, 3));
      const fl = new THREE.LineSegments(fGeo, fovRayMat); fl.renderOrder = 3; shadowGroup.add(fl);
    }
    const rays = [];
    computeShadows(bounds, obstacles, camInfo).forEach((sh) => {
      const mat = shadowMats[sh.blocked];
      [...sh.quads, sh.top].forEach((poly) => {
        if (poly.length < 3) return;
        const m = flatShape(poly, mat, 0.012); m.renderOrder = 3; shadowGroup.add(m);
      });
      if (sh.rays.length) rays.push(...sh.rays);
    });
    if (rays.length) {
      const rGeo = new THREE.BufferGeometry(); rGeo.setAttribute('position', new THREE.Float32BufferAttribute(rays, 3));
      const ls = new THREE.LineSegments(rGeo, rayMat); ls.renderOrder = 3; shadowGroup.add(ls);
    }
  }

  function syncCamVisual(bounds, obstacles, camInfo, selected = false) {
    const [x, y] = camInfo.xy, h = camInfo.h;
    const { pitchDeg, fwd, right, up } = camBasis(camInfo);
    const tgt = computeCamTarget(camInfo);

    camSphere.position.set(x, h, -y);
    camBase.position.set(x, 0.012, -y);
    camStemGeo.setFromPoints([new THREE.Vector3(x, 0, -y), new THREE.Vector3(x, h, -y)]);
    camYawRing.position.set(x, h, -y);
    camYawRing.material.opacity = selected ? 0.95 : 0.65;
    frustumMat.color.set(selected ? '#fde047' : '#fbbf24');

    // Frustum pyramid geometry
    const L = 0.56;
    const fovRad = (Math.min(145, Math.max(20, Number(camInfo.fov) || 75)) * Math.PI) / 180;
    const hw = L * Math.tan(fovRad / 2), hh = hw * (9 / 16);
    const pt = (df, dr, du) => [
      x + df * fwd[0] + dr * right[0] + du * up[0],
      h + df * fwd[1] + dr * right[1] + du * up[1],
      -y + df * fwd[2] + dr * right[2] + du * up[2],
    ];
    const p0 = [x, h, -y], tl = pt(L, -hw, hh), tr = pt(L, hw, hh), br = pt(L, hw, -hh), bl = pt(L, -hw, -hh);
    frustumGeo.setAttribute('position', new THREE.Float32BufferAttribute([
      ...p0, ...tl, ...p0, ...tr, ...p0, ...br, ...p0, ...bl,
      ...tl, ...tr, ...tr, ...br, ...br, ...bl, ...bl, ...tl,
    ], 3));

    const utL = pt(L, -hw * 0.55, hh + 0.04), utR = pt(L, hw * 0.55, hh + 0.04), utT = pt(L, 0, hh + 0.04 + hh * 0.55);
    upTriGeo.setAttribute('position', new THREE.Float32BufferAttribute([...utL, ...utR, ...utT], 3));
    upTriGeo.computeVertexNormals();

    const pNose = pt(L + 0.16, 0, 0);
    camPitchHandle.position.set(pNose[0], pNose[1], pNose[2]);
    camTargetHandle.position.set(tgt.x, tgt.z, -tgt.y);
    camTargetRing.position.set(tgt.x, 0.015, -tgt.y);
    camAimGeo.setFromPoints([new THREE.Vector3(x, h, -y), new THREE.Vector3(tgt.x, tgt.z, -tgt.y)]);

    camLabel.position.set(x, h + 0.34, -y);
    drawSprite(camLabel, 'Camera', `H ${rnd(h)}m · ${Math.round(camInfo.dir)}° · ${Math.round(pitchDeg)}°`);
    syncShadows(bounds, obstacles, camInfo);
  }

  return {
    camSphere, camDirHandle: camTargetHandle, camYawRing, camPitchHandle,
    syncShadows, syncCamVisual,
  };
}
