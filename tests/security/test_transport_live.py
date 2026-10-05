"""Transport security (ASVS V9). Only meaningful against a deployed HTTPS endpoint, so
these are skipped for the local plain-HTTP app."""
import os
import socket
import ssl
from urllib.parse import urlparse

import pytest
import requests

pytestmark = [pytest.mark.security]

BASE = os.environ.get("BASE_URL", "")
HOST = urlparse(BASE).hostname or ""
needs_https = pytest.mark.skipif(not BASE.startswith("https://"), reason="needs BASE_URL pointing at an HTTPS deployment")


def _handshake(minimum, maximum):
    ctx = ssl.create_default_context()
    ctx.minimum_version, ctx.maximum_version = minimum, maximum
    with socket.create_connection((HOST, 443), timeout=10) as sock:
        with ctx.wrap_socket(sock, server_hostname=HOST) as tls:
            return tls.version(), tls.getpeercert()


@needs_https
def test_tls_1_2_or_newer_is_negotiated_with_a_valid_certificate():
    version, cert = _handshake(ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.MAXIMUM_SUPPORTED)
    assert version in ("TLSv1.2", "TLSv1.3")
    assert cert, "certificate chain and hostname were verified by the default context"


@needs_https
@pytest.mark.parametrize("old", [ssl.TLSVersion.TLSv1, ssl.TLSVersion.TLSv1_1], ids=["TLS1.0", "TLS1.1"])
def test_obsolete_tls_versions_are_refused(old):
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        with pytest.raises((ssl.SSLError, OSError)):
            _handshake(old, old)


@needs_https
def test_plain_http_is_not_served():
    try:
        resp = requests.get(f"http://{HOST}/health", timeout=8, allow_redirects=False)
    except requests.RequestException:
        return  # nothing listens on port 80: nothing to downgrade to
    assert resp.status_code in (301, 302, 307, 308, 403) and "ok" not in resp.text


@needs_https
def test_hsts_is_sent_over_https():
    assert "max-age=" in requests.get(f"{BASE}/health", timeout=10).headers.get("Strict-Transport-Security", "")
