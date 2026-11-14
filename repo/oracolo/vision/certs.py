"""Certificato autofirmato per HTTPS (Safari sull'iPhone consente la camera solo su HTTPS)."""
from __future__ import annotations

import datetime
import ipaddress
import socket
from pathlib import Path


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
    """Crea (o riusa) ``cert.pem`` e ``key.pem`` validi per localhost e per gli IP indicati."""
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    cert, key = d / "cert.pem", d / "key.pem"
    ips = {"127.0.0.1", lan_ip(), *extra_ips}
    marker = d / "ips.txt"
    if cert.exists() and key.exists() and marker.exists() and set(marker.read_text().split()) >= ips:
        return str(cert), str(key)

    from cryptography import x509  # noqa: PLC0415
    from cryptography.hazmat.primitives import hashes, serialization  # noqa: PLC0415
    from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: PLC0415
    from cryptography.x509.oid import NameOID  # noqa: PLC0415

    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "oracolo")])
    san = x509.SubjectAlternativeName([x509.DNSName("localhost")] + [x509.IPAddress(ipaddress.ip_address(i)) for i in sorted(ips)])
    now = datetime.datetime.now(datetime.timezone.utc)
    c = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(k.public_key())
         .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(minutes=5))
         .not_valid_after(now + datetime.timedelta(days=30)).add_extension(san, critical=False)
         .sign(k, hashes.SHA256()))
    cert.write_bytes(c.public_bytes(serialization.Encoding.PEM))
    key.write_bytes(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                    serialization.NoEncryption()))
    marker.write_text("\n".join(sorted(ips)))
    return str(cert), str(key)
