# financial-context-graph — Financial Services Context Graph

AI agent with graph-based reasoning over investment management, trading, compliance, and risk — built on Neo4j + PydanticAI + Next.js.

---

## About this project

This project was pre-scaffolded using [create-context-graph](https://github.com/neo4j-labs/create-context-graph) and delivered as ready-to-run source code.

If you tried running `create-context-graph` directly and hit a network error pulling packages like `click` from PyPI, that is expected on restricted networks — **you do not need to run that tool**. Everything it would have generated is already here. The only packages you need to install are the runtime dependencies for the application itself (`make install` below), which are standard Python and Node packages your network may already allow.

---

## Fully offline installation

If `uv sync` or `npm install` are also blocked, use Docker. The images can be built on any machine with internet access and transferred as files — no network needed on the target machine.

**On a machine with internet access:**

```bash
docker compose build
docker save financial-context-graph-backend -o backend.tar
docker save financial-context-graph-frontend -o frontend.tar
```

Transfer `backend.tar`, `frontend.tar`, and `docker-compose.yml` to the target machine, then:

```bash
docker load -i backend.tar
docker load -i frontend.tar
docker compose up
```

The application will start on the same ports (`3000` / `8000`). `.env` still needs to be present with your Neo4j credentials and `ANTHROPIC_API_KEY`.

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- `uv` — [install](https://docs.astral.sh/uv/getting-started/installation/)
- Neo4j running locally (Desktop, Docker, or Aura)
- An Anthropic API key

---

## Setup

### 1. Configure your environment

Edit `.env` — the Neo4j connection is pre-filled with defaults; only the API key needs to be added:

```env
ANTHROPIC_API_KEY=your-key-here
NEO4J_URI=neo4j://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=your-database-name   # defaults to "neo4j" if omitted
```

### 2. Install dependencies

```bash
make install
```

Installs the Python backend (`uv sync`) and the Next.js frontend (`npm install`).

### 3. Seed sample data

```bash
make seed
```

Applies schema constraints/indexes and loads sample financial-services entities, documents, and decision traces into Neo4j.

### 4. Start the application

```bash
make start
```

| Service | URL |
| --- | --- |
| Frontend | <http://localhost:3000> |
| Backend API | <http://localhost:8000> |
| Neo4j Browser | <http://localhost:7474> |

---

## What's in the graph

| Entity | Type | Description |
| --- | --- | --- |
| Account | Object | Client accounts (checking, brokerage, retirement, etc.) |
| Transaction | Event | Transfers, trades, wire payments |
| Decision | Event | Investment decisions with full reasoning trace |
| Policy | Object | Compliance and trading policies |
| Security | Object | Financial instruments (equities, ETFs, bonds) |
| Person / Organization / Location | Base | Clients, advisors, firms |

Seeded with 3 end-to-end decision traces: trade execution, AML compliance review, and portfolio rebalance.

---

## Try these prompts

### Portfolio Analysis

- "Show me a summary of all client accounts and their current balances"
- "Which portfolios have the highest risk exposure?"

### Compliance & Risk

- "Are there any accounts flagged for compliance review?"
- "What policies apply to international wire transfers?"

### Decision Intelligence

- "What was the reasoning behind the decision to sell AAPL last week?"
- "Show me the causal chain for the Smith portfolio rebalance"

---

## Project structure

```text
financial-context-graph/
├── backend/          FastAPI + PydanticAI agent
│   ├── app/          Application code
│   └── scripts/      Data seeding
├── frontend/         Next.js + Chakra UI + Neo4j NVL graph viewer
├── cypher/           Schema constraints and GDS projections
├── data/             Domain ontology and fixture documents
├── .env              Local configuration (not committed)
└── Makefile          All dev commands
```

---

## Useful commands

```bash
make test-connection   # Verify Neo4j credentials before seeding
make seed              # Re-seed sample data (safe to re-run)
make reset             # Wipe Neo4j data and re-seed
make schema            # Apply schema only, no data
```

---

## Troubleshooting

### Backend won't start — `ANTHROPIC_API_KEY` error

Set `ANTHROPIC_API_KEY` in `.env`. The agent requires it at startup.

### Neo4j connection fails

Run `make test-connection`. Check that `NEO4J_URI`, `NEO4J_USERNAME`, and `NEO4J_PASSWORD` in `.env` are correct.

### Port conflict

Change `BACKEND_PORT` or `FRONTEND_PORT` in `.env`, then restart.

### Frontend build errors

Delete `frontend/node_modules` and re-run `make install`.
