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
    setError("");
    if (!email.trim() || !password) {
      setError("Enter your email or username and password.");
      return;
    }
    setBusy(true);
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 15000);
    try {
      await api<User>("/auth/login", {
        method: "POST", body: JSON.stringify({ email: email.trim(), password }),
        signal: controller.signal,
      });
      router.replace("/");
    } catch (cause) {
      setError(controller.signal.aborted
        ? "Sign-in timed out. Check that the launcher is still running, then try again."
        : cause instanceof TypeError ? "Could not reach the server. Check that the launcher is still running."
        : cause instanceof Error ? cause.message : "Could not sign in. Please try again.");
    } finally {
      setBusy(false);
      window.clearTimeout(timeout);
    }
  }
  return <main className="login-shell">
    <section className="card login-card">
      <p className="eyebrow">DBMS mini project</p>
      <h1>Sign in</h1>
      <p className="hint">Sign in with your email or demo username.</p>
      <form onSubmit={submit} className="stack-form" noValidate aria-busy={busy}>
        <label>Email or username<input type="text" autoComplete="username" value={email}
          onChange={event => setEmail(event.target.value)} required maxLength={255}
          autoCapitalize="none" spellCheck={false} aria-describedby={error ? "login-error" : undefined} /></label>
        <label>Password<input type="password" autoComplete="current-password"
          value={password} onChange={event => setPassword(event.target.value)} required /></label>
        <button type="submit" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
      </form>
      <div aria-live="assertive" aria-atomic="true">
        {error && <p className="error" id="login-error" role="alert">{error}</p>}
      </div>
      <p className="note">Local demo logins:<br />
        Admin: <code>admin</code> / <code>admin123</code><br />
        Analyst: <code>analyst</code> / <code>analyst123</code>
      </p>
    </section>
  </main>;
}
