import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { api, SESSION_EXPIRED_EVENT, setRefreshToken, setToken } from "@/api/client";
import type { User } from "@/types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const hasToken = !!localStorage.getItem("jarvis_access_token");
    if (!hasToken) {
      setLoading(false);
      return;
    }
    // If the access token expired since the last visit, api.me() transparently
    // tries a refresh (via the stored refresh token) before failing — see
    // apiRequest in @/api/client. This only reaches .catch() once that's
    // genuinely failed too (no/invalid refresh token), at which point
    // SESSION_EXPIRED_EVENT below has already cleared `user`.
    api
      .me()
      .then((data) => setUser(data as User))
      .catch(() => setToken(null))
      .finally(() => setLoading(false));
  }, []);

  // Keeps `user` in sync when a token refresh fails anywhere in the app —
  // not just during the mount check above. Without this, a 401 hit by some
  // other request mid-session (e.g. sending a chat message an hour in)
  // would clear localStorage but leave the UI still rendering as logged in
  // until a full page reload.
  useEffect(() => {
    function handleSessionExpired() {
      setUser(null);
    }
    window.addEventListener(SESSION_EXPIRED_EVENT, handleSessionExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, handleSessionExpired);
  }, []);

  async function login(email: string, password: string) {
    const { access_token, refresh_token } = await api.login(email, password);
    setToken(access_token);
    setRefreshToken(refresh_token);
    const me = await api.me();
    setUser(me as User);
  }

  function logout() {
    setToken(null);
    setRefreshToken(null);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
