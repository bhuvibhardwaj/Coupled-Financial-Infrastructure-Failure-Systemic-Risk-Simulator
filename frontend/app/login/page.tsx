"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { api, User } from "../../lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api<User>("/auth/login", {
        method: "POST", body: JSON.stringify({ email, password }),
      });
      router.replace("/");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not sign in");
    } finally {
      setBusy(false);
    }
  }
  return <main className="login-shell">
    <section className="card login-card">
      <p className="eyebrow">DBMS mini project</p>
      <h1>Sign in</h1>
      <p className="hint">Use your seeded Admin or Analyst account.</p>
      <form onSubmit={submit} className="stack-form">
        <label>Email<input type="email" autoComplete="username" value={email}
          onChange={event => setEmail(event.target.value)} required /></label>
        <label>Password<input type="password" autoComplete="current-password"
          value={password} onChange={event => setPassword(event.target.value)} required /></label>
        <button type="submit" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
      </form>
      {error && <p className="error" role="alert">{error}</p>}
    </section>
  </main>;
}
