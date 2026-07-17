# AI Presales Assistant

Multi-tenant SaaS that automates presales workflows: upload an
**RFP** or **Customer Requirements** doc, run an LLM extraction agent to pull
out structured requirements, match them against your **product/datasheet
catalog** with a deterministic rules engine, and auto-generate a **BOQ**,
**Cost Sheet**, **Estimate Sheet (.xlsx)** and a **Proposal (.pdf)**.

## Architectural principle

Same pattern used across the rest of this portfolio
**the LLM only extracts unstructured
input into structured candidates — it never decides quantities, product
matches, or prices.** All matching and pricing runs through
`backend/app/services/rules_engine.py`, a deterministic engine that logs a
`rule_trace` for every BOQ line, so every number on a proposal is auditable
back to an explicit rule. This is deliberately framed for GCC enterprise/
government presales panels who need explainability, not a black box.

## Stack

| Layer      | Tech |
|------------|------|
| Backend    | FastAPI, SQLAlchemy, PostgreSQL, Redis, LangGraph, Anthropic API |
| Frontend   | React 18, TypeScript, Vite, React Router |
| Storage    | S3 (prod) / local disk (dev) |
| Documents  | pypdf (RFP text extraction), openpyxl (xlsx), reportlab (pdf) |
| Auth       | JWT (python-jose), bcrypt password hashing, per-tenant row isolation |
| Deployment | Docker Compose (local) · AWS ECS Fargate + CDK (production) |

## Project layout

```
ai-presales-saas/
├── backend/                  FastAPI service
│   ├── app/
│   │   ├── main.py           app entrypoint, router wiring, /health for ALB
│   │   ├── config.py         env-driven settings
│   │   ├── models.py         SQLAlchemy models (multi-tenant)
│   │   ├── schemas.py        Pydantic request/response models
│   │   ├── auth.py           JWT + password hashing
│   │   ├── routers/          auth, projects, documents, extraction, products, pricing
│   │   └── services/
│   │       ├── extraction_agent.py   LangGraph extraction pipeline (LLM)
│   │       ├── rules_engine.py       deterministic matching + pricing (no LLM)
│   │       ├── proposal_generator.py xlsx/pdf export
│   │       └── s3_service.py         storage abstraction (local disk / S3)
│   ├── scripts/seed_catalog.py       demo product catalog seeder
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                 React + TS app (upload, requirements review, BOQ, export)
│   ├── src/pages/{Login,Dashboard,ProjectDetail}.tsx
│   └── Dockerfile             (multi-stage build → nginx)
├── infra/cdk/                 AWS CDK (Python) — production deployment
│   ├── app.py
│   └── stacks/presales_stack.py   VPC, ECS Fargate x2, RDS, ElastiCache, S3, Secrets Manager, ALB
├── docker-compose.yml          local dev: db + redis + backend + frontend
└── README.md
```

## Company Policy RAG pipeline

A separate, tenant-wide RAG pipeline handles internal policy documents
(discount approval rules, technical standards, compliance clauses, etc.) —
independent of the per-project RFP extraction flow above:

- **Upload** a policy doc (`.pdf`/`.txt`) via the **Policy Library** page — it's
  chunked (`services/policy_rag.py::chunk_text`) and embedded immediately
  using **Voyage AI** (`voyage-3.5` — Anthropic's recommended embeddings
  partner, since Anthropic doesn't serve embeddings directly).
- **Ask** a question and the pipeline does real cosine-similarity retrieval
  over your tenant's embedded chunks, then has Claude answer **using only
  the retrieved excerpts** — if nothing relevant was uploaded, it says so
  explicitly (`grounded: false`) rather than guessing at company policy.
- Every answer returns its **sources** (document title, section, similarity
  score, excerpt) so a sales engineer can verify the pipeline is actually
  working off the document they just uploaded, not off general knowledge.

Endpoints: `POST /policies/upload`, `GET /policies`, `DELETE /policies/{id}`,
`POST /policies/ask`. Embeddings are stored as plain JSON float arrays on
`PolicyChunk.embedding` — fine at this scale; swap for pgvector + an ANN
index if the policy library grows into the thousands of chunks.

Add your Voyage AI key to `.env` (`VOYAGE_API_KEY=pa-...`, get one at
https://www.voyageai.com) alongside `ANTHROPIC_API_KEY` before testing this.

## Run locally (Docker Compose)

```bash
cd ai-presales-saas/backend
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY + a real JWT_SECRET

cd ..
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend API docs: http://localhost:8000/docs

Sign up (creates a tenant + admin user), then seed a demo product catalog:

```bash
docker compose exec backend python scripts/seed_catalog.py <tenant_id>
```

(Get `tenant_id` from `GET /projects` response or the JWT payload — or just
add products yourself via `POST /products`.)

### End-to-end flow to test

1. Create a project (a customer bid/opportunity).
2. Upload an RFP or Customer Requirements file (`.pdf` or `.txt`).
3. Click **Run extraction agent** — LangGraph + Claude pulls out structured
   requirements with confidence scores.
4. Review/check requirements.
5. Click **Generate BOQ** — the deterministic rules engine matches
   requirements to catalog products and prices each line.
6. Download the **Estimate Sheet (.xlsx)** or **Proposal (.pdf)**.

## Deploy to AWS (production)

The CDK stack provisions: VPC (public/private/isolated subnets), ECS Fargate
cluster running backend + frontend as two ALB-fronted services, RDS
PostgreSQL, ElastiCache Redis, an S3 bucket for documents, and Secrets
Manager for DB credentials / JWT secret / Anthropic API key.

```bash
cd infra/cdk
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# first time only, per AWS account/region
cdk bootstrap

cdk deploy --context env=production
```

CDK builds and pushes the backend/frontend Docker images to ECR
automatically via `DockerImageAsset` (no manual `docker push` needed) —
just make sure Docker is running locally when you run `cdk deploy`.

After deploy, set your real Anthropic API key in Secrets Manager:

```bash
aws secretsmanager update-secret \
  --secret-id ai-presales/production/app-secrets \
  --secret-string '{"ANTHROPIC_API_KEY":"sk-ant-...","JWT_SECRET":"<keep-generated-value>"}'
```

Then force a new deployment so the tasks pick up the updated secret:

```bash
aws ecs update-service --cluster <cluster-name> --service <backend-service-name> --force-new-deployment
```

**Region note:** default region in this stack is `me-central-1` (UAE) for
GCC data residency; change via `CDK_DEFAULT_REGION` or the `env_name`
context if you need `me-south-1` (Bahrain) for KSA-adjacent latency.

**Costs/production hardening still worth doing before go-live:** enable RDS
Multi-AZ (already auto-enabled for `env=production`), add a WAF in front of
the ALB, move `create_all` to real Alembic migrations, add CloudWatch alarms
on the ECS services, and put the frontend behind CloudFront + ACM for TLS +
a custom domain.
