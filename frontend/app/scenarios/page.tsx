"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Nav } from "../../components/Nav";
import { amount, api, RunSummary, Service } from "../../lib/api";
import { useSession } from "../../lib/session";

export default function ScenariosPage() {
  const router = useRouter();
  const { user, loading, error: sessionError } = useSession();
  const [services, setServices] = useState<Service[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [serviceId, setServiceId] = useState("");
  const [name, setName] = useState("Payment Rail outage");
  const [severity, setSeverity] = useState(100);
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!user) return;
    Promise.all([api<Service[]>("/services"), api<RunSummary[]>("/runs")])
      .then(([list, history]) => {
        setServices(list); setRuns(history);
        if (list.length) setServiceId(String(list[0].id));
      }).catch((cause: Error) => setError(cause.message));
  }, [user]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const created = await api<{ run_id: number }>("/runs", {
        method: "POST",
        body: JSON.stringify({ name: name.trim(), failed_service_id: Number(serviceId), severity }),
      });
      router.push(`/runs/${created.run_id}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Simulation failed");
    } finally { setBusy(false); }
  }

  if (loading) return <main className="shell">Loading scenarios…</main>;
  if (!user) return <main className="shell">{sessionError || "Opening login…"}</main>;
  const filtered = runs.filter(run => run.scenario_name.toLowerCase().includes(search.toLowerCase()));
  return <main className="shell">
    <Nav user={user} />
    <header className="intro"><p className="eyebrow">Simulations</p><h1>Scenarios</h1>
      <p>Choose one failed service and a severity. Each run saves the network inputs and results for later comparison.</p></header>
    <section className="card">
      <h2>Run a new scenario</h2>
      <form onSubmit={submit} className="scenario-form with-top-gap">
        <label>Scenario name<input value={name} onChange={event => setName(event.target.value)} required maxLength={100} /></label>
        <label>Failed service<select value={serviceId} onChange={event => setServiceId(event.target.value)} required>
          {services.map(service => <option key={service.id} value={service.id}>{service.name}</option>)}</select></label>
        <label>Severity (%)<input type="number" min="0" max="100" value={severity}
          onChange={event => setSeverity(Number(event.target.value))} required /></label>
        <button disabled={busy || !serviceId} type="submit">{busy ? "Running…" : "Run simulation"}</button>
      </form>
      {error && <p className="error" role="alert">{error}</p>}
    </section>
    <section className="card">
      <div className="section-heading"><h2>Saved runs</h2>
        <input className="search-input" placeholder="Search scenario name" value={search}
          onChange={event => setSearch(event.target.value)} aria-label="Search scenarios" /></div>
      {filtered.length === 0 ? <p className="hint">No matching runs.</p> :
        <div className="history-list">{filtered.map(run =>
          <Link href={`/runs/${run.run_id}`} key={run.run_id}>
            <span>{run.scenario_name}<small>{run.failed_service} · {run.severity}% · {new Date(run.created_at).toLocaleString()}
              {run.baseline_run_id !== null ? " · comparison" : ""}</small></span>
            <strong>{amount(run.risk_score)}%</strong>
          </Link>)}</div>}
    </section>
  </main>;
}
