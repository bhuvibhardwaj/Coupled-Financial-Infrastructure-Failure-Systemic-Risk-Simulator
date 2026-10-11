# Coupled Financial Infrastructure Failure & Systemic Risk Simulator

## 1. Project idea

Banks depend on services such as payment systems and cloud providers. A service
failure can cause losses at a bank, which can then affect other banks connected
through financial exposures.

Build a small simulation using a fictional network. Users select a failed
service, inspect affected banks and propagation paths, and test whether adding
a liquidity buffer reduces the impact. The team should be able to explain the
database design and verify the simulation by hand.

## 2. Scope and final-brief requirements

The final course brief requires a **Next.js web application**, a SQL database
(PostgreSQL or MySQL), a second database paradigm, and an API/backend between
the UI and the databases. It also requires at least **four advanced SQL
concepts and one NoSQL/vector concept**. For this project, use PostgreSQL and
Neo4j. FastAPI is an allowed backend service; Python can remain the main
simulation language. Vector search is optional and does not suit this mostly
structured network data.

The project must show database design and operations, a usable Next.js UI,
two roles, validation, security, documentation and individual contributions.

### First-version features

Start with **6 banks and 4 infrastructure services**, with enough connections
to demonstrate a cascade across several banks.

The application will support:

1. Login with two roles: Admin and Analyst.
2. Admin forms for banks, services, dependencies and exposures.
3. A scenario form selecting one failed service and a severity percentage.
4. A simulation showing losses, liquidity stress and propagation rounds.
5. A simple network view and a table of failure-propagation paths.
6. A comparison after adding a liquidity buffer to one bank.
7. Saved run history with filtering and a risk summary.

Use synthetic data and describe the calculations as an educational model.
Multiple initial failures, recovery-time modelling, alternate providers, live
data, animations and downloadable reports can remain future enhancements.

## 3. Technology and database roles

| Technology | Use |
|---|---|
| Python + FastAPI | Main program: API, validation, scenario coordination, simulation rules and result saving. |
| PostgreSQL + pg8000 | Users, master data, scenarios, results and SQL reporting. Use parameterised SQL through a pure-Python driver. |
| Neo4j + Python driver | Dependency/exposure graph, affected-bank discovery and propagation paths. |
| Next.js + TypeScript | Required web application: pages, forms, search/filtering, dashboard and graph display. Keep simulation rules in Python. |
| Python password hashing/session library | Hashed passwords and role checks in the FastAPI backend. |

The browser uses the Next.js app, which calls FastAPI endpoints through a
Next.js API rewrite. This keeps the browser on one origin during development.
FastAPI is the backend/API layer and is the only process that talks to
PostgreSQL and Neo4j. A Python virtual environment manages backend packages;
npm manages the Next.js frontend. The final PDF explicitly permits an
appropriate backend service, so a Next.js Route Handler backend is an option,
not a requirement.

PostgreSQL holds the original data. Neo4j represents relationships for traversal
and path queries. Store credentials in environment variables and supply an
`.env.example`.

For this small dataset, provide one **Rebuild network** action after admin
changes. A Python backend function rebuilds the graph from PostgreSQL and
verifies node/edge counts before allowing simulations. Mark it stale after
further edits. If rebuilding fails, show an error and keep simulations
disabled. A PostgreSQL write and a Neo4j rebuild are separate operations, not
a shared transaction. Run network edits/rebuilds/simulations one at a time in
the first version to avoid using mixed data.

## 4. Roles and screens

**Admin:** maintain network data, rebuild the graph and use simulation features.
**Analyst:** view the network, create their own scenarios and run comparisons.
Enforce permissions and scenario ownership in FastAPI as well as the interface.

Keep the interface to five screens:

- **Login** — two seeded accounts; no registration/user-management screen needed.
- **Dashboard** — recent runs and a few summary numbers.
- **Network** — graph, dependency/exposure tables and admin editing forms.
- **Scenarios** — create scenarios and browse saved scenarios.
- **Run results** — impact table, paths and buffer comparison.

