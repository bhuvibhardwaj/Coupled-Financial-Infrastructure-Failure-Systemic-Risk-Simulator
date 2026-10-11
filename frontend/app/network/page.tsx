"use client";

import { useCallback, useEffect, useState } from "react";
import { Nav } from "../../components/Nav";
import { NetworkEditor } from "../../components/NetworkEditor";
import { NetworkGraph } from "../../components/NetworkGraph";
import { amount, api, Network } from "../../lib/api";
import { useSession } from "../../lib/session";

type AuditEntry = {
  id: number; changed_at: string; table_name: string;
  action: string; record_id: number; actor_name: string | null;
};

export default function NetworkPage() {
  const { user, loading, error: sessionError } = useSession();
  const [network, setNetwork] = useState<Network | null>(null);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setNetwork(await api<Network>("/network"));
    if (user?.role === "admin") setAudit(await api<AuditEntry[]>("/admin/audit"));
  }, [user]);

  useEffect(() => { if (user) refresh().catch((cause: Error) => setError(cause.message)); }, [user, refresh]);

  async function sync() {
    setBusy(true); setError("");
    try {
      await api("/admin/network/rebuild", { method: "POST" });
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not rebuild graph");
    } finally { setBusy(false); }
  }

  if (loading) return <main className="shell">Loading network…</main>;
  if (!user) return <main className="shell">{sessionError || "Opening login…"}</main>;
  return <main className="shell">
    <Nav user={user} />
    <header className="intro"><p className="eyebrow">Two connected layers</p>
      <h1>Network</h1>
      <p>Banks depend on infrastructure services and hold exposures to other banks. Arrows point from creditor to debtor.</p>
    </header>
    {error && <p className="error" role="alert">{error}</p>}
    {!network ? <p className="hint">Loading network data…</p> : <>
      <section className="card">
        <div className="section-heading"><h2>Graph overview</h2>
          <span className={network.graph_current ? "badge" : "badge danger"}>
            {network.graph_current ? "Neo4j in sync" : "Graph needs rebuild"}</span></div>
        <NetworkGraph network={network} />
        {!network.graph_current && <p className="note">This is the PostgreSQL network preview. Rebuild Neo4j before running a new simulation.</p>}
        {user.role === "admin" && <button className="primary-button" type="button" disabled={busy}
          onClick={sync}>{busy ? "Rebuilding…" : "Rebuild Neo4j network"}</button>}
      </section>
      {network.graph_current && <section className="card">
        <h2>Critical-node indicators</h2>
        <p className="note">Cypher aggregation ranks services by dependent banks and banks by creditor exposure. These are connectivity indicators, not failure probabilities.</p>
        <div className="ranking-grid">
          <div><h3>Services by dependents</h3>{network.service_ranking.map(item =>
            <p key={item.id}>{item.name} <strong>{item.dependent_banks}</strong></p>)}</div>
          <div><h3>Banks by creditor exposure</h3>{network.bank_ranking.map(item =>
            <p key={item.id}>{item.name} <strong>{amount(item.creditor_exposure)}</strong></p>)}</div>
        </div>
      </section>}
      {user.role === "admin" && <>
        <div className="section-heading admin-heading"><h2>Administrator: edit the network</h2>
          <span className="hint">Rebuild Neo4j after edits.</span></div>
        <NetworkEditor entity="banks" network={network} refresh={refresh} />
        <NetworkEditor entity="services" network={network} refresh={refresh} />
        <NetworkEditor entity="dependencies" network={network} refresh={refresh} />
        <NetworkEditor entity="exposures" network={network} refresh={refresh} />
        <section className="card"><h2>Recent master-data audit</h2>
          {audit.length === 0 ? <p className="hint">No audited changes yet.</p> :
            <div className="table-wrap"><table><thead><tr><th>When</th><th>Who</th><th>Action</th><th>Table</th><th>Record</th></tr></thead>
              <tbody>{audit.map(item => <tr key={item.id}><td>{new Date(item.changed_at).toLocaleString()}</td>
                <td>{item.actor_name ?? "Setup"}</td><td>{item.action}</td>
                <td>{item.table_name}</td><td>{item.record_id}</td></tr>)}</tbody></table></div>}
        </section>
      </>}
    </>}
  </main>;
}
