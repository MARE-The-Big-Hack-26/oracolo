import { shapeWaves } from "./waves.js";

const wavesEl = document.getElementById("waves");
if (wavesEl) shapeWaves(wavesEl);

document.querySelectorAll(".btn-primary").forEach((el) => {
  el.addEventListener("mousemove", (e) => {
    const r = el.getBoundingClientRect();
    el.style.setProperty("--mx", `${Math.round(e.clientX - r.left)}px`);
    el.style.setProperty("--my", `${Math.round(e.clientY - r.top)}px`);
    el.classList.add("is-tracking");
  }, { passive: true });
  el.addEventListener("mouseleave", () => {
    el.classList.remove("is-tracking");
    el.style.removeProperty("--mx");
    el.style.removeProperty("--my");
  }, { passive: true });
});

const COMMANDS = {
  unix: "git clone https://github.com/MARE-The-Big-Hack-26/oracolo.git && cd oracolo/repo && pip install -r requirements.txt && make live",
  windows: "git clone https://github.com/MARE-The-Big-Hack-26/oracolo.git && cd oracolo\\repo && pip install -r requirements.txt && python scripts/run_live.py --loop"
};

const cmdEl = document.getElementById("cli-cmd");
const copyBtn = document.getElementById("copy-cmd");

document.querySelectorAll(".os-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".os-tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    if (cmdEl && COMMANDS[tab.dataset.os]) cmdEl.textContent = COMMANDS[tab.dataset.os];
  });
});

if (copyBtn && cmdEl) {
  copyBtn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(cmdEl.textContent || "");
      copyBtn.textContent = "Copied";
      setTimeout(() => { copyBtn.textContent = "Copy"; }, 1600);
    } catch { copyBtn.textContent = "Copy manually"; }
  });
}

const canvas = document.getElementById("radar-canvas");
const ctx = canvas?.getContext("2d");
const lvlEl = document.getElementById("tele-level");
const spdEl = document.getElementById("tele-speed");
const stEl = document.getElementById("tele-state");

let cams = 1;
let ped = { x: 145, y: 95 };
const racks = [
  { x: 60, y: 36, w: 120, h: 78 },
  { x: 60, y: 186, w: 120, h: 78 },
  { x: 280, y: 186, w: 150, h: 78 }
];

function drawRadar() {
  if (!ctx || !canvas) return;
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  ctx.fillStyle = "#0b100e";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // Camera visibility cones
  ctx.fillStyle = "rgba(46, 204, 113, 0.14)";
  ctx.beginPath();
  ctx.moveTo(470, 42);
  ctx.lineTo(180, 36);
  ctx.lineTo(180, 264);
  ctx.lineTo(470, 186);
  ctx.closePath();
  ctx.fill();

  if (cams === 2) {
    ctx.beginPath();
    ctx.moveTo(230, 24);
    ctx.lineTo(40, 115);
    ctx.lineTo(40, 185);
    ctx.lineTo(270, 185);
    ctx.closePath();
    ctx.fill();
  } else {
    // Blind spot shadow behind upper rack when only 1 cam
    ctx.fillStyle = "rgba(245, 158, 11, 0.16)";
    ctx.fillRect(40, 36, 140, 148);
  }

  // Racks
  ctx.fillStyle = "#1c2421";
  ctx.strokeStyle = "#33413b";
  racks.forEach((r) => {
    ctx.fillRect(r.x, r.y, r.w, r.h);
    ctx.strokeRect(r.x, r.y, r.w, r.h);
  });

  // Forklift
  ctx.fillStyle = "#2ecc71";
  ctx.fillRect(250, 134, 38, 24);

  // Pedestrian
  const occluded = cams === 1 && ped.x < 185;
  ctx.fillStyle = occluded ? "#f59e0b" : "#f4f6f5";
  ctx.beginPath();
  ctx.arc(ped.x, ped.y, 8, 0, Math.PI * 2);
  ctx.fill();

  // Cameras
  ctx.fillStyle = "#2ecc71";
  ctx.beginPath();
  ctx.arc(470, 42, 6, 0, Math.PI * 2);
  ctx.fill();
  if (cams === 2) {
    ctx.beginPath();
    ctx.arc(230, 24, 6, 0, Math.PI * 2);
    ctx.fill();
  }

  const dist = Math.hypot(ped.x - 269, ped.y - 146);
  if (dist < 75) {
    lvlEl.textContent = "03 FERMA";
    lvlEl.className = "tele-val status-stop";
    spdEl.textContent = "0.0 m/s";
    stEl.textContent = occluded ? "Occluded · Close" : "Visible · Close";
  } else if (occluded) {
    lvlEl.textContent = "02 RALLENTA";
    lvlEl.className = "tele-val status-warn";
    spdEl.textContent = "1.4 m/s";
    stEl.textContent = "Occluded (Memory)";
  } else {
    lvlEl.textContent = "00 NORMALE";
    lvlEl.className = "tele-val status-ok";
    spdEl.textContent = "3.2 m/s";
    stEl.textContent = "Visible · Clear";
  }
}

document.querySelectorAll(".cam-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".cam-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    cams = Number(btn.dataset.cams || 1);
    const demoVideoPanel = document.getElementById("demo-video-panel");
const demoRadarPanel = document.getElementById("demo-radar-panel");
const demoVideo = document.getElementById("demo-video");

document.querySelectorAll(".demo-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".demo-tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    const mode = tab.dataset.demo;
    if (mode === "interactive") {
      if (demoVideoPanel) demoVideoPanel.hidden = true;
      if (demoRadarPanel) demoRadarPanel.hidden = false;
    } else {
      if (demoRadarPanel) demoRadarPanel.hidden = true;
      if (demoVideoPanel) demoVideoPanel.hidden = false;
      if (demoVideo) demoVideo.play().catch(() => {});
    }
  });
});

drawRadar();
  });
});

canvas?.addEventListener("pointermove", (e) => {
  const rect = canvas.getBoundingClientRect();
  ped.x = ((e.clientX - rect.left) / rect.width) * canvas.width;
  ped.y = ((e.clientY - rect.top) / rect.height) * canvas.height;
  const demoVideoPanel = document.getElementById("demo-video-panel");
const demoRadarPanel = document.getElementById("demo-radar-panel");
const demoVideo = document.getElementById("demo-video");

document.querySelectorAll(".demo-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".demo-tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    const mode = tab.dataset.demo;
    if (mode === "interactive") {
      if (demoVideoPanel) demoVideoPanel.hidden = true;
      if (demoRadarPanel) demoRadarPanel.hidden = false;
    } else {
      if (demoRadarPanel) demoRadarPanel.hidden = true;
      if (demoVideoPanel) demoVideoPanel.hidden = false;
      if (demoVideo) demoVideo.play().catch(() => {});
    }
  });
});

drawRadar();
});

const demoVideoPanel = document.getElementById("demo-video-panel");
const demoRadarPanel = document.getElementById("demo-radar-panel");
const demoVideo = document.getElementById("demo-video");

document.querySelectorAll(".demo-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".demo-tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    const mode = tab.dataset.demo;
    if (mode === "interactive") {
      if (demoVideoPanel) demoVideoPanel.hidden = true;
      if (demoRadarPanel) demoRadarPanel.hidden = false;
    } else {
      if (demoRadarPanel) demoRadarPanel.hidden = true;
      if (demoVideoPanel) demoVideoPanel.hidden = false;
      if (demoVideo) demoVideo.play().catch(() => {});
    }
  });
});

drawRadar();
