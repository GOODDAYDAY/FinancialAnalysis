# Production Deployment — Docker Containerization

> **Scope:** Containerized deployment via GitHub Container Registry + Docker Compose
> **Last reviewed:** 2026-04-22

## 1. Overview

The system deploys as **two Docker containers** on a Linux server:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Production Server                            │
│                                                                     │
│  ┌─────────────────────────┐       ┌─────────────────────────────┐ │
│  │  app container          │       │  mlflow container            │ │
│  │  image: ghcr.io/.../app │ HTTP  │  image: python:3.11-slim    │ │
│  │  port: 8501             │──────►│  port: 5000                 │ │
│  │  user: appuser          │       │  MLflow tracking server     │ │
│  │  memory: 4G max         │       │  memory: 2G max             │ │
│  │  cpu: 2.0 max           │       │  cpu: 1.0 max               │ │
│  │  restart: always        │       │  restart: always            │ │
│  └─────────┬───────────────┘       └──────────────┬──────────────┘ │
│            │                                       │                │
│            │     ┌──────────────────────────────────┘               │
│            ▼     ▼                                                  │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                   Docker Volumes                               │ │
│  │  mlflow-data          ← experiment run metadata                │ │
│  │  mlflow-artifacts     ← model artifacts, reports               │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌───────────────────────┐                                          │
│  │  nginx (external)      │     :443 (TLS)                          │
│  │  reverse proxy + TLS   │◄──── from users                         │
│  │  → localhost:8501      │                                         │
│  └───────────────────────┘                                          │
└─────────────────────────────────────────────────────────────────────┘
```

## 2. Docker Image

### 2.1 Multi-stage build

```
┌──────────────────────────────────────────────────────────────────┐
│ Stage 1: builder                                                 │
│ Base: python:3.11-slim                                           │
│                                                                  │
│  COPY requirements.txt .                                         │
│  RUN pip install --no-cache-dir --prefix=/install -r req.txt     │
│                                                                  │
│  Result: all pip packages in /install                            │
│  (gcc, build tools NOT included)                                 │
└────────────────────────┬─────────────────────────────────────────┘
                         │ COPY --from=builder
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ Stage 2: runtime                                                 │
│ Base: python:3.11-slim                                           │
│                                                                  │
│  RUN apt-get install gcc libgl1-mesa-glx curl                    │
│  RUN groupadd appuser && useradd -r -g appuser appuser           │
│  COPY --from=builder /install /usr/local                         │
│  COPY backend/ scripts/ frontend/ tools/ ./                      │
│                                                                  │
│  HEALTHCHECK curl http://localhost:8501/_stcore/health           │
│  EXPOSE 8501                                                     │
│  USER appuser  ← non-root for security                           │
│  CMD streamlit run frontend/app.py                               │
│                                                                  │
│  Result: ~500MB image, non-root user, health check enabled       │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 Image properties

| Property | Value |
|:---------|:------|
| Base image | python:3.11-slim |
| Build method | Multi-stage (builder → runtime) |
| Runtime user | `appuser` (non-root) |
| Size | ~500MB |
| Health check | `curl http://localhost:8501/_stcore/health` (30s interval, 3 retries) |
| Labels | `org.opencontainers.image.source`, `org.opencontainers.image.description` |

## 3. Docker Compose

### 3.1 Development (docker-compose.yml)

```yaml
services:
  app:
    image: ghcr.io/${GITHUB_REPOSITORY}/app:latest
    build: .                    # fallback for local dev
    ports: ["8501:8501"]
    env_file: .env
    memory: 2G limit, 1.0 CPU
    logging: json-file, 10MB max, 3 files

  mlflow:
    image: python:3.11-slim
    ports: ["5000:5000"]
    memory: 1G limit, 0.5 CPU
    volumes: mlflow-data, mlflow-artifacts
```

### 3.2 Production override (deploy/docker-compose.prod.yml)

```yaml
services:
  app:
    image: ghcr.io/${GITHUB_REPOSITORY}/app:${APP_TAG}
    memory: 4G limit, 2.0 CPU    # higher limits for production
    restart: always              # not just unless-stopped
    logging: json-file, 20MB max, 5 files  # larger log rotation

  mlflow:
    memory: 2G limit, 1.0 CPU
    restart: always
    logging: json-file, 10MB max, 5 files
```

### 3.3 Production deploy command

```bash
docker compose \
  -f docker-compose.yml \
  -f deploy/docker-compose.prod.yml \
  --env-file deploy/.env \
  up -d
```

