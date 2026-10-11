"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, User } from "../lib/api";

export function Nav({ user }: { user: User }) {
  const router = useRouter();
  async function logout() {
    await api<{ ok: boolean }>("/auth/logout", { method: "POST" });
    router.replace("/login");
  }
  return <nav className="top-nav" aria-label="Main navigation">
    <Link href="/">Dashboard</Link>
    <Link href="/scenarios">Scenarios</Link>
    <Link href="/network">Network</Link>
    <span className="nav-user">{user.name} · {user.role}</span>
    <button type="button" onClick={logout}>Sign out</button>
  </nav>;
}
