# Financial Infrastructure Failure and Systemic Risk Simulator

An educational simulation of how a failed payment/cloud service can affect
banks and spread losses through interbank exposures. Compare a saved run with
an extra liquidity buffer for one bank. All network data is fictional.

Team: Bhuvi B (PES2UG24AM041), Ashrit N (PES2UG24AM032).

## Run locally on Windows

Install Docker Desktop (and start it), Node.js 20.9+ and a standard Windows
Python 3.11+ installation. From the project directory, double-click `start.cmd`,
or run:

```powershell
.\start.ps1
```

The launcher prepares the Python environment and frontend packages, starts
PostgreSQL and Neo4j, applies the schema/seed, prepares demo users, rebuilds
the graph and opens the website. It chooses available ports; use the URL it
prints. The first launch needs internet access to install dependencies.
Errors are saved in `.local-logs`. Press Ctrl+C in the launcher to stop the
web/API processes; database containers remain running.

Demo logins: `admin` / `admin123`, `analyst` / `analyst123`.

## Admin and Analyst roles

| Action | Admin | Analyst |
|---|---|---|
| View network and rankings | Yes | Yes |
| Create scenarios and run simulations | Yes | Yes |
| Inspect results and propagation paths | Yes | Yes, for their own runs |
| Run buffer comparisons | Yes | Yes, for their own runs |
| View saved runs | All users' runs | Only their own |
| Add/edit/delete banks, services, dependencies and exposures | Yes | No |
| Rebuild Neo4j after network changes | Yes | No |
| View audit history | Yes | No |

Admin maintains the network; Analyst uses it to perform simulations.
Permissions and run ownership are enforced by the FastAPI backend as well as
reflected in the frontend controls.


## Tech stack

| Layer | Technologies | Purpose |
|---|---|---|
| Frontend | Next.js, React, TypeScript, CSS | Dashboard, network visualization, admin forms, scenarios and results. |
| Backend / API | Python, FastAPI, Uvicorn, Pydantic | REST endpoints, request validation, authentication and simulation coordination. |
| Simulation | Python `Decimal` | Deterministic loss calculations, default propagation and buffer comparisons. |
| Relational database | PostgreSQL 17, SQL, PL/pgSQL | Master data, users/sessions, saved runs, constraints, views, functions and audit triggers. |
| Graph database | Neo4j 5, Cypher | Network projection, relationship traversal and connectivity rankings. |
| Database drivers | pg8000, Neo4j Python driver | Backend connections and parameterized database queries. |
| Local environment | Docker Compose, Python virtual environment, Node.js/npm, PowerShell | Database containers, dependencies and one-shot Windows startup. |
| Verification | Python `unittest`, TypeScript compiler, Next.js build | Focused logic tests, type checking and frontend compilation. |

Request flow: **Browser → Next.js → FastAPI → PostgreSQL / Neo4j**.
Python runs the cascade; PostgreSQL is the source of truth and Neo4j is a
rebuildable graph projection.

## Project files

- `frontend/`: Next.js, React and TypeScript interface.
- `backend/`: Python/FastAPI API, sessions, simulation and database access.
- PostgreSQL: users, network records, scenarios, saved impacts and audit logs.
- Neo4j: graph projection, traversal and connectivity rankings.
- `sql/schema.sql`: schema used by setup; `create_database.sql` is the same
  DDL with explanations. `seed.sql` supplies the fictional network.
- `sql/demo_queries.sql`, `cypher/demo_queries.cypher`: DBMS demonstrations.
- `tests/`: focused simulation and request/snapshot tests.

Configuration comes from `.env` (copy `.env.example` for manual setup).
Next.js forwards `/api` to `BACKEND_URL`, defaulting to localhost port 8000.
PostgreSQL is authoritative; rebuild the graph after network edits. Saved
comparisons reuse the original input snapshot.

## Manual setup

```powershell
Copy-Item .env.example .env  # only if .env does not exist
python -m venv .venv-windows
.\.venv-windows\Scripts\python.exe -m pip install -r backend/requirements.txt
docker compose up -d
# Once both databases are ready:
.\.venv-windows\Scripts\python.exe -m backend.setup_db
.\.venv-windows\Scripts\python.exe -m backend.seed_users --defaults
.\.venv-windows\Scripts\python.exe -m backend.sync_graph
.\.venv-windows\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open the frontend URL printed by Next.js. For pgAdmin, use the PostgreSQL
connection values in `.env`; the Compose database is named `systemic_risk`.

## Checks

```powershell
.\.venv-windows\Scripts\python.exe -m unittest discover -s tests -v
cd frontend
npm run typecheck
npm run build
```

Unit tests and type checks do not constitute full system testing. Reports,
diagrams, screenshots and coursework documents are kept locally and excluded
from Git.
