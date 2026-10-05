# Security tooling

Standards mapping, coverage and known gaps are in [docs/12_security.md](../docs/12_security.md).

| Layer | Tool | Run locally |
|---|---|---|
| Security regression tests | pytest, REST Assured | `pytest -m security`, `make java` |
| SAST | bandit | `make audit` |
| SCA | pip-audit | `make audit` |
| Secret scanning | gitleaks | `make audit` (needs `brew install gitleaks`) |
| IaC lint | cfn-lint | `make audit` |
| DAST | OWASP ZAP baseline | GitHub Actions job `dynamic-scan`; report in the `zap-report` artifact. Needs Docker to run locally |

`.zap/rules.tsv` decides which ZAP alerts fail the build and records why any are ignored.
