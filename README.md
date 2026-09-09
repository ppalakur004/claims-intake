# Claims Intake Service

A service that accepts a first notice of loss, validates it against the policy
master and the rule table in `docs/api-contract.md`, and either records a
notification and issues a claim reference or refuses the submission with a
specific reason.

The only HTTP operation in scope is accepting a notification:

```http
POST /notifications
```

The service does not adjust claims, reserve payments, or decide whether a claim
will be paid. It only decides whether the notification is well formed and
admissible under rules V-1 through V-7.

## Where things are

| Path | What it holds |
| --- | --- |
| `docs/api-contract.md` | What the service accepts, returns, and refuses. The authority. |
| `docs/requirements-brief.md` | The open work items and their acceptance criteria. |
| `docs/payload-triage.md` | Your Day 1 classification of the edge payloads. |
| `data/` | Synthetic policies and notification payloads. |
| `src/claims/` | The service. |
| `tests/` | Unit tests mirror `src/claims/`. Integration tests exercise HTTP. |

## Working in this repository

You are inside a Linux container. Confirm it before you start:

```bash
uname -sm     # Linux aarch64
pwd           # /workspaces/claims-intake
```

Dependencies are installed when the container is created. There is no install step
for this lab.

Run the service locally:

```bash
uv run uvicorn claims.api.routes:app --host 0.0.0.0 --port 8000
```

Submit a valid notification from another terminal:

```bash
curl -s -X POST http://127.0.0.1:8000/notifications \
  -H "Content-Type: application/json" \
  -d '{
    "policy_number": "MOT-4471",
    "loss_date": "2026-04-02",
    "claim_type": "collision",
    "estimated_amount": "4200.00",
    "description": "Rear ended at a junction."
  }'
```

Expected response:

```json
{
  "claim_reference": "CLM-2026-000001",
  "status": "recorded"
}
```

Run the checks:

```bash
uv run pytest
uv run ruff check .
uv run mypy src tests
```

## Docker

Build the image for the deployment platform:

```bash
docker buildx build --platform linux/amd64 -t claims-intake:day4 .
```

Run the image:

```bash
docker run --rm -p 8000:8000 claims-intake:day4
```

The `--platform linux/amd64` flag makes the image match the target Linux server
architecture. That matters when the laptop or dev container host is a different
architecture, such as Apple Silicon/ARM, because an image built for the host may
not run in the same place the service is deployed.

## Data

Everything in `data/` is synthetic and was authored for this program. It contains
no real client data and no named clients.
