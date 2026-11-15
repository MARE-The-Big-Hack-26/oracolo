(() => {
  function sameWorld(a, b) {
    return Math.hypot((a[0] || 0) - b.x, (a[1] || 0) - b.y) < 0.025 && Math.abs((a[2] || 0) - b.z) < 0.025;
  }

  function hitVertex(overlay, px, py, rad, ovScale, worldPts, disabled) {
    if (disabled || !overlay || !Array.isArray(overlay.vertices)) return null;
    let best = null, bestD = rad;
    for (const v of overlay.vertices) {
      const d = Math.hypot(v.u * ovScale - px, v.v * ovScale - py);
      if (d < bestD) { bestD = d; best = v; }
    }
    if (!best) return null;
    const existingIdx = (worldPts || []).findIndex((w) => sameWorld(w, best));
    return { vertex: best, existingIdx };
  }

  function drawVertices(c, overlay, ovScale, hoverHit, dragging) {
    if (!overlay || !Array.isArray(overlay.vertices)) return;
    for (const v of overlay.vertices) {
      const x = v.u * ovScale, y = v.v * ovScale;
      const isTop = (v.z || 0) > 0.05;
      c.fillStyle = isTop ? 'rgba(56,189,248,0.85)' : 'rgba(245,158,11,0.85)';
      c.beginPath(); c.arc(x, y, 4.2, 0, Math.PI * 2); c.fill();
      c.strokeStyle = 'rgba(15,23,42,0.9)'; c.lineWidth = 1.5; c.stroke();
    }
    if (!hoverHit || dragging) return;
    const v = hoverHit.vertex, x = v.u * ovScale, y = v.v * ovScale;
    c.strokeStyle = '#38bdf8'; c.lineWidth = 2.5;
    c.beginPath(); c.arc(x, y, 10, 0, Math.PI * 2); c.stroke();
    const text = `Trascina: ${v.label}`;
    c.font = '600 13px sans-serif';
    const tw = c.measureText(text).width + 14;
    const tx = Math.min(Math.max(8, x + 12), c.canvas.width - tw - 8);
    const ty = Math.max(28, y - 12);
    c.fillStyle = 'rgba(15,23,42,0.92)';
    c.fillRect(tx, ty - 18, tw, 22);
    c.strokeStyle = '#38bdf8'; c.lineWidth = 1;
    c.strokeRect(tx, ty - 18, tw, 22);
    c.fillStyle = '#e0f2fe';
    c.fillText(text, tx + 7, ty - 3);
  }

  window.OracoloCadDrag = { hitVertex, drawVertices };
})();
