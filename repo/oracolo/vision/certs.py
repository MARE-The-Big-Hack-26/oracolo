"""Certificato autofirmato per HTTPS locale e tunnel Cloudflare per HTTPS pubblico affidabile."""
from __future__ import annotations

import atexit
import datetime
import ipaddress
import os
import platform
import re
import shutil
import socket
import ssl
import subprocess
import tarfile
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

_TRYCF_RE = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def ensure_cert(directory, extra_ips=()) -> tuple:
    """Crea (o riusa) ``cert.pem`` e ``key.pem`` validi per localhost, .local e gli IP indicati."""
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    cert, key = d / "cert.pem", d / "key.pem"
    ips = {"127.0.0.1", lan_ip(), *extra_ips}
    host = socket.gethostname().strip()
    dns_names = ["localhost"]
    if host and host.lower() != "localhost":
        local_host = host if host.endswith(".local") else f"{host.split('.')[0]}.local"
        if local_host not in dns_names:
            dns_names.append(local_host)
    required = ips | set(dns_names)
    marker = d / "ips.txt"
    if cert.exists() and key.exists() and marker.exists() and set(marker.read_text().split()) >= required:
        return str(cert), str(key)

    from cryptography import x509  # noqa: PLC0415
    from cryptography.hazmat.primitives import hashes, serialization  # noqa: PLC0415
    from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: PLC0415
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID  # noqa: PLC0415

    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "oracolo")])
    san = x509.SubjectAlternativeName(
        [x509.DNSName(h) for h in dns_names] + [x509.IPAddress(ipaddress.ip_address(i)) for i in sorted(ips)]
    )
    now = datetime.datetime.now(datetime.timezone.utc)
    c = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(k.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=30))
        .add_extension(san, critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                key_cert_sign=True,
                crl_sign=False,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(k, hashes.SHA256())
    )
    cert.write_bytes(c.public_bytes(serialization.Encoding.PEM))
    key.write_bytes(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                    serialization.NoEncryption()))
    marker.write_text("\n".join(sorted(required)))
    return str(cert), str(key)


def ensure_cloudflared(cache_dir=None) -> str | None:
    """Restituisce il percorso di ``cloudflared`` (locale o scaricato in cache), oppure None."""
    for candidate in (shutil.which("cloudflared"), "/opt/homebrew/bin/cloudflared", "/usr/local/bin/cloudflared"):
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return str(candidate)

    cdir = Path(cache_dir) if cache_dir is not None else Path.home() / ".cache" / "oracolo"
    target = cdir / "cloudflared"
    if target.is_file() and os.access(target, os.X_OK):
        return str(target)

    sys_name = platform.system().lower()
    mach = platform.machine().lower()
    arch = "arm64" if mach in ("arm64", "aarch64") else ("amd64" if mach in ("x86_64", "amd64") else None)
    if not arch or sys_name not in ("darwin", "linux"):
        return None

    asset = f"cloudflared-{sys_name}-{arch}" + (".tgz" if sys_name == "darwin" else "")
    url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/{asset}"
    try:
        cdir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=cdir, delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            with urllib.request.urlopen(url, timeout=30) as resp, open(tmp_path, "wb") as out:
                shutil.copyfileobj(resp, out)
            if sys_name == "darwin":
                with tarfile.open(tmp_path, "r:gz") as tf:
                    member = next((m for m in tf.getmembers() if m.isfile() and Path(m.name).name == "cloudflared"), None)
                    if member is None:
                        return None
                    with tf.extractfile(member) as src, tempfile.NamedTemporaryFile(dir=cdir, delete=False) as bin_tmp:
                        bin_tmp_path = Path(bin_tmp.name)
                        shutil.copyfileobj(src, bin_tmp)
                bin_tmp_path.chmod(0o755)
                bin_tmp_path.replace(target)
                tmp_path.unlink(missing_ok=True)
            else:
                tmp_path.chmod(0o755)
                tmp_path.replace(target)
            return str(target)
        except Exception:  # noqa: BLE001
            tmp_path.unlink(missing_ok=True)
            return None
    except Exception:  # noqa: BLE001
        return None


def start_tunnel(port: int, timeout: float = 20.0) -> tuple[str | None, subprocess.Popen | None]:
    """Avvia un Quick Tunnel Cloudflare verso ``127.0.0.1:port`` e restituisce (url_https, proc)."""
    bin_path = ensure_cloudflared()
    if not bin_path:
        return None, None

    proc = subprocess.Popen(
        [bin_path, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{port}"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    atexit.register(proc.terminate)

    found_url: list[str] = []
    registered = [False]
    ready = threading.Event()

    def _drain():
        if proc.stdout is None:
            return
        for line in proc.stdout:
            if not ready.is_set():
                if not found_url:
                    m = _TRYCF_RE.search(line)
                    if m:
                        found_url.append(m.group(0))
                if "Registered tunnel connection" in line:
                    registered[0] = True
                if found_url and registered[0]:
                    ready.set()

    threading.Thread(target=_drain, daemon=True).start()
    if ready.wait(timeout=timeout) and found_url:
        time.sleep(1.5)
        return found_url[0], proc

    proc.terminate()
    return None, None


def maybe_wrap_tls(sock: socket.socket, ssl_ctx: ssl.SSLContext | None) -> socket.socket:
    """Esegue l'handshake TLS se il client invia ClientHello, altrimenti lascia HTTP in chiaro."""
    if isinstance(sock, ssl.SSLSocket):
        sock.settimeout(10)
        sock.do_handshake()
        sock.settimeout(None)
        return sock
    if ssl_ctx is not None:
        sock.settimeout(10)
        try:
            first = sock.recv(1, socket.MSG_PEEK)
        except OSError:
            first = b""
        if first == b"\x16":  # TLS ClientHello
            sock = ssl_ctx.wrap_socket(sock, server_side=True, do_handshake_on_connect=False)
            sock.do_handshake()
        sock.settimeout(None)
    return sock


def build_ssl_context(certfile, keyfile) -> ssl.SSLContext | None:
    """Crea un contesto TLS server dal certificato indicato."""
    if not certfile:
        return None
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile, keyfile)
    return ctx
