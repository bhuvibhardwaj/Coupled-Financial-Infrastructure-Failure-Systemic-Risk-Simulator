"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Nav } from "../components/Nav";
import { amount, api, RunSummary } from "../lib/api";
import { useSession } from "../lib/session";

export default function Dashboard() {
  const { user, loading, error: sessionError } = useSession();
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    if (user) api<RunSummary[]>("/runs").then(setRuns)
      .catch((cause: Error) => setError(cause.message));
  }, [user]);
  if (loading) return <main className="shell">Loading dashboard…</main>;
  if (!user) return <main className="shell">{sessionError || "Opening login…"}</main>;
  const originals = runs.filter(run => run.baseline_run_id === null);
  const latest = runs[0];
  return <main className="shell">
    <Nav user={user} />
    <header className="intro">
      <p className="eyebrow">DBMS mini project · fictional network</p>
      <h1>Systemic Risk Simulator</h1>
      <p>Explore how a shared service outage can put banks under stress and pass losses to creditors.</p>
    </header>
    {error && <p className="error" role="alert">{error}</p>}
    <section className="metrics dashboard-metrics">
      <div><span>Recent original runs</span><strong>{originals.length}</strong></div>
      <div><span>Recent comparisons</span><strong>{runs.length - originals.length}</strong></div>
      <div><span>Latest risk score</span><strong>{latest ? `${amount(latest.risk_score)}%` : "—"}</strong></div>
    </section>
    <section className="card">
      <div className="section-heading"><h2>Recent runs</h2><Link className="button-link" href="/scenarios">New scenario</Link></div>
      {runs.length === 0 ? <p className="hint">No simulations saved yet. Create a scenario to begin.</p> :
        <div className="history-list">{runs.slice(0, 10).map(run =>
          <Link href={`/runs/${run.run_id}`} key={run.run_id}>
            <span>{run.scenario_name}<small>{run.failed_service} · {run.severity}% severity
              {run.baseline_run_id !== null ? " · buffer comparison" : ""}</small></span>
            <strong>{amount(run.risk_score)}%</strong>
          </Link>
        )}</div>}
    </section>
    <section className="card">
      <h2>What the score means</h2>
      <p className="note">Each bank&apos;s stress is its cumulative loss divided by its liquidity buffer, capped at 100%. The scenario score is the average across all banks. This is an educational model using synthetic data.</p>
    </section>
  </main>;
}
