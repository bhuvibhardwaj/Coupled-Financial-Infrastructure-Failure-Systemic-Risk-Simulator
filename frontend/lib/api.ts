export type User = { id: number; name: string; email: string; role: "admin" | "analyst" };
export type Service = { id: number; name: string; category: string };
export type Bank = { id: number; name: string; buffer: string };
export type Dependency = { bank_id: number; service_id: number; loss: string };
export type Exposure = { creditor_id: number; debtor_id: number; amount: string; recovery_rate: string };
export type Network = {
  banks: Bank[];
  services: Service[];
  dependencies: Dependency[];
  exposures: Exposure[];
  graph_current: boolean;
  service_ranking: { id: number; name: string; dependent_banks: number }[];
  bank_ranking: { id: number; name: string; creditor_exposure: number }[];
};
export type RunSummary = {
  run_id: number;
  created_at: string;
  scenario_name: string;
  failed_service: string;
  severity: number;
  risk_score: string | number;
  default_count: number;
  baseline_run_id: number | null;
  extra_buffer: string | number | null;
  mitigation_bank_id?: number | null;
};
export type Impact = {
  bank_id: number;
  bank_name: string;
  first_affected_round: number | null;
  operational_loss: string | number;
  financial_loss: string | number;
  stress_pct: string | number;
  defaulted: boolean;
  propagation_path: string[];
};
export type RunDetail = RunSummary & { impacts: Impact[] };

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data?.detail;
    const message = typeof detail === "string" ? detail :
      `Request failed (${response.status}). Check that the Python API is running.`;
    throw new Error(message);
  }
  if (data === null) throw new Error("The API returned an invalid response.");
  return data as T;
}

export function amount(value: string | number | null | undefined): string {
  return Number(value ?? 0).toFixed(2);
}
