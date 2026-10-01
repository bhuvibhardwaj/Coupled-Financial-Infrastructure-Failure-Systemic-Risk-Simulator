"use client";

import { useEffect, useState } from "react";

type Service = { id: number; name: string; category: string };
type RunSummary = {
  run_id: number;
  created_at: string;
  scenario_name: string;
  failed_service: string;
  severity: number;
  risk_score: string;
  default_count: number;
};
type Impact = {
  bank_name: string;
  first_affected_round: number | null;
  operational_loss: string;
  financial_loss: string;
  stress_pct: string;
  defaulted: boolean;
};
type RunDetail = RunSummary & { impacts: Impact[] };

async function readJson<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data && typeof data.detail === "string" ? data.detail : null;
    throw new Error(detail ?? `API request failed (${response.status}). Check that the backend is running.`);
  }
  if (data === null) throw new Error("API returned an invalid response.");
  return data as T;
}

function amount(value: string | number) {
  return Number(value).toFixed(2);
}

export default function Home() {
  const [services, setServices] = useState<Service[]>([]);
  const [recent, setRecent] = useState<RunSummary[]>([]);
  const [selectedService, setSelectedService] = useState("");
  const [name, setName] = useState("Payment Rail outage");
  const [severity, setSeverity] = useState(100);
  const [run, setRun] = useState<RunDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      fetch("/api/services").then(readJson<Service[]>),
      fetch("/api/runs").then(readJson<RunSummary[]>),
    ]).then(([list, history]) => {
      setServices(list);
      setRecent(history);
      if (list.length) setSelectedService(String(list[0].id));
    }).catch((cause: Error) => setError(cause.message));
  }, []);

  async function openRun(id: number) {
    setError("");
    setBusy(true);
    try {
      setRun(await fetch(`/api/runs/${id}`).then(readJson<RunDetail>));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load run");
    } finally {
      setBusy(false);
    }
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const created = await fetch("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          failed_service_id: Number(selectedService),
          severity: Number(severity),
        }),
      }).then(readJson<{ run_id: number }>);
      const [details, history] = await Promise.all([
        fetch(`/api/runs/${created.run_id}`).then(readJson<RunDetail>),
        fetch("/api/runs").then(readJson<RunSummary[]>),
      ]);
      setRun(details);
      setRecent(history);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Simulation failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="shell">
      <header className="intro">
        <p className="eyebrow">DBMS mini project · first milestone</p>
        <h1>Systemic Risk Simulator</h1>
        <p>See how an infrastructure outage can affect banks through operational dependencies and financial exposures.</p>
      </header>

      <section className="card">
        <div className="section-heading">
          <h2>Run a scenario</h2>
          <span className="hint">Fictional network: 6 banks · 4 services</span>
        </div>
        <form onSubmit={submit} className="scenario-form">
          <label>
            Scenario name
            <input value={name} onChange={(event) => setName(event.target.value)} required maxLength={100} />
          </label>
          <label>
            Failed service
            <select value={selectedService} onChange={(event) => setSelectedService(event.target.value)} required>
              {services.map((service) => <option key={service.id} value={service.id}>{service.name}</option>)}
            </select>
          </label>
          <label>
            Failure severity (%)
            <input type="number" min="0" max="100" value={severity}
              onChange={(event) => setSeverity(Number(event.target.value))} required />
          </label>
          <button disabled={busy || !selectedService} type="submit">
            {busy ? "Working…" : "Run simulation"}
          </button>
        </form>
        {error && <p className="error" role="alert">{error}</p>}
      </section>

      {run && <section className="card results">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Saved run #{run.run_id}</p>
            <h2>{run.scenario_name}</h2>
          </div>
          <span className="hint">{run.failed_service} · {run.severity}% severity</span>
        </div>
        <div className="metrics">
          <div><span>Average stress</span><strong>{amount(run.risk_score)}%</strong></div>
          <div><span>Defaulted banks</span><strong>{run.default_count}</strong></div>
          <div><span>Banks in network</span><strong>{run.impacts.length}</strong></div>
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Bank</th><th>First round</th><th>Operational loss</th><th>Financial loss</th><th>Stress</th><th>Status</th></tr></thead>
            <tbody>{run.impacts.map((impact) => <tr key={impact.bank_name}>
              <td>{impact.bank_name}</td>
              <td>{impact.first_affected_round ?? "—"}</td>
              <td>{amount(impact.operational_loss)}</td>
              <td>{amount(impact.financial_loss)}</td>
              <td>{amount(impact.stress_pct)}%</td>
              <td><span className={impact.defaulted ? "badge danger" : "badge"}>{impact.defaulted ? "Defaulted" : "Stable"}</span></td>
            </tr>)}</tbody>
          </table>
        </div>
        <p className="note">Stress is the bank&apos;s total loss divided by its liquidity buffer, capped at 100%. Risk score is average stress across all banks.</p>
      </section>}

      <section className="card history">
        <h2>Recent runs</h2>
        {recent.length === 0 ? <p className="hint">No simulations saved yet.</p> :
          <div className="history-list">{recent.map((item) =>
            <button key={item.run_id} type="button" disabled={busy} onClick={() => openRun(item.run_id)}>
              <span>{item.scenario_name}<small>{item.failed_service} · {item.severity}%</small></span>
              <strong>{amount(item.risk_score)}%</strong>
            </button>
          )}</div>}
      </section>
    </main>
  );
}
