import { useState } from "react";
import { Card } from "../components/Card";
import { useAuth } from "./AuthContext";

export default function Login() {
  const { authenticate } = useAuth();
  const [register, setRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError(null);
    try { await authenticate(email, password, register); }
    catch (err) { setError(err instanceof Error ? err.message : "Authentication failed."); }
    finally { setBusy(false); }
  }
  return <div className="flex min-h-screen items-center justify-center bg-vajra-bg p-6"><div className="w-full max-w-md"><div className="mb-6 text-center"><div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-vajra-accent to-vajra-accent2 text-lg font-bold text-white">V</div><h1 className="text-xl font-semibold text-slate-100">Vajra Security Lab</h1><p className="mt-1 text-sm text-slate-500">Secure access to your hunting workstation</p></div><Card><h2 className="mb-4 text-sm font-semibold text-slate-100">{register ? "Create your account" : "Sign in"}</h2><form onSubmit={submit} className="space-y-4"><label className="block"><span className="mb-1 block text-xs text-slate-400">Email</span><input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} className={inputClass} /></label><label className="block"><span className="mb-1 block text-xs text-slate-400">Password</span><input type="password" minLength={12} autoComplete={register ? "new-password" : "current-password"} required value={password} onChange={(e) => setPassword(e.target.value)} className={inputClass} /><span className="mt-1 block text-[11px] text-slate-600">Minimum 12 characters</span></label>{error && <div className="rounded-md border border-rose-500/40 bg-rose-500/5 p-3 text-xs text-rose-300">{error}</div>}<button disabled={busy} className="w-full rounded-md bg-vajra-accent px-4 py-2.5 text-sm font-medium text-white hover:bg-vajra-accent/90 disabled:opacity-50">{busy ? "Please wait..." : register ? "Create account" : "Sign in"}</button></form><button onClick={() => { setRegister(!register); setError(null); }} className="mt-4 w-full text-xs text-vajra-accent2 hover:underline">{register ? "Already have an account? Sign in" : "First time here? Create an account"}</button></Card></div></div>;
}
const inputClass = "w-full rounded-md border border-vajra-border bg-vajra-bg px-3 py-2 text-sm text-slate-200 focus:border-vajra-accent focus:outline-none";