## 4. CI/CD Pipeline

### 4.1 Deploy workflow (deploy.yml)

```
  push to main
      │
      ▼
┌─────────────────────────────┐
│  Job 1: build-and-push      │
│                             │
│  1. Checkout                 │
│  2. Docker Buildx            │
│  3. Login to ghcr.io         │
│  4. Build image              │
│  5. Push to ghcr.io          │
│     tags: <sha>, latest      │
│     cache: type=gha          │
└─────────────┬───────────────┘
              │ needs: build-and-push
              ▼
┌─────────────────────────────┐
│  Job 2: deploy              │
│                             │
│  1. Setup SSH (ed25519 key) │
│  2. SSH to server            │
│  3. docker compose pull app  │
│  4. docker compose up -d app │
│  5. Health check:            │
│     curl :8501/_stcore/      │
│     health (15 × 2s)         │
│  6. Show logs on failure     │
└─────────────────────────────┘
```

### 4.2 Image lifecycle

```
  developer pushes to main
      │
      │  SHA: a1b2c3d
      ▼
  ghcr.io/owner/repo/app:a1b2c3d    ← new image pushed
  ghcr.io/owner/repo/app:latest     ← latest tag updated
      │
      │  deploy.yml SSH to server
      ▼
  Server pulls app:a1b2c3d
      │
      │  docker compose up -d
      ▼
  Old container stopped, new container started
  Health check verifies :8501 is responding
```

### 4.3 Rollback

```bash
# Deploy a previous version by specifying the SHA tag
APP_TAG=previous_sha docker compose up -d app

# All SHA-tagged images are retained in ghcr.io
# No separate registry cleanup needed
```

## 5. Security

### 5.1 Container security layers

```
┌─────────────────────────────────────────────────────────┐
│ Layer 1: Multi-stage build                              │
│  → Build tools (gcc, headers) not in runtime image       │
│  → Smaller attack surface                                │
├─────────────────────────────────────────────────────────┤
│ Layer 2: Non-root user                                  │
│  → appuser (no root privileges inside container)         │
│  → Cannot install packages, modify system files          │
├─────────────────────────────────────────────────────────┤
│ Layer 3: Trivy vulnerability scan                       │
│  → CI gate: CRITICAL/HIGH CVEs block deployment          │
│  → Runs after Docker build, before push                  │
├─────────────────────────────────────────────────────────┤
│ Layer 4: Resource limits                                │
│  → Memory/CPU limits prevent resource exhaustion         │
│  → Log rotation prevents disk fill                       │
├─────────────────────────────────────────────────────────┤
│ Layer 5: SSH key authentication                         │
│  → Ed25519 key from GitHub secrets                       │
│  → StrictHostKeyChecking=yes (no MITM)                   │
│  → No password authentication                            │
└─────────────────────────────────────────────────────────┘
```

### 5.2 Secrets

| Secret | Usage |
|:-------|:------|
| `GITHUB_TOKEN` | Docker login to ghcr.io (auto-generated, scoped to repo) |
| `SSH_PRIVATE_KEY` | SSH deploy key (Ed25519, deployed from GitHub secrets) |
| `SSH_KNOWN_HOSTS` | Pinned server host key (prevents MITM) |
| `DEEPSEEK_API_KEY` | In `.env` file on server (chmod 600, not in git) |

## 6. Local development

### 6.1 Quick start

```bash
# 1. Copy environment template
cp deploy/.env.example deploy/.env
# Edit deploy/.env with your DEEPSEEK_API_KEY

# 2. Build and start
docker compose up -d --build

# 3. Access the app
open http://localhost:8501
open http://localhost:5000  # MLflow UI
```

### 6.2 Docker image layers (optimized)

```
Layer 1: python:3.11-slim base (~120MB)
Layer 2: apt-get install gcc, libgl1, curl (~80MB)
Layer 3: pip packages from builder (~250MB)
Layer 4: application code (~10MB)
────────────────────────────────────────
Total: ~460MB
```

### 6.3 Layer caching strategy

| Layer | Cache key | When invalidated |
|:------|:----------|:-----------------|
| Base image | python:3.11-slim digest | Rarely (upstream update) |
| System packages | apt-get install command | When Dockerfile changes |
| Pip packages | requirements.txt content | When requirements change |
| Application code | COPY backend/ scripts/... | Every code change |

The `--prefix=/install` trick in the builder stage means pip packages are cached independently from the application code, so code changes don't invalidate the expensive pip install step.
