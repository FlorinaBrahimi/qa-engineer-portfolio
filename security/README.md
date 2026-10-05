# Security testing

Three layers, all automated:

| Layer | Tool | What it catches | Run |
|---|---|---|---|
| Behavioural | `tests/security/` (pytest) and `SecurityTest.java` | Missing auth, missing hardening headers, injection and XSS handling, information leakage | `pytest -m security` |
| Dependencies | [pip-audit](https://github.com/pypa/pip-audit) | Known CVEs in the Python packages the app and tests depend on | `make audit` |
| Static analysis | [bandit](https://bandit.readthedocs.io) | Insecure code patterns in the app (hard-coded secrets, unsafe calls, debug mode) | `make audit` |

Both scans run in CI (`security-scans` job) and fail the build on high-severity findings.
Reports land in `reports/pip-audit.json` and `reports/bandit.json`.

## Dynamic scanning (nightly, not in this repo's CI)

For a deployed environment run an OWASP ZAP baseline scan against the live URL:

```bash
docker run --rm -t ghcr.io/zaproxy/zaproxy:stable zap-baseline.py -t "$BASE_URL" -r zap-report.html
```

ZAP needs Docker, which is why it is a nightly Jenkins stage rather than a PR check.
