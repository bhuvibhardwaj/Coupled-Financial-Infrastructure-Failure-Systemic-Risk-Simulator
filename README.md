# Systemic Risk Simulator

A DBMS mini project with a Next.js web app, Python/FastAPI backend,
PostgreSQL records, and a Neo4j dependency/exposure graph. It simulates how
a fictional infrastructure failure can lead to bank liquidity stress and
financial contagion. See [the project plan](PROJECT_PLAN.md) and
[design documentation](docs/DESIGN.md).

The app includes Admin/Analyst login, editable network data, graph rebuild,
scenario history, run paths, Cypher critical-node rankings, and a saved
liquidity-buffer comparison. The data and score are educational examples,
not financial forecasts.

## Requirements

- Standard Python 3.11+ with `venv` and `pip` (recommended over MSYS Python on
  Windows, which may compile Pydantic from source)
- Node.js 20.9+ and npm
- Docker Desktop, or separate PostgreSQL 17 and Neo4j 5 installations

## Set up locally (PowerShell)

From the project root:

```powershell
Copy-Item .env.example .env
docker compose up -d
python -m venv .venv
$projectPython = if (Test-Path '.venv\Scripts\python.exe') {
    '.\.venv\Scripts\python.exe'
} else {
    '.\.venv\bin\python.exe'
}
& $projectPython -m pip install -r backend\requirements.txt
& $projectPython -m backend.setup_db
& $projectPython -m backend.seed_users
& $projectPython -m backend.sync_graph
```

`seed_users` prompts for names, emails and passwords for one Admin and one
Analyst. Use distinct passwords of at least 12 characters. It stores only
salted password hashes. Re-running it updates those two accounts, so use it
deliberately. `.env` contains the local database URLs and is ignored by Git;
the values in `.env.example` match Docker Compose. Change the demo credentials
for non-local use, and set `COOKIE_SECURE=true` when serving over HTTPS.

`backend.setup_db` creates or updates the schema and inserts the fictional
six-bank/four-service dataset. It is safe to rerun without deleting saved runs.
`backend.sync_graph` rebuilds only this project's labelled Neo4j nodes.
After Admin edits, use the Network page's **Rebuild Neo4j network** button
before starting a new scenario.

Start the API from the project root in one terminal:

```powershell
$projectPython = if (Test-Path '.venv\Scripts\python.exe') {
    '.\.venv\Scripts\python.exe'
} else {
    '.\.venv\bin\python.exe'
}
& $projectPython -m uvicorn backend.main:app --reload
```

Start the web app in another terminal:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open `http://localhost:3000`. API documentation is at
`http://localhost:8000/docs`. Next.js forwards `/api/*` to FastAPI; the
frontend itself does not hold database credentials.

## Demo flow

1. Sign in as Admin and open **Network**. Inspect the banks, services,
   dependency lines, creditor arrows and Cypher rankings.
2. Open **Scenarios**, select **Payment Rail**, set severity to 100%, and run.
   Bank A and Bank B default; the expected average stress is 49.33%.
3. Open a bank's **Inspect** path to see the recorded propagation chain.
4. On the run page, add 20 to Bank B's liquidity buffer and compare. Bank B
   no longer defaults; the original master data is unchanged.
5. As Admin, edit a bank/service, inspect the audit list, rebuild the graph,
   and run again. As Analyst, check that edit/rebuild actions are unavailable
   and API-protected.

## Focused checks and DBMS query files

```powershell
python -m unittest discover -s tests -v
python -m compileall -q backend tests
```

In `frontend`, use `npm run typecheck` and `npm run build`.
[`sql/demo_queries.sql`](sql/demo_queries.sql) contains DDL, DML,
JOIN/GROUP BY/HAVING/ORDER BY, aggregate, subquery, view and function
demonstrations. [`cypher/demo_queries.cypher`](cypher/demo_queries.cypher)
contains dependency, aggregation and variable-length path queries. These
demo files are not run automatically.

The full browser-to-databases system checks, screenshots and observed results
are intentionally deferred; see [verification status](docs/TEST_STATUS.md).
For submission, record both team members' actual contributions and commits,
plus the live results and screenshots. Do not treat the demo data as real-world
financial advice.
