# MLSecOps Pipeline

> **Scope:** Multi-Agent Investment Research System (REQ-001)
> **Reference:** OWASP MLSecOps top 10, Google Secure AI Framework (SAIF)
> **Last reviewed:** 2026-04-07

## 1. Pipeline overview

```
    developer
        │ git push
        ▼
  ┌───────────────────┐
  │  GitHub Actions   │   ci.yml  (lint + test + security scan)
  │  (hosted runners) │
  └─────────┬─────────┘
            │ artifacts
            ▼
  ┌───────────────────┐
  │  GitHub Actions   │   deploy.yml  (SSH → self-hosted server)
  │  self-hosted env  │
  └─────────┬─────────┘
            │
            ▼
       production
     (user's server)
```

## 2. CI stage (`.github/workflows/ci.yml`)

Runs on every push and PR:

1. **Checkout** — pinned `actions/checkout@v4`
2. **Python setup** — Python 3.11
3. **Dependency install** — `pip install -r requirements.txt`
4. **Lint** — `ruff check backend/`
5. **Unit tests** — `pytest tests/` (includes security suite)
6. **Dependency audit** — `pip install pip-audit && pip-audit` (CVE scan)
7. **Security regex scan** — `pytest tests/security/` must pass with 0 failures
8. **Static secret scan** — simple grep for `sk-[a-zA-Z0-9]{20,}` in tracked files
9. **Artifact upload** — test report, audit scan report

CI fails the build on any of:
- failing test
- high-severity CVE
- detected secret

## 3. CD stage (`.github/workflows/deploy.yml`)

Triggered manually (`workflow_dispatch`) or on push to `main`:

1. **Verify CI passed** — guarded by `needs: ci`
2. **SSH key** — `webfactory/ssh-agent@v0.9.0` loads `DEPLOY_SSH_KEY` secret
3. **Rsync** — push the repo to `${SERVER_USER}@${SERVER_HOST}:${DEPLOY_PATH}` (excludes `.git`, `__pycache__`, `logs/`)
4. **Remote install** — `ssh ... "cd $DEPLOY_PATH && ./scripts/install_linux.sh --upgrade"`
5. **Remote smoke test** — `ssh ... "./scripts/smoke_test.sh"` — runs a tiny analysis query and checks exit code
6. **Systemd reload** — `ssh ... "sudo systemctl restart ai-research.service"`
7. **Audit log** — writes a deploy event to the remote `logs/audit_trail.jsonl`

## 4. Secrets management

- `DEEPSEEK_API_KEY`, `DEPLOY_SSH_KEY`, `SERVER_HOST`, `SERVER_USER`, `DEPLOY_PATH` — stored as **GitHub repo secrets**, never printed.
- `.env` on the server is owned by the service account, `chmod 600`.
- The CI workflow never mounts `.env` and never runs live LLM calls; tests use mocked responses.

## 5. Model supply-chain controls

| Control                  | Implementation                                                                  |
|--------------------------|----------------------------------------------------------------------------------|
| Pinned model ID          | `deepseek-chat` pinned in `backend/config.py`                                    |
| Pinned API version       | OpenAI SDK version pinned in `requirements.txt`                                  |
| Egress allowlist         | Production server firewall allows only DeepSeek, yfinance, akshare endpoints     |
| Rate limiting            | Token-budget guard in `backend/observability/token_tracker.py` (soft 200k/req)   |
| Dependency hashing       | `pip-audit` step in CI; Dependabot enabled in repo settings                      |

## 6. Runtime observability

- **Token accounting** — `backend/observability/token_tracker.py` records per-agent usage per request; `graph.run_analysis()` attaches a `token_usage` block to the result.
- **Audit trail** — `backend/observability/audit_trail.py` writes append-only JSONL for every sanitizer block, output filter flag, advisory override.
- **Health checks** — systemd unit uses `ExecStart=/usr/bin/python -m backend.healthcheck` (reuse Stage-7 verify script).

## 7. Incident response

1. **Detect** — grep `logs/audit_trail.jsonl` for `kind: security_alert` or `kind: input_blocked` spike
2. **Contain** — disable the offending user via IP block at the reverse proxy; rotate `DEEPSEEK_API_KEY` if it leaked
3. **Investigate** — replay the conversation via `request_id` in the audit trail
4. **Report** — append finding to `docs/ai_security_risk_register.md`
5. **Remediate** — add a new pattern to `backend/security/injection_patterns.py` and a regression test to `tests/security/`

## 8. Hardening checklist (self-hosted server)

- [ ] Server runs as non-root service account (`aiuser`)
- [ ] `.env` is `chmod 600` and owned by `aiuser`
- [ ] Firewall allows 443 inbound and only the 3 required outbound hosts
- [ ] `fail2ban` on SSH
- [ ] `logs/audit_trail.jsonl` rotated daily via logrotate
- [ ] Streamlit fronted by nginx + TLS cert
- [ ] Backup of `config/schedule.json` to off-host storage
