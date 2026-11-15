#!/usr/bin/env python3
"""Avvio immediato ClearCorner: prepara l'ambiente, avvia il server live e apre il browser."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT / "repo"
VENV = REPO / ".venv"


def _venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _ensure_env() -> Path:
    py = _venv_python()
    if not py.exists():
        print("[ClearCorner] Creo ambiente virtuale in repo/.venv...")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])
    check = subprocess.run([str(py), "-c", "import shapely, numpy"], capture_output=True)
    if check.returncode != 0:
        print("[ClearCorner] Installo le dipendenze (requirements.txt)...")
        subprocess.check_call([str(py), "-m", "pip", "install", "-q", "-r", str(REPO / "requirements.txt")])
    return py


def _free_port(start: int = 8000) -> int:
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start


def main() -> None:
    py = _ensure_env()
    port = _free_port(8000)
    env = {**os.environ, "PYTHONPATH": str(REPO)}
    cmd = [str(py), str(REPO / "scripts" / "run_live.py"), "--loop", "--no-tunnel", "--port", str(port)]
    print(f"[ClearCorner] Avvio app su http://127.0.0.1:{port} ...")
    proc = subprocess.Popen(cmd, cwd=str(REPO), env=env)
    url = f"http://127.0.0.1:{port}/"
    opened = False
    try:
        for _ in range(40):
            if proc.poll() is not None:
                break
            try:
                urllib.request.urlopen(url, timeout=0.5).close()
                print(f"[ClearCorner] App pronta -> apro {url}")
                webbrowser.open(url)
                opened = True
                break
            except Exception:
                time.sleep(0.25)
        if not opened and proc.poll() is None:
            webbrowser.open(url)
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        proc.wait(timeout=3)


if __name__ == "__main__":
    main()