The results page handles mitigation without a separate management screen.

## 5. Database design

### PostgreSQL tables

Finalise columns and cardinalities in the ERD before implementation. Every table
has a primary key.

| Table | Main data and relationships |
|---|---|
| `users` / `user_sessions` | Name, unique email, password hash and role; hashed session token and expiry. |
| `institutions` | Bank name and initial liquidity buffer. |
| `infrastructure` | Service name and category. |
| `dependencies` | Bank FK, service FK and estimated loss at full failure. Unique bank/service pair. |
| `exposures` | Creditor-bank FK, debtor-bank FK, amount and recovery rate. Unique directed bank pair. |
| `scenarios` | Owner FK, name, failed-service FK and severity. |
| `simulation_runs` | Scenario FK, creator FK, timestamps, score, formula version and input snapshot. Optional baseline-run FK, buffer-bank FK and extra-buffer amount for comparisons. |
| `run_impacts` | Run FK, bank FK, first affected round, operational loss, financial loss and stress percentage. Unique run/bank pair. |
| `audit_logs` | Timestamp, changed table/record and old/new values for audited master-data changes. |

The input snapshot records the network and parameters used, so later edits do
not change a saved run's meaning. Comparison runs reuse that snapshot and record
the extra buffer; no separate mitigation tables are needed.

Add constraints for positive initial buffers, non-negative amounts,
severity/stress between 0 and 100, recovery rates between 0 and 1, valid roles
and no self-exposures. Use foreign keys and restrict deletion of records used
by scenarios/results. Unreferenced demo records can demonstrate deletion.

### Neo4j model

- `(:RiskInstitution {id, name})`
- `(:RiskInfrastructure {id, name})`
- `(bank)-[:DEPENDS_ON {loss}]->(service)`
- `(creditor)-[:EXPOSED_TO {amount, recovery_rate}]->(debtor)`

Enforce unique node IDs. A failed service affects incoming `DEPENDS_ON` banks;
a defaulted debtor affects incoming `EXPOSED_TO` creditors. Document the
direction clearly.

## 6. Simulation rules

Use one fixed rule set:

1. Read the selected service/severity and find dependent banks in Neo4j.
2. Calculate each dependent bank's operational loss:
   `loss at full failure × severity / 100`.
3. Reduce available buffers by cumulative losses. A bank defaults when losses
   reach or exceed its initial buffer.
4. For every newly defaulted debtor, find creditors in Neo4j. Each loses
   `exposure amount × (1 − recovery rate)`.
5. Repeat until no new defaults occur. Process each default and exposure loss
   only once, so cycles cannot double-count losses. Group losses by round before
   deciding which banks newly default.
6. Calculate each bank's stress:
   `min(100, 100 × total loss / initial buffer)`.
   The risk score is the average stress across all banks, including unaffected
   banks with zero stress.
7. Python saves the summary and all bank impacts together in a PostgreSQL
   transaction.

Rerun the same input snapshot with an extra buffer for one bank. Compare the
score and default count without modifying master data or rebuilding the shared
Neo4j graph. The original run already saved the graph-derived relationships,
which makes the comparison reproducible even after later edits. Show failed
runs clearly.

**Worked example:** A service failure costs Bank A 120 units against a buffer
of 100, so A defaults. Bank B has an exposure of 80 to A with a recovery rate of
25%; B loses 60 units. With a buffer of 50, B defaults too. Adding 20 to B's
buffer prevents B's default and can stop losses reaching another creditor.

For critical-node analysis, rank services by dependent-bank count and banks by
total exposure held by their creditors. Label these as simple connectivity
indicators. Show actual simulated paths separately; connectivity alone is not a
failure probability.

## 7. Database features for evaluation

The final brief requires at least **four SQL** advanced concepts and **one
NoSQL/vector** concept. Implement the following, with clear demo evidence:

