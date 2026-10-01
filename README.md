# Systemic Risk Simulator

This is the first working milestone of the DBMS mini project. A Next.js page
lets you choose an infrastructure service and severity. FastAPI uses
PostgreSQL for the fictional network and saved results, Neo4j for dependency
and exposure edges, and a Python cascade model to calculate bank stress.

The [project plan](PROJECT_PLAN.md) describes the remaining features. This
milestone has one end-to-end scenario flow and saved run history; login, admin
editing, graph visualisation, mitigation and the remaining advanced-database
demonstrations are scheduled next. **Do not expose this unauthenticated demo on
a public network.**

## Prerequisites

- Standard Python 3.11 or newer, with `venv` and `pip` (recommended over MSYS
  Python on Windows, which may need to compile Pydantic from source)
- Node.js 20.9 or newer, with npm
- Docker Desktop running (or local PostgreSQL and Neo4j installations)

## Set up on Windows PowerShell

From the repository root:

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
& $projectPython -m backend.sync_graph
```

The executable is under `.venv\Scripts` for standard Windows Python and
`.venv\bin` for MSYS Python. If your default `python` does not include `pip`,
use a Python installation that supports `venv` and `pip`. The `.env` values
match the local Docker Compose services; change the passwords outside this
local demo. The `.env` file is ignored by Git.

Start the API in one terminal:

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
npm install
npm run dev
```

Open `http://localhost:3000`. The FastAPI documentation is at
`http://localhost:8000/docs`. Run `& $projectPython -m backend.sync_graph` again after
changing the network tables. If the graph does not match PostgreSQL, the API
returns a clear conflict error instead of silently simulating stale data.

## Test the calculation

```powershell
python -m unittest discover -s tests -v
```

The Payment Rail example should produce two defaults and an average stress of
49.33%. Bank A has 120 units of operational loss, Bank B loses 60 through its
exposure to A, and Bank C loses 72 through its exposure to B. The six-bank
average includes three unaffected banks with zero stress.

## Current data flow

1. `backend.setup_db` creates PostgreSQL tables and seeds six banks/four services.
2. `backend.sync_graph` projects the two relationship types into Neo4j.
3. Next.js calls the FastAPI endpoints through `/api` rewrites.
4. FastAPI checks the graph version, calculates the cascade and saves a scenario,
   run and all bank impacts in one PostgreSQL transaction.
5. The UI reads the saved run and displays the impact table and recent history.

The demo's seed data is fictional and its risk score is a teaching metric, not
a financial forecast.
