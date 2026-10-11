"use client";

import { FormEvent, useState } from "react";
import { api, Network } from "../lib/api";

type Entity = "banks" | "services" | "dependencies" | "exposures";
type Field = { name: string; label: string; kind: "text" | "number" | "bank" | "service"; step?: string };
type Row = Record<string, string | number>;

function definition(entity: Entity): Field[] {
  if (entity === "banks") return [
    { name: "name", label: "Bank name", kind: "text" },
    { name: "liquidity_buffer", label: "Liquidity buffer", kind: "number", step: "0.01" },
  ];
  if (entity === "services") return [
    { name: "name", label: "Service name", kind: "text" },
    { name: "category", label: "Category", kind: "text" },
  ];
  if (entity === "dependencies") return [
    { name: "institution_id", label: "Bank", kind: "bank" },
    { name: "infrastructure_id", label: "Service", kind: "service" },
    { name: "loss_at_full_failure", label: "Loss at full failure", kind: "number", step: "0.01" },
  ];
  return [
    { name: "creditor_id", label: "Creditor", kind: "bank" },
    { name: "debtor_id", label: "Debtor", kind: "bank" },
    { name: "amount", label: "Exposure amount", kind: "number", step: "0.01" },
    { name: "recovery_rate", label: "Recovery rate (0–1)", kind: "number", step: "0.001" },
  ];
}

function rows(entity: Entity, network: Network): Row[] {
  if (entity === "banks") return network.banks.map(bank =>
    ({ id: bank.id, name: bank.name, liquidity_buffer: bank.buffer }));
  if (entity === "services") return network.services;
  if (entity === "dependencies") return network.dependencies.map(edge =>
    ({ institution_id: edge.bank_id, infrastructure_id: edge.service_id,
       loss_at_full_failure: edge.loss }));
  return network.exposures;
}

function keyFor(entity: Entity, row: Row): string {
  if (entity === "dependencies") return `${row.institution_id}/${row.infrastructure_id}`;
  if (entity === "exposures") return `${row.creditor_id}/${row.debtor_id}`;
  return String(row.id);
}

function labelFor(entity: Entity, row: Row, network: Network): string {
  const bank = (id: string | number) => network.banks.find(b => b.id === Number(id))?.name ?? `Bank ${id}`;
  const service = (id: string | number) => network.services.find(s => s.id === Number(id))?.name ?? `Service ${id}`;
  if (entity === "banks") return `${row.name} · buffer ${row.liquidity_buffer}`;
  if (entity === "services") return `${row.name} · ${row.category}`;
  if (entity === "dependencies") return `${bank(row.institution_id)} depends on ${service(row.infrastructure_id)} · loss ${row.loss_at_full_failure}`;
  return `${bank(row.creditor_id)} exposed to ${bank(row.debtor_id)} · ${row.amount} at ${row.recovery_rate} recovery`;
}

export function NetworkEditor({ entity, network, refresh }: {
  entity: Entity; network: Network; refresh: () => Promise<void>;
}) {
  const fields = definition(entity);
  const entries = rows(entity, network);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const title = entity[0].toUpperCase() + entity.slice(1);
  const singular = {
    banks: "bank", services: "service", dependencies: "dependency", exposures: "exposure",
  }[entity];

  function edit(row: Row) {
    setEditingKey(keyFor(entity, row));
    setForm(Object.fromEntries(fields.map(field => [field.name, String(row[field.name] ?? "")])));
    setError("");
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const body = Object.fromEntries(fields.map(field =>
      [field.name, field.kind === "text" ? form[field.name]?.trim() : Number(form[field.name])]));
    try {
      await api(`/admin/${entity}${editingKey ? `/${editingKey}` : ""}`, {
        method: editingKey ? "PUT" : "POST", body: JSON.stringify(body),
      });
      setEditingKey(null); setForm({}); await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save");
    } finally { setBusy(false); }
  }

  async function remove(row: Row) {
    if (!window.confirm(`Delete ${labelFor(entity, row, network)}?`)) return;
    setBusy(true); setError("");
    try {
      await api(`/admin/${entity}/${keyFor(entity, row)}`, { method: "DELETE" });
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not delete");
    } finally { setBusy(false); }
  }

  return <section className="card editor-card">
    <h2>{title}</h2>
    <div className="editable-list">{entries.map(row =>
      <div className="editable-row" key={keyFor(entity, row)}>
        <span>{labelFor(entity, row, network)}</span>
        <div><button type="button" disabled={busy} onClick={() => edit(row)}>Edit</button>
          <button type="button" disabled={busy} onClick={() => remove(row)}>Delete</button></div>
      </div>)}</div>
    <h3>{editingKey ? `Edit ${singular}` : `Add ${singular}`}</h3>
    <form className="editor-form" onSubmit={save}>
      {fields.map(field => <label key={field.name}>{field.label}
        {field.kind === "bank" || field.kind === "service" ?
          <select value={form[field.name] ?? ""} required disabled={!!editingKey}
            onChange={event => setForm({ ...form, [field.name]: event.target.value })}>
            <option value="">Select…</option>
            {(field.kind === "bank" ? network.banks : network.services).map(option =>
              <option value={option.id} key={option.id}>{option.name}</option>)}</select> :
          <input type={field.kind} required step={field.step} min={field.kind === "number" ? "0" : undefined}
            value={form[field.name] ?? ""} onChange={event => setForm({ ...form, [field.name]: event.target.value })} />}
      </label>)}
      <button disabled={busy} type="submit">{busy ? "Saving…" : editingKey ? "Save changes" : "Add"}</button>
      {editingKey && <button type="button" onClick={() => { setEditingKey(null); setForm({}); }}>Cancel</button>}
    </form>
    {error && <p className="error" role="alert">{error}</p>}
  </section>;
}