| Database / feature | Demonstration |
|---|---|
| PostgreSQL transaction | Save a run and all bank results together; demonstrate rollback. |
| PostgreSQL view | Join scenarios, runs and users for the dashboard summary. |
| PostgreSQL stored function | Calculate average bank stress for a saved run. |
| PostgreSQL trigger | Audit changes to institution and infrastructure records. |
| PostgreSQL indexes | Index scenario owner and run scenario/date; explain which queries they support. |
| Neo4j aggregation | Use Cypher `count()` to rank services by dependent-bank count, and `sum()` to total exposure by debtor. Display one result on the network page. |

Prepare a short SQL script covering CREATE, ALTER and DROP on a disposable demo
table, plus INSERT, UPDATE, DELETE and SELECT. Include:

- JOINs for run/scenario/user details.
- GROUP BY and aggregates for losses by bank.
- HAVING for banks exceeding an average-stress threshold.
- ORDER BY for highest-risk runs.
- A subquery for runs above the overall average score.

Include Cypher queries for dependent banks, exposed creditors, multi-hop
paths and the required aggregation. Explain how a candidate graph path is
checked against simulated defaults/rounds before presenting it as an actual
propagation path. Document Neo4j nodes, relationships, properties, constraints,
indexes and traversal/aggregation strategy.

## 8. Work plan

This is a suggested sequence; adjust the weeks to the actual deadline.

| Stage | Deliverable |
|---|---|
| Week 1: design | Confirm scope/title, draw ERD and graph model, choose seed data and work through one cascade by hand. |
| Week 2: databases | PostgreSQL schema/constraints, seed data, Python graph rebuild, SQL/Cypher queries and advanced features. |
| Week 3: first working flow | FastAPI simulation/save endpoints and a small Next.js service-selection form plus results table; add login/roles. |
| Week 4: complete web interface | Next.js dashboard, network view, admin forms, paths, comparison and error handling. |
| Week 5: submission | Test, fix problems, complete documentation/screenshots and rehearse. |

First milestone in the required Next.js interface: **select a service → call
FastAPI → run the cascade → save results → show the impact table**. Add graph
presentation and mitigation after this works.

### Two-member split

| Member | Database responsibility | Application responsibility |
|---|---|---|
| A | PostgreSQL schema, seed data, SQL features and Python result persistence. | FastAPI master-data/scenario endpoints and their Next.js forms. |
| B | Neo4j model, Python rebuild/path queries and cascade calculations. | FastAPI run/auth endpoints and Next.js network/results pages. |

Both review the simulation, test integration and contribute to the report.
Commit work as it is completed so history reflects actual progress and individual
contributions.

## 9. Testing and submission

Maintain a table of inputs, expected outcomes, actual outcomes and pass/fail.
Cover:

- A service with no dependents and a zero-severity failure.
- The worked cascade, a cycle and a bank with multiple loss sources.
- A buffer comparison that prevents a default.
- Invalid amounts/FKs, duplicate edges and transaction rollback.
- Admin versus Analyst access and scenario ownership.
- A stale graph or failed rebuild preventing a run.
- A saved-run comparison after master data changes.

Use parameterised queries, hashed passwords and FastAPI validation backed by
database constraints. Add Python unit tests for the cascade using the
hand-calculated example, plus a small integration test for saving a run.

Submit documentation as a soft copy containing the problem statement, objectives, scope,
requirements, ERD, relational schema/data dictionary, graph model, database
justification, architecture, key queries/features, screenshots, test results,
limitations and future enhancements. Include setup, environment variables,
database creation, seeding and execution in the README. Document both the
Python virtual-environment commands and the Next.js npm commands.

For the demo, show the network, run the worked example, inspect a path, add a
buffer and compare results. Then demonstrate SQL features and each member's
contribution.

Use the linked repository as a reference. The assignment requires original
design and implementation; confirm the title is unique within the section and
develop the team's own schema, rules and demonstration data.

## Implementation status

The planned features, SQL/Cypher demonstrations and design documentation are
implemented in the repository. The full-system run, live database results,
application screenshots and two members' final contribution evidence remain
for the submission stage; see `docs/TEST_STATUS.md`.
