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
  const [selected, setSelected] = useState<Record<number, number>>({});
  const [name, setName] = useState("Payment Rail outage");
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!user) return;
    Promise.all([api<Service[]>("/services"), api<RunSummary[]>("/runs")])
      .then(([list, history]) => {
        setServices(list); setRuns(history);
        if (list.length) setSelected({ [list[0].id]: 100 });
      }).catch((cause: Error) => setError(cause.message));
  }, [user]);

  function toggleService(id: number) {
    setSelected(previous => {
      const next = { ...previous };
      if (id in next) delete next[id]; else next[id] = 100;
      return next;
    });
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const failures = Object.entries(selected).map(([id, value]) => ({
      service_id: Number(id), severity: Number(value),
    }));
    if (failures.some(item => !Number.isInteger(item.severity) || item.severity < 0 || item.severity > 100)) {
      setError("Each severity must be a whole number between 0 and 100."); setBusy(false); return;
    }
    try {
      const created = await api<{ run_id: number }>("/runs", {
        method: "POST",
        body: JSON.stringify({ name: name.trim(), failures }),
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
      <p>Select one or more failed services and set each severity. Each run saves the network inputs and results for later comparison.</p></header>
    <section className="card">
      <h2>Run a new scenario</h2>
      <form onSubmit={submit} className="stack-form">
        <label>Scenario name<input value={name} onChange={event => setName(event.target.value)} required maxLength={100} /></label>
        <div>
          <p className="field-label">Failed services</p>
          <p className="hint">Tick each service to fail and set its severity from 0 to 100%.</p>
          <div className="editable-list">
            {services.map(service => {
              const chosen = service.id in selected;
              return <div className="editable-row service-option" key={service.id}>
                <label className="service-choice">
                  <input type="checkbox" checked={chosen} onChange={() => toggleService(service.id)} />
                  <span>{service.name} <small>{service.category}</small></span>
                </label>
                <input className="severity-input" type="number" min="0" max="100" step="1"
                  value={chosen ? selected[service.id] : ""} disabled={!chosen} required={chosen}
                  aria-label={`${service.name} severity`}
                  onChange={event => setSelected(previous => ({ ...previous, [service.id]: Number(event.target.value) }))} />
              </div>;
            })}
          </div>
        </div>
        <button disabled={busy || !Object.keys(selected).length} type="submit">{busy ? "Running…" : "Run simulation"}</button>
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
