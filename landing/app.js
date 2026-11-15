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
  unix: "git clone https://github.com/MARE-The-Big-Hack-26/oracolo.git && python3 oracolo/start.py",
  zip: "python3 ~/Downloads/oracolo-main/start.py",
  windows: "git clone https://github.com/MARE-The-Big-Hack-26/oracolo.git; py oracolo\\start.py"
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
