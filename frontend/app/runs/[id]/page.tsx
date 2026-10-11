"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Nav } from "../../../components/Nav";
import { amount, api, RunDetail } from "../../../lib/api";
import { useSession } from "../../../lib/session";

type Trace = { path: string[]; graph_current: boolean; verified_in_graph: boolean | null };

export default function RunPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user, loading, error: sessionError } = useSession();
  const [run, setRun] = useState<RunDetail | null>(null);
  const [baseline, setBaseline] = useState<RunDetail | null>(null);
  const [bankId, setBankId] = useState("");
  const [extraBuffer, setExtraBuffer] = useState("20");
  const [trace, setTrace] = useState<Trace | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!user) return;
    setRun(null);
    setBaseline(null);
    setTrace(null);
    api<RunDetail>(`/runs/${params.id}`).then(async detail => {
      setRun(detail);
      const first = detail.impacts.find(item => item.bank_name === "Bank B") ?? detail.impacts[0];
      if (first) setBankId(String(first.bank_id));
      if (detail.baseline_run_id !== null) {
        setBaseline(await api<RunDetail>(`/runs/${detail.baseline_run_id}`));
      }
    }).catch((cause: Error) => setError(cause.message));
  }, [user, params.id]);

  async function compare(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const result = await api<{ run_id: number }>(`/runs/${params.id}/compare`, {
        method: "POST", body: JSON.stringify({ bank_id: Number(bankId), extra_buffer: extraBuffer }),
      });
      router.push(`/runs/${result.run_id}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Comparison failed");
    } finally { setBusy(false); }
  }

  async function inspectPath(id: number) {
    setTrace(null); setError("");
    try {
      setTrace(await api<Trace>(`/runs/${params.id}/trace/${id}`));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not inspect path");
    }
  }

  if (loading) return <main className="shell">Loading run…</main>;
  if (!user) return <main className="shell">{sessionError || "Opening login…"}</main>;
  return <main className="shell">
    <Nav user={user} />
    {error && <p className="error" role="alert">{error}</p>}
    {!run ? <p className="hint">Loading saved run…</p> : <>
      <header className="intro"><p className="eyebrow">Saved run #{run.run_id}</p>
        <h1>{run.scenario_name}</h1>
        <p>{run.failed_service} · {run.severity}% severity · {new Date(run.created_at).toLocaleString()}</p>
        {run.baseline_run_id !== null && <p><Link href={`/runs/${run.baseline_run_id}`}>View original run #{run.baseline_run_id}</Link></p>}
      </header>
      <section className="metrics">
        <div><span>Average stress</span><strong>{amount(run.risk_score)}%</strong></div>
        <div><span>Defaulted banks</span><strong>{run.default_count}</strong></div>
        <div><span>Banks measured</span><strong>{run.impacts.length}</strong></div>
      </section>
      {baseline && <section className="card comparison">
        <h2>Buffer comparison</h2>
        <p>Extra buffer: {amount(run.extra_buffer)}. Risk score changed from
          {` ${amount(baseline.risk_score)}%`} to {amount(run.risk_score)}%; defaults from
          {` ${baseline.default_count}`} to {run.default_count}.</p>
      </section>}
      <section className="card">
        <h2>Bank impacts</h2>
        <div className="table-wrap with-top-gap"><table>
          <thead><tr><th>Bank</th><th>Round</th><th>Operational loss</th><th>Financial loss</th><th>Stress</th><th>Status</th><th>Path</th></tr></thead>
          <tbody>{run.impacts.map(item => <tr key={item.bank_id}>
            <td>{item.bank_name}</td><td>{item.first_affected_round ?? "—"}</td>
            <td>{amount(item.operational_loss)}</td><td>{amount(item.financial_loss)}</td>
            <td>{amount(item.stress_pct)}%</td>
            <td><span className={item.defaulted ? "badge danger" : "badge"}>{item.defaulted ? "Defaulted" : "Stable"}</span></td>
            <td>{item.propagation_path?.length ? <button className="text-button" type="button"
              onClick={() => inspectPath(item.bank_id)}>Inspect</button> : "—"}</td>
          </tr>)}</tbody>
        </table></div>
        {trace && <div className="trace-panel"><strong>Propagation path</strong>
          <p>{trace.path.join(" → ")}</p>
          <small>{trace.graph_current
            ? trace.verified_in_graph ? "Path also verified in the current Neo4j graph."
              : "Saved simulation path; current graph has a different candidate path."
            : "Saved simulation path; the current graph has changed or is unavailable."}</small>
        </div>}
        <p className="note">Risk score = average of bank stress percentages. Each bank&apos;s stress is cumulative loss ÷ its liquidity buffer, capped at 100%.</p>
      </section>
      {run.baseline_run_id === null && <section className="card">
        <h2>Test a liquidity buffer</h2>
        <p className="hint">Rerun the same saved network with extra buffer for one bank. Master data will not change.</p>
        <form className="compare-form" onSubmit={compare}>
          <label>Bank<select value={bankId} onChange={event => setBankId(event.target.value)} required>
            {run.impacts.map(item => <option key={item.bank_id} value={item.bank_id}>{item.bank_name}</option>)}</select></label>
          <label>Additional buffer<input type="number" min="0.01" step="0.01" value={extraBuffer}
            onChange={event => setExtraBuffer(event.target.value)} required /></label>
          <button type="submit" disabled={busy || !bankId}>{busy ? "Comparing…" : "Compare with baseline"}</button>
        </form>
      </section>}
    </>}
  </main>;
}
