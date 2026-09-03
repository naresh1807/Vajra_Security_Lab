import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { AuthUser } from "../types";

interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  authenticate: (email: string, password: string, register: boolean) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { api.me().then(setUser).catch(() => setUser(null)).finally(() => setLoading(false)); }, []);
  useEffect(() => {
    const expired = () => setUser(null);
    window.addEventListener("vajra:unauthorized", expired);
    return () => window.removeEventListener("vajra:unauthorized", expired);
  }, []);
  async function authenticate(email: string, password: string, register: boolean) {
    setUser(register ? await api.register(email, password) : await api.login(email, password));
  }
  async function logout() { await api.logout(); setUser(null); }
  return <AuthContext.Provider value={{ user, loading, authenticate, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
