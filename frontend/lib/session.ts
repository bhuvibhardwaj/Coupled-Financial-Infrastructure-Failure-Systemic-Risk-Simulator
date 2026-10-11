"use client";

import { useEffect, useState } from "react";
import { api, User } from "./api";

export function useSession() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    api<User>("/auth/me").then(setUser).catch((cause: Error) => {
      if (cause.message.includes("sign in") || cause.message.includes("expired")) {
        window.location.replace("/login");
      } else {
        setError(cause.message);
      }
    }).finally(() => setLoading(false));
  }, []);
  return { user, loading, error };
}
